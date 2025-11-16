from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .. import models, schemas
from ..utils import helpers
from ..services import email

NOTIFICATION_TYPES = {
    "agent_offline": {
        "title": "Agente Offline",
        "priority": "high",
        "email_template": "agent_offline.html"
    },
    "backup_failed": {
        "title": "Backup Falhou",
        "priority": "high",
        "email_template": "backup_failed.html"
    },
    "storage_warning": {
        "title": "Espaço em Disco Baixo",
        "priority": "medium",
        "email_template": "storage_warning.html"
    },
    "system_alert": {
        "title": "Alerta do Sistema",
        "priority": "medium",
        "email_template": "system_alert.html"
    }
}

def send_notification(
    db: Session,
    title: str,
    message: str,
    category: str,
    priority: str = "medium",
    related_id: Optional[str] = None,
    user_id: Optional[int] = None,
    send_email: bool = True
):
    """Envia notificação e opcionalmente email"""
    # Criar notificação no banco
    notification = models.Notification(
        title=title,
        message=message,
        category=category,
        priority=priority,
        related_id=related_id,
        user_id=user_id,
        read=False,
        timestamp=datetime.utcnow()
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # Enviar email se necessário
    if send_email and should_send_email(priority):
        try:
            email.send_notification_email(
                to=get_notification_emails(db, category),
                subject=title,
                template="notification.html",
                context={
                    "title": title,
                    "message": message,
                    "category": category,
                    "priority": priority,
                    "timestamp": datetime.utcnow().isoformat(),
                    "related_id": related_id
                }
            )
        except Exception as e:
            print(f"Erro ao enviar email de notificação: {e}")
    
    return notification

def should_send_email(priority: str) -> bool:
    """Verifica se deve enviar email baseado na prioridade"""
    email_priorities = ["high", "critical"]
    return priority in email_priorities

def get_notification_emails(db: Session, category: str) -> List[str]:
    """Obtém emails para notificações com base na categoria"""
    # Para MVP, retornar email administrador
    admin_user = db.query(models.User).filter(models.User.is_superuser == True).first()
    return [admin_user.email] if admin_user else []

def get_user_notifications(db: Session, user_id: int, read: Optional[bool] = None, limit: int = 20):
    """Obtém notificações do usuário"""
    query = db.query(models.Notification).filter(models.Notification.user_id == user_id)
    
    if read is not None:
        query = query.filter(models.Notification.read == read)
    
    notifications = query.order_by(models.Notification.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "category": n.category,
            "priority": n.priority,
            "related_id": n.related_id,
            "read": n.read,
            "timestamp": n.timestamp.isoformat()
        } for n in notifications
    ]

def mark_notification_read(db: Session, notification_id: int, user_id: int):
    """Marca notificação como lida"""
    notification = db.query(models.Notification).filter(
        and_(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id
        )
    ).first()
    
    if not notification:
        return False
    
    notification.read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    
    return True

def mark_all_notifications_read(db: Session, user_id: int):
    """Marca todas as notificações do usuário como lidas"""
    db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == user_id,
            models.Notification.read == False
        )
    ).update({
        models.Notification.read: True,
        models.Notification.read_at: datetime.utcnow()
    })
    
    db.commit()
    return True

def get_unread_notification_count(db: Session, user_id: int):
    """Obtém contagem de notificações não lidas"""
    return db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == user_id,
            models.Notification.read == False
        )
    ).count()