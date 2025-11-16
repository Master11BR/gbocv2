import os
import sys
import json
import logging
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import platform
import requests

from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import psutil

# Configurações padrão
DEFAULT_CONFIG = {
    "server_url": "http://localhost:9200/api/agents",
    "agent_id": None,
    "web_port": 8080,
    "data_dir": r"C:\ProgramData\BackupAgent",  # Raw string para caminhos Windows
    "backup_jobs": [],
    "repositories": [
        {
            "id": 1,
            "name": "Repo_Local",
            "type": "filesystem",
            "path": r"C:\ProgramData\BackupAgent\repositories\local",
            "password": "default_password_change_me",
            "retention": {
                "daily": 7,
                "weekly": 4,
                "monthly": 12
            }
        }
    ],
    "logging": {
        "level": "INFO",
        "file": r"C:\ProgramData\BackupAgent\logs\agent.log",
        "max_size_mb": 10,
        "backup_count": 5
    },
    "security": {
        "web_local_only": True,
        "require_auth": False,
        "admin_password": "",
        "allowed_ips": ["127.0.0.1", "::1"]
    },
    "binaries": {
        "kopia": "",
        "restic": ""
    }
}

class BackupAgent:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        self.config = DEFAULT_CONFIG.copy()
        self.scheduler = BackgroundScheduler()
        self.setup_logging()
        self.setup_routes()
        self.load_config()
        
    def setup_logging(self):
        """Configurar logging para console e arquivo"""
        log_dir = Path(self.config["logging"]["file"]).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = getattr(logging, self.config.get("logging", {}).get("level", "INFO"), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config["logging"]["file"]),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("BackupAgent")
        
    def load_config(self):
        """Carregar configuração do arquivo ou usar padrão"""
        config_path = Path(r"C:\ProgramData\BackupAgent\agent_config.json")  # Raw string
        
        if not config_path.exists():
            self.logger.info("Arquivo de configuração não encontrado. Criando configuração padrão...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salvar configuração padrão
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            self.config = DEFAULT_CONFIG.copy()
        else:
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
                self.logger.info("Configuração carregada com sucesso")
            except Exception as e:
                self.logger.error(f"Erro ao carregar configuração: {e}. Usando configuração padrão.")
                self.config = DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Salvar configuração atualizada"""
        config_path = Path(r"C:\ProgramData\BackupAgent\agent_config.json")  # Raw string
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        self.logger.info("Configuração salva com sucesso")
    
    def setup_routes(self):
        """Configurar rotas do Flask"""
        @self.app.route('/')
        def dashboard():
            return "Backup Agent está funcionando!"
        
        @self.app.route('/api/status')
        def api_status():
            return jsonify({
                'status': 'running',
                'agent_id': self.config.get('agent_id'),
                'hostname': platform.node(),
                'os': platform.system(),
                'version': '1.0.0'
            })
        
        @self.app.route('/api/register', methods=['POST'])
        def api_register():
            return self.register_with_server()
        
        @self.app.route('/api/config')
        def api_config():
            return jsonify(self.config)
    
    def register_with_server(self):
        """Registrar este agente no servidor central"""
        if not self.config.get('server_url'):
            self.logger.warning("URL do servidor não configurada. Pulando registro.")
            return jsonify({'error': 'URL do servidor não configurada'}), 400
        
        try:
            agent_info = {
                'hostname': platform.node(),
                'ip_address': self.get_local_ip(),
                'os': f"{platform.system()} {platform.release()}",
                'agent_version': '1.0.0'
            }
            
            self.logger.info(f"Registrando no servidor: {self.config['server_url']}/register")
            self.logger.info(f"Dados do agente: {agent_info}")
            
            response = requests.post(
                f"{self.config['server_url']}/register",
                json=agent_info,
                timeout=10
            )
            
            self.logger.info(f"Resposta do servidor: Status {response.status_code}")
            self.logger.info(f"Conteúdo da resposta: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                self.config['agent_id'] = data.get('agent_id')
                self.save_config()
                self.logger.info(f"Registrado com sucesso no servidor central. Agent ID: {self.config['agent_id']}")
                return jsonify(data)
            else:
                self.logger.error(f"Falha no registro: HTTP {response.status_code} - {response.text}")
                return jsonify({'error': f"Falha no registro: HTTP {response.status_code} - {response.text}"}), response.status_code
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar no servidor: {e}")
            return jsonify({'error': str(e)}), 500
    
    def get_local_ip(self) -> str:
        """Obter IP local da máquina"""
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == 2:  # AF_INET
                        if not addr.address.startswith('127.'):
                            return addr.address
            return '127.0.0.1'
        except Exception as e:
            self.logger.error(f"Erro ao obter IP local: {e}")
            return '127.0.0.1'
    
    def heartbeat(self):
        """Enviar heartbeat para o servidor central"""
        while True:
            try:
                if self.config.get('agent_id') and self.config.get('server_url'):
                    agent_id = self.config['agent_id']
                    server_url = self.config['server_url']
                    url = f"{server_url}/heartbeat/{agent_id}"
                    self.logger.debug(f"Enviando heartbeat para: {url}")
                    
                    response = requests.post(
                        url,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        self.logger.debug("Heartbeat enviado com sucesso")
                    else:
                        self.logger.warning(f"Heartbeat falhou. Status: {response.status_code}")
            except Exception as e:
                self.logger.debug(f"Erro no heartbeat: {e}")
            time.sleep(300)  # 5 minutos
    
    def start(self):
        """Iniciar o agente completo"""
        self.logger.info("Iniciando Backup Agent...")
        
        # Iniciar heartbeat em thread separada
        heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Iniciar agendador
        self.scheduler.start()
        self.logger.info("Agendador iniciado com sucesso")
        
        # Iniciar servidor web local
        host = '127.0.0.1' if self.config['security'].get('web_local_only', True) else '0.0.0.0'
        port = self.config.get('web_port', 8080)
        
        self.logger.info(f"Iniciando interface web local em http://{host}:{port}")
        self.logger.info(f"URL do servidor central: {self.config.get('server_url', 'não configurado')}")
        
        try:
            self.logger.info("Tentando registrar no servidor central...")
            # Adicionar contexto de aplicativo
            with self.app.app_context():
                registration_result = self.register_with_server()
            self.logger.info(f"Resultado do registro: {registration_result}")
            
            # Iniciar servidor web
            self.app.run(host=host, port=port, threaded=True, use_reloader=False)
        except Exception as e:
            self.logger.exception(f"Erro fatal: {e}")
            sys.exit(1)

if __name__ == '__main__':
    try:
        agent = BackupAgent()
        agent.start()
    except KeyboardInterrupt:
        print("\nAgente interrompido pelo usuário")
    except Exception as e:
        logging.exception(f"Erro fatal: {e}")
        sys.exit(1)