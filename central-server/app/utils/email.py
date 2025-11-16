import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
import json
import os
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any, Optional
from datetime import datetime

# Configurações de email
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "backup-system@example.com")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Backup System")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"

# Templates directory
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates", "email")
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

def send_email(
    to: List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None
):
    """Envia email com ou sem conteúdo HTML"""
    if not EMAIL_ENABLED:
        print("📧 Email desabilitado nas configurações")
        return True
    
    try:
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = formataddr((str(Header(EMAIL_FROM_NAME, 'utf-8')), EMAIL_FROM))
        msg['To'] = ", ".join(to)
        
        # Adicionar partes do email
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Enviar email
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            if EMAIL_USE_TLS:
                server.starttls()
            
            if EMAIL_USER and EMAIL_PASSWORD:
                server.login(EMAIL_USER, EMAIL_PASSWORD)
            
            server.send_message(msg)
        
        print(f"📧 Email enviado para {', '.join(to)}")
        return True
    
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Renderiza template Jinja2"""
    try:
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        print(f"❌ Erro ao renderizar template {template_name}: {e}")
        # Retornar template fallback
        return f"Erro ao renderizar template: {str(e)}"

def send_notification_email(
    to: List[str],
    subject: str,
    template: str,
    context: Dict[str, Any]
):
    """Envia email de notificação usando template"""
    if not EMAIL_ENABLED:
        return
    
    # Adicionar contexto padrão
    context.update({
        "current_year": datetime.utcnow().year,
        "system_name": "Backup Central System",
        "contact_email": EMAIL_FROM
    })
    
    # Renderizar templates
    html_content = render_template(f"{template}", context)
    text_content = render_template(f"{template.replace('.html', '.txt')}", context)
    
    # Enviar email
    send_email(
        to=to,
        subject=subject,
        body=text_content,
        html_body=html_content
    )

def send_backup_failure_alert(
    to: List[str],
    agent_hostname: str,
    backup_source: str,
    error_message: str,
    job_id: str
):
    """Envia alerta de falha de backup"""
    context = {
        "agent_hostname": agent_hostname,
        "backup_source": backup_source,
        "error_message": error_message,
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    send_notification_email(
        to=to,
        subject=f"🚨 Backup Falhou: {agent_hostname} - {backup_source}",
        template="backup_failed.html",
        context=context
    )

def send_agent_offline_alert(
    to: List[str],
    agent_hostname: str,
    last_seen: str,
    agent_id: str
):
    """Envia alerta de agente offline"""
    context = {
        "agent_hostname": agent_hostname,
        "last_seen": last_seen,
        "agent_id": agent_id,
        "offline_duration": calculate_offline_duration(last_seen)
    }
    
    send_notification_email(
        to=to,
        subject=f"🚨 Agente Offline: {agent_hostname}",
        template="agent_offline.html",
        context=context
    )

def send_storage_warning(
    to: List[str],
    usage_percent: float,
    used_gb: float,
    total_gb: float,
    free_gb: float
):
    """Envia alerta de storage quase cheio"""
    context = {
        "usage_percent": usage_percent,
        "used_gb": used_gb,
        "total_gb": total_gb,
        "free_gb": free_gb,
        "warning_level": "CRÍTICO" if usage_percent > 90 else "ALTO"
    }
    
    send_notification_email(
        to=to,
        subject=f"⚠️ Storage Quase Cheio: {usage_percent:.1f}%", 
        template="storage_warning.html",
        context=context
    )

def calculate_offline_duration(last_seen_str: str) -> str:
    """Calcula duração offline em formato amigável"""
    try:
        last_seen = datetime.fromisoformat(last_seen_str)
        duration = datetime.utcnow() - last_seen
        
        if duration.total_seconds() < 60:
            return f"{int(duration.total_seconds())} segundos"
        elif duration.total_seconds() < 3600:
            return f"{int(duration.total_seconds() // 60)} minutos"
        elif duration.total_seconds() < 86400:
            return f"{int(duration.total_seconds() // 3600)} horas"
        else:
            return f"{int(duration.total_seconds() // 86400)} dias"
    except:
        return "desconhecido"