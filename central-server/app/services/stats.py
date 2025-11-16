from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from .. import models, schemas
from ..services import agents, backup

def get_system_overview(db: Session):
    """Obtém visão geral do sistema"""
    # Contagem de agentes
    total_agents = db.query(models.Agent).count()
    online_agents = db.query(models.Agent).filter(
        models.Agent.last_seen > datetime.utcnow() - timedelta(minutes=15)
    ).count()
    
    # Contagem de backups
    total_backups = db.query(models.BackupJob).count()
    success_backups = db.query(models.BackupJob).filter(
        models.BackupJob.status == "success"
    ).count()
    failed_backups = db.query(models.BackupJob).filter(
        models.BackupJob.status == "failed"
    ).count()
    running_backups = db.query(models.BackupJob).filter(
        models.BackupJob.status == "running"
    ).count()
    
    # Calcular taxa de sucesso
    success_rate = round((success_backups / total_backups * 100) if total_backups > 0 else 0, 2)
    
    # Calcular tamanho total de backups
    total_size_bytes = db.query(func.sum(models.BackupJob.size_bytes)).scalar() or 0
    total_size_gb = round(total_size_bytes / (1024 ** 3), 2)
    
    # Calcular crescimento diário (últimos 7 dias)
    last_week = datetime.utcnow() - timedelta(days=7)
    backups_last_week = db.query(models.BackupJob).filter(
        models.BackupJob.start_time >= last_week
    ).all()
    
    if backups_last_week:
        avg_daily_size = sum(b.size_bytes for b in backups_last_week) / 7
        daily_growth_gb = round(avg_daily_size / (1024 ** 3), 2)
    else:
        daily_growth_gb = 0
    
    # Calcular capacidade de storage (simulado)
    storage_capacity_gb = 1000  # 1TB
    used_storage_gb = total_size_gb
    free_storage_gb = storage_capacity_gb - used_storage_gb
    storage_usage_percent = round((used_storage_gb / storage_capacity_gb * 100), 2)
    
    return {
        "total_agents": total_agents,
        "online_agents": online_agents,
        "total_backups": total_backups,
        "success_rate": success_rate,
        "failed_backups": failed_backups,
        "running_backups": running_backups,
        "total_size_gb": total_size_gb,
        "daily_growth_gb": daily_growth_gb,
        "storage": {
            "capacity_gb": storage_capacity_gb,
            "used_gb": used_storage_gb,
            "free_gb": free_storage_gb,
            "usage_percent": storage_usage_percent
        }
    }

def get_backup_trends(db: Session, days: int = 30):
    """Obtém tendências de backups nos últimos dias"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Query para tendências diárias
    query = """
    SELECT 
        DATE(start_time) as date,
        COUNT(*) as total_backups,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_backups,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_backups,
        SUM(size_bytes) as total_size_bytes,
        AVG(strftime('%s', end_time) - strftime('%s', start_time)) as avg_duration
    FROM backup_jobs
    WHERE start_time >= :start_date
    GROUP BY DATE(start_time)
    ORDER BY date
    """
    
    result = db.execute(text(query), {"start_date": start_date}).fetchall()
    
    trends = []
    for row in result:
        trends.append({
            "date": row[0].isoformat(),
            "total_backups": row[1],
            "success_backups": row[2],
            "failed_backups": row[3],
            "total_size_gb": round((row[4] or 0) / (1024 ** 3), 2),
            "avg_duration_seconds": round(row[5] or 0, 2)
        })
    
    return trends

def get_agent_performance_comparison(db: Session):
    """Compara performance entre agentes"""
    agents_list = agents.get_agents(db)
    performance_data = []
    
    for agent in agents_list:
        agent_performance = agents.get_agent_performance(db, agent.agent_id, days=7)
        agent_stats = agents.get_agent_stats(db, agent.agent_id)
        
        performance_data.append({
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "success_rate": agent_performance["success_rate"],
            "avg_duration": agent_performance["avg_duration"],
            "total_size_gb": agent_performance["total_size_gb"],
            "total_backups": agent_performance["total_backups"],
            "health_score": agent_stats.get("health_score", 80)  # Default 80 se não existir
        })
    
    # Ordenar por taxa de sucesso e saúde
    performance_data.sort(key=lambda x: (x["success_rate"], x["health_score"]), reverse=True)
    
    return performance_data

def get_storage_usage_by_agent(db: Session):
    """Obtém uso de storage por agente"""
    query = """
    SELECT 
        agent_id,
        SUM(size_bytes) as total_size_bytes,
        COUNT(*) as backup_count,
        AVG(size_bytes) as avg_size_bytes
    FROM backup_jobs
    WHERE status = 'success' AND size_bytes > 0
    GROUP BY agent_id
    ORDER BY total_size_bytes DESC
    """
    
    result = db.execute(text(query)).fetchall()
    
    storage_usage = []
    for row in result:
        storage_usage.append({
            "agent_id": row[0],
            "total_size_gb": round((row[1] or 0) / (1024 ** 3), 2),
            "backup_count": row[2],
            "avg_size_gb": round((row[3] or 0) / (1024 ** 3), 2)
        })
    
    return storage_usage

def get_backup_success_rate_by_tool(db: Session, days: int = 30):
    """Obtém taxa de sucesso por ferramenta de backup"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = """
    SELECT 
        tool,
        COUNT(*) as total_backups,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_backups,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_backups
    FROM backup_jobs
    WHERE start_time >= :start_date
    GROUP BY tool
    """
    
    result = db.execute(text(query), {"start_date": start_date}).fetchall()
    
    tool_stats = []
    for row in result:
        total = row[1]
        success = row[2]
        failed = row[3]
        
        tool_stats.append({
            "tool": row[0],
            "total_backups": total,
            "success_backups": success,
            "failed_backups": failed,
            "success_rate": round((success / total * 100) if total > 0 else 0, 2)
        })
    
    return tool_stats

def get_top_backup_sources(db: Session, limit: int = 10):
    """Obtém as principais fontes de backup por tamanho"""
    query = """
    SELECT 
        source,
        COUNT(*) as backup_count,
        SUM(size_bytes) as total_size_bytes,
        AVG(size_bytes) as avg_size_bytes
    FROM backup_jobs
    WHERE status = 'success' AND size_bytes > 0
    GROUP BY source
    ORDER BY total_size_bytes DESC
    LIMIT :limit
    """
    
    result = db.execute(text(query), {"limit": limit}).fetchall()
    
    sources = []
    for row in result:
        sources.append({
            "source": row[0],
            "backup_count": row[1],
            "total_size_gb": round((row[2] or 0) / (1024 ** 3), 2),
            "avg_size_gb": round((row[3] or 0) / (1024 ** 3), 2)
        })
    
    return sources