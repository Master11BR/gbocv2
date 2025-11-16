"""
Serviço de gerenciamento de agentes
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app import models, schemas
from app.config import settings
from app.utils import helpers

logger = logging.getLogger(__name__)


def get_agent(db: Session, agent_id: str) -> Optional[models.Agent]:
    """Obtém agente por ID"""
    return db.query(models.Agent).filter(
        models.Agent.agent_id == agent_id
    ).first()


def get_agent_by_hostname(db: Session, hostname: str) -> Optional[models.Agent]:
    """Obtém agente por hostname"""
    return db.query(models.Agent).filter(
        models.Agent.hostname == hostname
    ).first()


def get_agents(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    enabled: Optional[bool] = None
) -> List[models.Agent]:
    """Lista agentes com paginação"""
    query = db.query(models.Agent)
    
    if enabled is not None:
        query = query.filter(models.Agent.enabled == enabled)
    
    return query.offset(skip).limit(limit).all()


def create_agent(db: Session, agent_info: dict) -> models.Agent:
    """Cria novo agente"""
    try:
        # Verificar se já existe
        existing = get_agent_by_hostname(db, agent_info["hostname"])
        if existing:
            # Atualizar existente
            existing.ip_address = agent_info.get("ip_address", existing.ip_address)
            existing.os = agent_info.get("os", existing.os)
            existing.last_seen = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            logger.info(f"Agente atualizado: {existing.hostname}")
            return existing
        
        # Criar novo
        agent = models.Agent(
            hostname=agent_info["hostname"],
            ip_address=agent_info.get("ip_address", ""),
            os=agent_info.get("os", ""),
            agent_id=str(uuid4()),
            last_seen=datetime.utcnow(),
            enabled=True
        )
        
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Criar configuração padrão
        create_default_config(db, agent.agent_id)
        
        logger.info(f"Novo agente criado: {agent.hostname} ({agent.agent_id})")
        return agent
        
    except Exception as e:
        logger.error(f"Erro ao criar agente: {e}", exc_info=True)
        db.rollback()
        raise


def create_default_config(db: Session, agent_id: str):
    """Cria configuração padrão para agente"""
    default_config = {
        "server_url": f"http://{settings.host}:9200/api/agents",
        "heartbeat_interval": 60,
        "backup_jobs": [],
        "repositories": [],
        "logging": {
            "level": "INFO",
            "file": f"/var/log/backup_agent_{agent_id}.log"
        },
        "security": {
            "web_local_only": True,
            "require_auth": False
        }
    }
    
    config = models.AgentConfig(
        agent_id=agent_id,
        config=json.dumps(default_config)
    )
    
    db.add(config)
    db.commit()
    logger.info(f"Configuração padrão criada para agente: {agent_id}")


def update_agent(db: Session, agent_id: str, agent_update: dict) -> Optional[models.Agent]:
    """Atualiza agente"""
    try:
        agent = get_agent(db, agent_id)
        if not agent:
            return None
        
        # Atualizar campos
        agent.enabled = agent_update.get("enabled", agent.enabled)
        agent.updated_at = datetime.utcnow()
        
        # Atualizar configuração se fornecida
        if "config" in agent_update and agent_update["config"]:
            update_agent_config(db, agent_id, agent_update["config"])
        
        db.commit()
        db.refresh(agent)
        
        logger.info(f"Agente atualizado: {agent_id}")
        return agent
        
    except Exception as e:
        logger.error(f"Erro ao atualizar agente {agent_id}: {e}", exc_info=True)
        db.rollback()
        raise


def update_agent_config(db: Session, agent_id: str, config: dict):
    """Atualiza configuração do agente"""
    try:
        agent_config = db.query(models.AgentConfig).filter(
            models.AgentConfig.agent_id == agent_id
        ).first()
        
        if not agent_config:
            agent_config = models.AgentConfig(agent_id=agent_id)
            db.add(agent_config)
        
        agent_config.config = json.dumps(config)
        agent_config.updated_at = datetime.utcnow()
        
        # Atualizar hash no agente
        agent = get_agent(db, agent_id)
        if agent:
            agent.config_hash = helpers.generate_config_hash(config)
        
        db.commit()
        logger.info(f"Configuração atualizada para agente: {agent_id}")
        
    except Exception as e:
        logger.error(f"Erro ao atualizar config do agente {agent_id}: {e}", exc_info=True)
        db.rollback()
        raise


def update_agent_heartbeat(db: Session, agent_id: str) -> bool:
    """Atualiza heartbeat do agente"""
    try:
        agent = get_agent(db, agent_id)
        if not agent:
            return False
        
        agent.last_seen = datetime.utcnow()
        db.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar heartbeat {agent_id}: {e}")
        db.rollback()
        return False


def get_agent_config(db: Session, agent_id: str) -> Optional[dict]:
    """Obtém configuração do agente"""
    try:
        agent = get_agent(db, agent_id)
        if not agent:
            return None
        
        config = db.query(models.AgentConfig).filter(
            models.AgentConfig.agent_id == agent_id
        ).first()
        
        if not config:
            return {"config": {}, "config_hash": ""}
        
        return {
            "config": json.loads(config.config),
            "config_hash": agent.config_hash
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter config do agente {agent_id}: {e}")
        return None


def report_backup(db: Session, agent_id: str, report: dict) -> models.BackupJob:
    """Registra relatório de backup"""
    try:
        job = models.BackupJob(
            agent_id=agent_id,
            start_time=datetime.fromisoformat(report["start_time"]),
            end_time=datetime.fromisoformat(report["end_time"]) if report.get("end_time") else None,
            status=report["status"],
            tool=report["tool"],
            source=report["source"],
            destination=report["destination"],
            size_bytes=report.get("size_bytes", 0),
            logs=report.get("logs", ""),
            error_message=report.get("error_message")
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(f"Backup registrado: {job.id} do agente {agent_id} - Status: {job.status}")
        return job
        
    except Exception as e:
        logger.error(f"Erro ao registrar backup do agente {agent_id}: {e}", exc_info=True)
        db.rollback()
        raise


def get_agent_stats(db: Session, agent_id: str) -> Optional[dict]:
    """Obtém estatísticas do agente"""
    try:
        agent = get_agent(db, agent_id)
        if not agent:
            return None
        
        # Total de backups
        total_backups = db.query(models.BackupJob).filter(
            models.BackupJob.agent_id == agent_id
        ).count()
        
        # Backups com sucesso
        success_backups = db.query(models.BackupJob).filter(
            and_(
                models.BackupJob.agent_id == agent_id,
                models.BackupJob.status == "success"
            )
        ).count()
        
        # Backups falhados
        failed_backups = db.query(models.BackupJob).filter(
            and_(
                models.BackupJob.agent_id == agent_id,
                models.BackupJob.status == "failed"
            )
        ).count()
        
        # Último backup
        last_backup = db.query(models.BackupJob).filter(
            models.BackupJob.agent_id == agent_id
        ).order_by(models.BackupJob.start_time.desc()).first()
        
        # Status online/offline
        threshold = datetime.utcnow() - timedelta(minutes=settings.agent_heartbeat_timeout_minutes)
        status = "online" if agent.last_seen > threshold else "offline"
        
        return {
            "agent_id": agent_id,
            "hostname": agent.hostname,
            "total_backups": total_backups,
            "success_backups": success_backups,
            "failed_backups": failed_backups,
            "success_rate": round((success_backups / total_backups * 100) if total_backups > 0 else 0, 2),
            "last_backup": last_backup.start_time.isoformat() if last_backup else None,
            "status": status,
            "last_seen": agent.last_seen.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter stats do agente {agent_id}: {e}", exc_info=True)
        return None


def get_agent_performance(db: Session, agent_id: str, days: int = 7) -> dict:
    """Obtém métricas de performance do agente"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        backups = db.query(models.BackupJob).filter(
            and_(
                models.BackupJob.agent_id == agent_id,
                models.BackupJob.start_time >= start_date
            )
        ).order_by(models.BackupJob.start_time).all()
        
        if not backups:
            return {
                "daily_backups": [],
                "success_rate": 0,
                "avg_duration": 0,
                "total_size_gb": 0,
                "total_backups": 0
            }
        
        # Agrupar por dia
        daily_stats = {}
        for backup in backups:
            day = backup.start_time.date().isoformat()
            if day not in daily_stats:
                daily_stats[day] = {
                    "success": 0,
                    "failed": 0,
                    "total": 0,
                    "duration": 0,
                    "size": 0
                }
            
            daily_stats[day]["total"] += 1
            
            if backup.end_time:
                duration = (backup.end_time - backup.start_time).total_seconds()
                daily_stats[day]["duration"] += duration
            
            daily_stats[day]["size"] += backup.size_bytes
            
            if backup.status == "success":
                daily_stats[day]["success"] += 1
            elif backup.status == "failed":
                daily_stats[day]["failed"] += 1
        
        # Calcular métricas
        success_count = sum(stats["success"] for stats in daily_stats.values())
        total_count = sum(stats["total"] for stats in daily_stats.values())
        total_duration = sum(stats["duration"] for stats in daily_stats.values())
        total_size = sum(stats["size"] for stats in daily_stats.values())
        
        return {
            "daily_backups": [
                {"date": day, **stats} for day, stats in daily_stats.items()
            ],
            "success_rate": round((success_count / total_count * 100) if total_count > 0 else 0, 2),
            "avg_duration": round((total_duration / total_count) if total_count > 0 else 0, 2),
            "total_size_gb": round(total_size / (1024 ** 3), 2),
            "total_backups": total_count
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter performance do agente {agent_id}: {e}", exc_info=True)
        return {
            "daily_backups": [],
            "success_rate": 0,
            "avg_duration": 0,
            "total_size_gb": 0,
            "total_backups": 0
        }