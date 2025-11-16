from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .. import models, schemas
from ..utils import notifications, helpers

EVENT_CATEGORIES = {
    "agent": ["register", "heartbeat", "config_update", "offline", "online"],
    "backup": ["start", "success", "failed", "warning"],
    "system": ["startup", "shutdown", "error", "maintenance"],
    "security": ["login", "logout", "unauthorized", "config_change"]
}

EVENT_PRIORITIES = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}

def create_event(
    db: Session,
    category: str,
    event_type: str,
    description: str,
    agent_id: Optional[str] = None,
    backup_job_id: Optional[int] = None,
    related_id: Optional[str] = None,
    details: Optional[Dict] = None,
    priority: str = "medium"
):
    """Cria um novo evento no sistema"""
    if category not in EVENT_CATEGORIES:
        raise ValueError(f"Categoria de evento inválida: {category}")
    
    if event_type not in EVENT_CATEGORIES[category]:
        raise ValueError(f"Tipo de evento inválido para categoria {category}: {event_type}")
    
    if priority not in EVENT_PRIORITIES:
        raise ValueError(f"Prioridade inválida: {priority}")
    
    event = models.SystemEvent(
        category=category,
        event_type=event_type,
        description=description,
        agent_id=agent_id,
        backup_job_id=backup_job_id,
        related_id=related_id,
        details=json.dumps(details) if details else None,
        priority=priority,
        timestamp=datetime.utcnow()
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    # Enviar notificação para eventos importantes
    if EVENT_PRIORITIES[priority] >= EVENT_PRIORITIES["high"]:
        send_event_notification(db, event)
    
    return event

def send_event_notification(db: Session, event: models.SystemEvent):
    """Envia notificação para eventos importantes"""
    title = f"Evento {event.priority.upper()}: {event.event_type}"
    
    if event.category == "agent":
        if event.event_type == "offline":
            message = f"Agente {event.agent_id} está offline há mais de 15 minutos"
        elif event.event_type == "failed":
            message = f"Backup falhou no agente {event.agent_id}"
    elif event.category == "backup":
        if event.event_type == "failed":
            message = f"Backup falhou no agente {event.agent_id}"
    else:
        message = event.description
    
    notifications.send_notification(
        db,
        title=title,
        message=message,
        category=event.category,
        priority=event.priority,
        related_id=event.agent_id or event.related_id
    )

def get_events(
    db: Session,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    agent_id: Optional[str] = None,
    days: int = 7,
    skip: int = 0,
    limit: int = 50
):
    """Obtém eventos do sistema com filtros"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(models.SystemEvent).filter(
        models.SystemEvent.timestamp >= start_date
    )
    
    if category:
        query = query.filter(models.SystemEvent.category == category)
    
    if priority:
        query = query.filter(models.SystemEvent.priority == priority)
    
    if agent_id:
        query = query.filter(models.SystemEvent.agent_id == agent_id)
    
    events = query.order_by(models.SystemEvent.timestamp.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": event.id,
            "category": event.category,
            "event_type": event.event_type,
            "description": event.description,
            "agent_id": event.agent_id,
            "backup_job_id": event.backup_job_id,
            "related_id": event.related_id,
            "details": json.loads(event.details) if event.details else None,
            "priority": event.priority,
            "timestamp": event.timestamp.isoformat()
        } for event in events
    ]

def get_event_summary(db: Session, days: int = 7):
    """Obtém resumo de eventos por categoria e prioridade"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = """
    SELECT 
        category,
        priority,
        COUNT(*) as event_count,
        MAX(timestamp) as last_event
    FROM system_events
    WHERE timestamp >= :start_date
    GROUP BY category, priority
    ORDER BY event_count DESC
    """
    
    result = db.execute(text(query), {"start_date": start_date}).fetchall()
    
    summary = {}
    for row in result:
        category = row[0]
        priority = row[1]
        
        if category not in summary:
            summary[category] = {
                "total_events": 0,
                "by_priority": {},
                "last_event": None
            }
        
        summary[category]["total_events"] += row[2]
        summary[category]["by_priority"][priority] = row[2]
        
        if not summary[category]["last_event"] or row[3] > summary[category]["last_event"]:
            summary[category]["last_event"] = row[3]
    
    return summary

def get_agent_events(db: Session, agent_id: str, days: int = 7):
    """Obtém eventos específicos de um agente"""
    return get_events(db, agent_id=agent_id, days=days)

def get_backup_events(db: Session, backup_job_id: int, days: int = 7):
    """Obtém eventos específicos de um job de backup"""
    return get_events(db, backup_job_id=backup_job_id, days=days)

def cleanup_old_events(db: Session, days: int = 90):
    """Remove eventos antigos do banco de dados"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    deleted_count = db.query(models.SystemEvent).filter(
        models.SystemEvent.timestamp < cutoff_date
    ).delete()
    
    db.commit()
    return deleted_count