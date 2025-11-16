import json
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .. import models, schemas
from ..services import agents, backup, stats
from ..utils import helpers

def generate_backup_report(db: Session, agent_id: Optional[str] = None, days: int = 7):
    """Gera relatório detalhado de backups"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(models.BackupJob).filter(
        models.BackupJob.start_time >= start_date
    )
    
    if agent_id:
        query = query.filter(models.BackupJob.agent_id == agent_id)
    
    backups = query.order_by(models.BackupJob.start_time.desc()).all()
    
    if not backups:
        return None
    
    # Calcular estatísticas gerais
    total_backups = len(backups)
    success_backups = sum(1 for b in backups if b.status == "success")
    failed_backups = sum(1 for b in backups if b.status == "failed")
    running_backups = sum(1 for b in backups if b.status == "running")
    
    success_rate = round((success_backups / total_backups * 100) if total_backups > 0 else 0, 2)
    
    # Calcular tamanho total e média
    total_size_bytes = sum(b.size_bytes for b in backups if b.size_bytes)
    avg_size_bytes = total_size_bytes / total_backups if total_backups > 0 else 0
    
    # Calcular tempo médio de execução
    durations = []
    for b in backups:
        if b.end_time and b.start_time:
            duration = (b.end_time - b.start_time).total_seconds()
            durations.append(duration)
    
    avg_duration = round(sum(durations) / len(durations) if durations else 0, 2)
    
    # Agrupar por ferramenta
    tool_stats = {}
    for backup in backups:
        tool = backup.tool
        if tool not in tool_stats:
            tool_stats[tool] = {"count": 0, "success": 0, "failed": 0, "size": 0}
        
        tool_stats[tool]["count"] += 1
        if backup.status == "success":
            tool_stats[tool]["success"] += 1
            tool_stats[tool]["size"] += backup.size_bytes
        elif backup.status == "failed":
            tool_stats[tool]["failed"] += 1
    
    # Top 5 origens por tamanho
    source_stats = {}
    for backup in backups:
        if backup.status == "success" and backup.size_bytes > 0:
            source = backup.source
            if source not in source_stats:
                source_stats[source] = {"count": 0, "total_size": 0}
            source_stats[source]["count"] += 1
            source_stats[source]["total_size"] += backup.size_bytes
    
    top_sources = sorted(source_stats.items(), key=lambda x: x[1]["total_size"], reverse=True)[:5]
    
    # Preparar dados do relatório
    report = {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}",
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_backups": total_backups,
            "success_backups": success_backups,
            "failed_backups": failed_backups,
            "running_backups": running_backups,
            "success_rate": success_rate,
            "total_size_gb": round(total_size_bytes / (1024 ** 3), 2),
            "avg_size_gb": round(avg_size_bytes / (1024 ** 3), 2),
            "avg_duration_seconds": avg_duration
        },
        "tool_breakdown": tool_stats,
        "top_sources": [
            {
                "source": source,
                "backup_count": stats["count"],
                "total_size_gb": round(stats["total_size"] / (1024 ** 3), 2)
            } for source, stats in top_sources
        ],
        "detailed_backups": [
            {
                "id": b.id,
                "agent_id": b.agent_id,
                "status": b.status,
                "tool": b.tool,
                "source": b.source,
                "destination": b.destination,
                "size_gb": round(b.size_bytes / (1024 ** 3), 2) if b.size_bytes else 0,
                "start_time": b.start_time.isoformat(),
                "end_time": b.end_time.isoformat() if b.end_time else None,
                "duration_seconds": (b.end_time - b.start_time).total_seconds() if b.end_time and b.start_time else None
            } for b in backups[:50]  # Limitar a 50 backups detalhados
        ]
    }
    
    return report

def generate_agent_health_report(db: Session, days: int = 7):
    """Gera relatório de saúde dos agentes"""
    agents_list = agents.get_agents(db)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    report = {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}",
        "generated_at": datetime.utcnow().isoformat(),
        "total_agents": len(agents_list),
        "online_agents": 0,
        "offline_agents": 0,
        "agents": []
    }
    
    for agent in agents_list:
        agent_stats = agents.get_agent_stats(db, agent.agent_id)
        agent_performance = agents.get_agent_performance(db, agent.agent_id, days)
        
        # Verificar status online/offline
        is_online = agent.last_seen > datetime.utcnow() - timedelta(minutes=15)
        if is_online:
            report["online_agents"] += 1
        else:
            report["offline_agents"] += 1
        
        # Calcular tempo de uptime
        uptime_minutes = 0
        if is_online:
            uptime_minutes = (datetime.utcnow() - agent.last_seen).total_seconds() / 60
        
        # Identificar problemas comuns
        issues = []
        if agent_stats["failed_backups"] > agent_stats["total_backups"] * 0.3:  # Mais de 30% de falhas
            issues.append("high_failure_rate")
        
        if agent.last_seen < datetime.utcnow() - timedelta(hours=1):
            issues.append("not_reporting")
        
        if agent_performance["success_rate"] < 80:
            issues.append("low_success_rate")
        
        # Preparar dados do agente
        agent_data = {
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "ip_address": agent.ip_address,
            "os": agent.os,
            "status": "online" if is_online else "offline",
            "last_seen": agent.last_seen.isoformat(),
            "uptime_minutes": round(uptime_minutes, 2),
            "stats": agent_stats,
            "performance": agent_performance,
            "issues": issues,
            "health_score": calculate_health_score(agent, agent_stats, agent_performance, issues)
        }
        
        report["agents"].append(agent_data)
    
    return report

def calculate_health_score(agent, stats, performance, issues):
    """Calcula pontuação de saúde do agente (0-100)"""
    score = 100
    
    # Penalizar por problemas
    if "high_failure_rate" in issues:
        score -= 30
    if "not_reporting" in issues:
        score -= 40
    if "low_success_rate" in issues:
        score -= 20
    
    # Penalizar por baixa taxa de sucesso
    if performance["success_rate"] < 80:
        score -= (80 - performance["success_rate"]) * 0.5
    
    # Bonificar por uptime
    if agent.last_seen > datetime.utcnow() - timedelta(minutes=15):
        score += 10
    
    return max(0, min(100, score))

def export_report_to_csv(report: dict, report_type: str = "backup"):
    """Exporta relatório para CSV"""
    output = io.StringIO()
    
    if report_type == "backup":
        writer = csv.writer(output)
        writer.writerow([
            "Backup ID", "Agent ID", "Status", "Tool", "Source", 
            "Destination", "Size (GB)", "Start Time", "End Time", "Duration (s)"
        ])
        
        for backup in report["detailed_backups"]:
            writer.writerow([
                backup["id"],
                backup["agent_id"],
                backup["status"],
                backup["tool"],
                backup["source"],
                backup["destination"],
                backup["size_gb"],
                backup["start_time"],
                backup["end_time"] or "",
                backup["duration_seconds"] or ""
            ])
    
    elif report_type == "agent_health":
        writer = csv.writer(output)
        writer.writerow([
            "Agent ID", "Hostname", "Status", "Health Score", 
            "Success Rate (%)", "Total Backups", "Failed Backups", "Last Seen"
        ])
        
        for agent in report["agents"]:
            writer.writerow([
                agent["agent_id"],
                agent["hostname"],
                agent["status"],
                agent["health_score"],
                agent["performance"]["success_rate"],
                agent["stats"]["total_backups"],
                agent["stats"]["failed_backups"],
                agent["last_seen"]
            ])
    
    return output.getvalue()

def export_report_to_json(report: dict):
    """Exporta relatório para JSON formatado"""
    return json.dumps(report, indent=2, ensure_ascii=False)