"""
Backup Agent para Windows
- Serviço Windows via NSSM
- Comunicação com servidor central via API REST
- Monitoramento de sistema
- Relatórios de backup
- Heartbeat automático
- Agendamento de tarefas
- Logging robusto
"""
import os
import sys
import json
import time
import threading
import logging
import requests
import socket
import psutil
import win32serviceutil
import win32service
import win32event
import win32evtlogutil
import servicemanager
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Configurações padrão
DEFAULT_CONFIG = {
    "server_url": "http://localhost:9200/api/agents",
    "agent_id": None,
    "heartbeat_interval": 300,  # 5 minutos
    "data_dir": "C:\\ProgramData\\BackupAgent",
    "logging": {
        "level": "INFO",
        "file": "C:\\ProgramData\\BackupAgent\\logs\\agent.log",
        "max_size_mb": 10,
        "backup_count": 5
    },
    "security": {
        "server_url_whitelist": ["http://localhost", "https://servidor-central.exemplo.com"]
    },
    "system_info": {
        "collect_interval": 3600  # 1 hora
    }
}

class BackupAgentService(win32serviceutil.ServiceFramework):
    """Serviço Windows para o Backup Agent"""
    _svc_name_ = "BackupAgent"
    _svc_display_name_ = "Backup Agent Service"
    _svc_description_ = "Serviço de monitoramento e backup para sistemas Windows"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.agent = None
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        """Parar o serviço"""
        self.running = False
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        if self.agent:
            self.agent.shutdown()

    def SvcDoRun(self):
        """Executar o serviço"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.running = True
        self.main()

    def main(self):
        """Método principal do serviço"""
        try:
            # Configurar logging antes de tudo
            self.setup_logging()
            
            # Criar diretórios necessários
            self.create_directories()
            
            # Inicializar o agente
            self.agent = BackupAgent()
            self.agent.start()
            
            # Esperar até que o serviço seja parado
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            logging.error(f"Erro no serviço principal: {e}")
            servicemanager.LogErrorMsg(str(e))
        finally:
            if self.agent:
                self.agent.shutdown()

    def setup_logging(self):
        """Configurar logging para o serviço"""
        log_dir = Path(DEFAULT_CONFIG["logging"]["file"]).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=DEFAULT_CONFIG["logging"]["level"],
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(DEFAULT_CONFIG["logging"]["file"]),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def create_directories(self):
        """Criar diretórios necessários para o agente"""
        Path(DEFAULT_CONFIG["data_dir"]).mkdir(parents=True, exist_ok=True)
        Path(DEFAULT_CONFIG["logging"]["file"]).parent.mkdir(parents=True, exist_ok=True)

class BackupAgent:
    """Classe principal do agente de backup"""
    
    def __init__(self):
        self.config = self.load_config()
        self.scheduler = BackgroundScheduler()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BackupAgent/1.0"})
        self.logger = logging.getLogger("BackupAgent")
        
    def load_config(self):
        """Carregar configuração do arquivo ou usar padrão"""
        config_path = Path(DEFAULT_CONFIG["data_dir"]) / "agent_config.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                self.logger.info("Configuração carregada com sucesso")
                return config
            except Exception as e:
                self.logger.error(f"Erro ao carregar configuração: {e}. Usando configuração padrão.")
        
        # Retornar configuração padrão se não existir ou houver erro
        self.logger.info("Usando configuração padrão")
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Salvar configuração atualizada"""
        config_path = Path(DEFAULT_CONFIG["data_dir"]) / "agent_config.json"
        
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info("Configuração salva com sucesso")
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração: {e}")
    
    def get_system_info(self):
        """Coletar informações detalhadas do sistema"""
        try:
            return {
                "hostname": socket.gethostname(),
                "ip_address": self.get_local_ip(),
                "os": f"{platform.system()} {platform.release()}",
                "architecture": platform.machine(),
                "cpu_count": psutil.cpu_count(),
                "total_memory_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
                "disk_usage": {
                    partition.device: {
                        "total_gb": round(partition.total / (1024 ** 3), 2),
                        "used_gb": round(partition.used / (1024 ** 3), 2),
                        "percent": partition.percent
                    } for partition in psutil.disk_partitions()
                },
                "agent_version": "1.0.0",
                "agent_start_time": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Erro ao coletar informações do sistema: {e}")
            return {
                "hostname": socket.gethostname(),
                "ip_address": self.get_local_ip(),
                "os": platform.system(),
                "agent_version": "1.0.0"
            }
    
    def get_local_ip(self):
        """Obter IP local da máquina"""
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == 2:  # AF_INET
                        if not addr.address.startswith(('127.', '169.254.')):
                            return addr.address
            return '127.0.0.1'
        except Exception as e:
            self.logger.error(f"Erro ao obter IP local: {e}")
            return '127.0.0.1'
    
    def register_with_server(self):
        """Registrar este agente no servidor central"""
        if not self.config.get('server_url'):
            self.logger.warning("URL do servidor não configurada. Pulando registro.")
            return False
        
        try:
            # Verificar se a URL está na whitelist
            if not any(self.config['server_url'].startswith(allowed) for allowed in self.config['security']['server_url_whitelist']):
                self.logger.error(f"URL do servidor não autorizada: {self.config['server_url']}")
                return False
            
            agent_info = self.get_system_info()
            
            self.logger.info(f"Registrando no servidor: {self.config['server_url']}/register")
            self.logger.info(f"Dados do agente: {agent_info['hostname']}, {agent_info['os']}")
            
            response = self.session.post(
                f"{self.config['server_url']}/register",
                json=agent_info,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.config['agent_id'] = data.get('agent_id')
                self.save_config()
                self.logger.info(f"Registrado com sucesso no servidor central. Agent ID: {self.config['agent_id']}")
                return True
            else:
                self.logger.error(f"Falha no registro: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar no servidor: {e}")
            return False
    
    def send_heartbeat(self):
        """Enviar heartbeat para o servidor central"""
        if not self.config.get('agent_id') or not self.config.get('server_url'):
            # Tentar registrar novamente se não tiver agent_id
            self.logger.info("Agent ID não configurado. Tentando registrar novamente...")
            if not self.register_with_server():
                return False
        
        try:
            system_info = self.get_system_info()
            heartbeat_data = {
                'agent_id': self.config['agent_id'],
                'timestamp': datetime.utcnow().isoformat(),
                'system_info': system_info
            }
            
            response = self.session.post(
                f"{self.config['server_url']}/heartbeat/{self.config['agent_id']}",
                json=heartbeat_data,
                timeout=15
            )
            
            if response.status_code == 200:
                self.logger.debug("Heartbeat enviado com sucesso")
                return True
            else:
                self.logger.warning(f"Heartbeat falhou. Status: {response.status_code}")
                # Tentar registrar novamente se o heartbeat falhar
                if response.status_code == 404:
                    self.logger.info("Agente não encontrado no servidor. Tentando registrar novamente...")
                    return self.register_with_server()
                return False
                
        except Exception as e:
            self.logger.error(f"Erro no heartbeat: {e}")
            return False
    
    def collect_and_report_metrics(self):
        """Coletar métricas do sistema e reportar para o servidor"""
        if not self.config.get('agent_id') or not self.config.get('server_url'):
            return
        
        try:
            metrics = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_io': {
                    'read_bytes': psutil.disk_io_counters().read_bytes,
                    'write_bytes': psutil.disk_io_counters().write_bytes
                },
                'network_io': {
                    'bytes_sent': psutil.net_io_counters().bytes_sent,
                    'bytes_recv': psutil.net_io_counters().bytes_recv
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.session.post(
                f"{self.config['server_url']}/metrics/{self.config['agent_id']}",
                json=metrics,
                timeout=15
            )
            
            if response.status_code == 200:
                self.logger.debug("Métricas enviadas com sucesso")
            else:
                self.logger.warning(f"Falha ao enviar métricas: HTTP {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Erro ao coletar e reportar métricas: {e}")
    
    def start(self):
        """Iniciar o agente completo"""
        self.logger.info("Iniciando Backup Agent...")
        
        # Registrar no servidor central
        if not self.register_with_server():
            self.logger.warning("Falha inicial ao registrar no servidor. Continuando...")
        
        # Agendar heartbeat
        self.scheduler.add_job(
            func=self.send_heartbeat,
            trigger=IntervalTrigger(seconds=self.config['heartbeat_interval']),
            id='heartbeat_job',
            name='Agent Heartbeat',
            replace_existing=True
        )
        
        # Agendar coleta de métricas
        self.scheduler.add_job(
            func=self.collect_and_report_metrics,
            trigger=IntervalTrigger(seconds=self.config['system_info']['collect_interval']),
            id='metrics_job',
            name='System Metrics Collection',
            replace_existing=True
        )
        
        # Iniciar agendador
        self.scheduler.start()
        self.logger.info("Agendador iniciado com sucesso")
        self.logger.info(f"Intervalo de heartbeat: {self.config['heartbeat_interval']} segundos")
        self.logger.info(f"Intervalo de coleta de métricas: {self.config['system_info']['collect_interval']} segundos")
        
        # Enviar heartbeat inicial
        self.send_heartbeat()
        
    def shutdown(self):
        """Parar o agente graciosamente"""
        self.logger.info("Parando Backup Agent...")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.logger.info("Agente parado com sucesso")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Executar como console para debug
        print("Executando como console para debug...")
        agent = BackupAgent()
        agent.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.shutdown()
    else:
        # Executar como serviço Windows
        win32serviceutil.HandleCommandLine(BackupAgentService)