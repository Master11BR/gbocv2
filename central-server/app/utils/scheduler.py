from datetime import datetime
from typing import Callable, Dict, Any
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ..database import SessionLocal
from ..services import agents, backup, reports, events
from ..utils import notifications

class SystemScheduler:
    """Agendador de tarefas do sistema"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        self.running = False
    
    def start(self):
        """Inicia o agendador"""
        if self.running:
            return
        
        # Agendar tarefas do sistema
        self.schedule_system_tasks()
        
        self.scheduler.start()
        self.running = True
        print("✅ Agendador de tarefas iniciado")
    
    def shutdown(self):
        """Para o agendador"""
        if not self.running:
            return
        
        self.scheduler.shutdown()
        self.running = False
        print("⏹️ Agendador de tarefas parado")
    
    def schedule_system_tasks(self):
        """Agenda tarefas automáticas do sistema"""
        db = SessionLocal()
        
        try:
            # Limpeza de eventos antigos (diariamente às 2h)
            self.add_job(
                id="cleanup_events",
                func=cleanup_old_events,
                trigger=CronTrigger(hour=2, minute=0),
                args=[db]
            )
            
            # Geração de relatório diário (diariamente às 8h)
            self.add_job(
                id="daily_report",
                func=generate_daily_report,
                trigger=CronTrigger(hour=8, minute=0),
                args=[db]
            )
            
            # Verificação de agentes offline (a cada 15 minutos)
            self.add_job(
                id="check_offline_agents",
                func=check_offline_agents,
                trigger="interval",
                minutes=15,
                args=[db]
            )
            
            # Monitoramento de storage (a cada 30 minutos)
            self.add_job(
                id="monitor_storage",
                func=monitor_storage_usage,
                trigger="interval",
                minutes=30,
                args=[db]
            )
            
            # Limpeza de notificações antigas (semanalmente)
            self.add_job(
                id="cleanup_notifications",
                func=cleanup_old_notifications,
                trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
                args=[db]
            )
            
        finally:
            db.close()
    
    def add_job(self, id: str, func: Callable, trigger: Any, **kwargs):
        """Adiciona um job ao agendador"""
        if id in self.jobs:
            self.scheduler.remove_job(id)
        
        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=id,
            **kwargs
        )
        
        self.jobs[id] = job
        return job
    
    def remove_job(self, id: str):
        """Remove um job do agendador"""
        if id in self.jobs:
            self.scheduler.remove_job(id)
            del self.jobs[id]
    
    def get_job_status(self):
        """Obtém status de todos os jobs"""
        return {
            job_id: {
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            } for job_id, job in self.jobs.items()
        }

# Instância singleton do agendador
scheduler = SystemScheduler()

# Funções de tarefas do sistema
def cleanup_old_events(db):
    """Limpa eventos antigos do banco de dados"""
    from ..services.events import cleanup_old_events
    
    try:
        deleted_count = cleanup_old_events(db, days=90)
        if deleted_count > 0:
            print(f"🧹 Eventos antigos removidos: {deleted_count}")
    except Exception as e:
        print(f"❌ Erro ao limpar eventos antigos: {e}")

def generate_daily_report(db):
    """Gera relatório diário do sistema"""
    from ..services.reports import generate_backup_report, generate_agent_health_report, export_report_to_json
    
    try:
        # Gerar relatório de backups
        backup_report = generate_backup_report(db, days=1)
        if backup_report:
            report_json = export_report_to_json(backup_report)
            # Salvar relatório ou enviar por email
            print("📋 Relatório diário de backups gerado")
        
        # Gerar relatório de saúde dos agentes
        health_report = generate_agent_health_report(db, days=1)
        if health_report:
            print("📋 Relatório diário de saúde dos agentes gerado")
        
        # Enviar notificação de relatório gerado
        notifications.send_notification(
            db,
            title="Relatório Diário Gerado",
            message="Relatórios diários de backups e saúde dos agentes foram gerados com sucesso",
            category="system",
            priority="low"
        )
        
    except Exception as e:
        print(f"❌ Erro ao gerar relatório diário: {e}")
        # Enviar notificação de erro
        notifications.send_notification(
            db,
            title="Erro ao Gerar Relatório",
            message=f"Ocorreu um erro ao gerar os relatórios diários: {str(e)}",
            category="system",
            priority="high"
        )

def check_offline_agents(db):
    """Verifica agentes offline e envia notificações"""
    from ..services.agents import get_agents
    from datetime import timedelta
    
    try:
        offline_threshold = datetime.utcnow() - timedelta(minutes=15)
        offline_agents = []
        
        agents_list = get_agents(db)
        for agent in agents_list:
            if agent.last_seen < offline_threshold:
                offline_agents.append(agent)
        
        if offline_agents:
            print(f"⚠️ {len(offline_agents)} agentes offline detectados")
            
            for agent in offline_agents:
                # Criar evento de agente offline
                events.create_event(
                    db,
                    category="agent",
                    event_type="offline",
                    description=f"Agente {agent.hostname} está offline há mais de 15 minutos",
                    agent_id=agent.agent_id,
                    priority="high"
                )
                
                # Enviar notificação
                notifications.send_notification(
                    db,
                    title=f"Agente Offline: {agent.hostname}",
                    message=f"O agente {agent.hostname} não responde há mais de 15 minutos. Último heartbeat: {agent.last_seen.isoformat()}",
                    category="agent",
                    priority="high",
                    related_id=agent.agent_id
                )
        
    except Exception as e:
        print(f"❌ Erro ao verificar agentes offline: {e}")

def monitor_storage_usage(db):
    """Monitora uso de storage e envia alertas"""
    from ..services.stats import get_system_overview
    
    try:
        overview = get_system_overview(db)
        storage = overview["storage"]
        
        if storage["usage_percent"] > 90:
            print(f"🚨 ALERTA: Storage acima de 90% ({storage['usage_percent']}%)")
            
            # Criar evento de storage crítico
            events.create_event(
                db,
                category="system",
                event_type="warning",
                description=f"Uso de storage crítico: {storage['usage_percent']}%",
                priority="critical"
            )
            
            # Enviar notificação
            notifications.send_notification(
                db,
                title="ALERTA CRÍTICO: Storage Quase Cheio",
                message=f"O storage está {storage['usage_percent']}% cheio. Capacidade total: {storage['capacity_gb']}GB, Usado: {storage['used_gb']}GB, Livre: {storage['free_gb']}GB",
                category="system",
                priority="critical"
            )
        
        elif storage["usage_percent"] > 80:
            print(f"⚠️ Aviso: Storage acima de 80% ({storage['usage_percent']}%)")
            
            # Criar evento de storage alto
            events.create_event(
                db,
                category="system",
                event_type="warning",
                description=f"Uso de storage alto: {storage['usage_percent']}%",
                priority="high"
            )
            
            # Enviar notificação
            notifications.send_notification(
                db,
                title="Aviso: Storage Acima de 80%",
                message=f"O storage está {storage['usage_percent']}% cheio. Capacidade total: {storage['capacity_gb']}GB, Usado: {storage['used_gb']}GB, Livre: {storage['free_gb']}GB",
                category="system",
                priority="high"
            )
    
    except Exception as e:
        print(f"❌ Erro ao monitorar storage: {e}")

def cleanup_old_notifications(db):
    """Limpa notificações antigas do banco de dados"""
    from datetime import datetime, timedelta
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        deleted_count = db.query(models.Notification).filter(
            models.Notification.timestamp < cutoff_date
        ).delete()
        
        db.commit()
        
        if deleted_count > 0:
            print(f"🧹 Notificações antigas removidas: {deleted_count}")
    
    except Exception as e:
        print(f"❌ Erro ao limpar notificações antigas: {e}")