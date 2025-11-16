<#
.SYNOPSIS
    Instala o Backup Agent corrigido para funcionar com o servidor WSL2
.DESCRIPTION
    Script corrigido para instalar o agente de backup com suporte a caminhos Windows e contexto Flask
.PARAMETER ServerUrl
    URL do servidor central (ex: http://localhost:9200/api/agents)
.EXAMPLE
    .\install_agent_fixed.ps1 -ServerUrl "http://localhost:9200/api/agents"
#>

param(
    [string]$ServerUrl = "http://localhost:9200/api/agents"
)

# Verificar permissões de administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Este script precisa ser executado como Administrador"
    exit 1
}

Write-Host "🚀 Iniciando instalação do Backup Agent corrigido..." -ForegroundColor Cyan

# Configurar variáveis
$installDir = "C:\Program Files\BackupAgent"
$configDir = "C:\ProgramData\BackupAgent"
$logDir = "$configDir\logs"
$repoDir = "$configDir\repositories"
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

# Criar diretórios necessários
Write-Host "📁 Criando diretórios..." -ForegroundColor Yellow
$null = New-Item -ItemType Directory -Path $installDir -Force
$null = New-Item -ItemType Directory -Path $configDir -Force
$null = New-Item -ItemType Directory -Path $logDir -Force
$null = New-Item -ItemType Directory -Path $repoDir -Force

Write-Host "✅ Diretórios criados com sucesso" -ForegroundColor Green

# Verificar se Python está instalado
Write-Host "🐍 Verificando instalação do Python..." -ForegroundColor Yellow
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    Write-Error "Python não encontrado. Por favor, instale Python 3.8 ou superior."
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Cyan
    exit 1
}

$pythonVersion = (python --version 2>&1).Split(' ')[1]
if ([version]$pythonVersion -lt [version]"3.8") {
    Write-Error "Versão do Python muito antiga. Requerido: 3.8 ou superior. Encontrado: $pythonVersion"
    exit 1
}

Write-Host "✅ Python $pythonVersion encontrado" -ForegroundColor Green

# Criar ambiente virtual
Write-Host "🏗️  Criando ambiente virtual Python..." -ForegroundColor Yellow
$venvDir = Join-Path $installDir "venv"
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$pipExe = Join-Path $venvDir "Scripts\pip.exe"

Write-Host "✅ Ambiente virtual criado em $venvDir" -ForegroundColor Green

# Instalar dependências Python
Write-Host "📦 Instalando dependências Python..." -ForegroundColor Yellow
$requirementsContent = @"
Flask==3.0.0
Flask-Cors==4.0.0
requests==2.31.0
APScheduler==3.10.4
psutil==5.9.6
pywin32==305
"@
$requirementsPath = Join-Path $installDir "requirements.txt"
$requirementsContent | Out-File -FilePath $requirementsPath -Encoding UTF8 -Force

try {
    & $pythonExe -m pip install --no-cache-dir -r $requirementsPath
    Write-Host "✅ Dependências Python instaladas com sucesso" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Falha ao instalar dependências: $_" -ForegroundColor Yellow
    exit 1
}

# Baixar e instalar NSSM
Write-Host "🔧 Baixando e instalando NSSM..." -ForegroundColor Yellow
$nssmZip = Join-Path $env:TEMP "nssm.zip"
$nssmTempDir = Join-Path $env:TEMP "nssm_temp"

try {
    # Limpar diretório temporário anterior
    if (Test-Path $nssmTempDir) {
        Remove-Item -Path $nssmTempDir -Recurse -Force
    }
    
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
    Expand-Archive -Path $nssmZip -DestinationPath $nssmTempDir -Force
    
    # Encontrar nssm.exe no conteúdo extraído
    $nssmExePath = Get-ChildItem -Path $nssmTempDir -Include "nssm.exe" -Recurse | Select-Object -First 1 -ExpandProperty FullName
    
    if (-not $nssmExePath -or -not (Test-Path $nssmExePath)) {
        Write-Error "NSSM.exe não encontrado após extração"
        exit 1
    }
    
    # Copiar nssm.exe para o diretório de instalação
    Copy-Item -Path $nssmExePath -Destination $installDir -Force
    $nssmExe = Join-Path $installDir "nssm.exe"
    
    # Limpar arquivos temporários
    Remove-Item -Path $nssmTempDir -Recurse -Force
    Remove-Item -Path $nssmZip -Force
    
    Write-Host "✅ NSSM instalado em $nssmExe" -ForegroundColor Green
} catch {
    Write-Error "Falha ao instalar NSSM: $_"
    exit 1
}

# Criar arquivo do agente com CORREÇÕES para Windows
Write-Host "🔧 Criando arquivo do agente corrigido..." -ForegroundColor Yellow
$agentContent = @"
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
import socket

from flask import Flask, jsonify, current_app
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import psutil

# Configurações padrão - USAR RAW STRINGS para caminhos Windows
DEFAULT_CONFIG = {
    "server_url": "$ServerUrl",
    "agent_id": None,
    "web_port": 8080,
    "data_dir": r"$configDir",
    "backup_jobs": [],
    "repositories": [
        {
            "id": 1,
            "name": "Repo_Local",
            "type": "filesystem",
            "path": r"$([System.IO.Path]::GetFullPath("$repoDir\local"))",
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
        "file": r"$([System.IO.Path]::GetFullPath("$logDir\agent.log"))",
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
        log_dir = Path(r"$([System.IO.Path]::GetFullPath("$logDir"))")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = getattr(logging, self.config.get("logging", {}).get("level", "INFO"), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(r"$([System.IO.Path]::GetFullPath("$logDir\agent.log"))"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("BackupAgent")
        
    def load_config(self):
        """Carregar configuração do arquivo ou usar padrão"""
        # USAR RAW STRING para o caminho do arquivo de configuração
        config_path = Path(r"$([System.IO.Path]::GetFullPath("$configDir\agent_config.json"))")
        
        if not config_path.exists():
            self.logger.info("Arquivo de configuração não encontrado. Criando configuração padrão...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salvar configuração padrão
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            self.config = DEFAULT_CONFIG.copy()
        else:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.logger.info("Configuração carregada com sucesso")
            except Exception as e:
                self.logger.error(f"Erro ao carregar configuração: {e}. Usando configuração padrão.")
                self.config = DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Salvar configuração atualizada"""
        # USAR RAW STRING para o caminho do arquivo de configuração
        config_path = Path(r"$([System.IO.Path]::GetFullPath("$configDir\agent_config.json"))")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
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
                timeout=15
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
                        if not addr.address.startswith(('127.', '169.254.')):
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
                        timeout=10
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
            # USAR CONTEXTO DE APLICAÇÃO CORRIGIDO
            with self.app.app_context():
                self.logger.info("Contexto de aplicação criado com sucesso")
                registration_result = self.register_with_server()
            self.logger.info(f"Resultado do registro: {registration_result}")
            
            # Iniciar servidor web
            self.logger.info("Iniciando servidor web Flask...")
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
"@

$agentPath = Join-Path $installDir "agent.py"
$agentContent | Out-File -FilePath $agentPath -Encoding UTF8 -Force
Write-Host "✅ Arquivo do agente criado com escapes corrigidos em $agentPath" -ForegroundColor Green

# Criar configuração padrão
Write-Host "⚙️  Criando configuração padrão..." -ForegroundColor Yellow
$defaultConfig = @{
    server_url = $ServerUrl
    agent_id = $null
    web_port = 8080
    data_dir = $configDir
    backup_jobs = @()
    repositories = @(
        @{
            id = 1
            name = "Repo_Local"
            type = "filesystem"
            path = "$repoDir\local"
            password = "CHANGE_ME_SECURE_PASSWORD"
            retention = @{
                daily = 7
                weekly = 4
                monthly = 12
            }
        }
    )
    logging = @{
        level = "INFO"
        file = "$logDir\agent.log"
        max_size_mb = 10
        backup_count = 5
    }
    security = @{
        web_local_only = $true
        require_auth = $false
        admin_password = ""
        allowed_ips = @("127.0.0.1", "::1")
    }
    binaries = @{
        kopia = ""
        restic = ""
    }
} | ConvertTo-Json -Depth 10

$configPath = "$configDir\agent_config.json"
$defaultConfig | Out-File -FilePath $configPath -Encoding UTF8 -Force
Write-Host "✅ Arquivo de configuração padrão criado em $configPath" -ForegroundColor Green

# Configurar permissões
Write-Host "🔒 Configurando permissões para o serviço..." -ForegroundColor Yellow
try {
    $acl = Get-Acl $configDir
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Users", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    $acl.SetAccessRule($rule)
    Set-Acl $configDir $acl
    
    $acl = Get-Acl $logDir
    $acl.SetAccessRule($rule)
    Set-Acl $logDir $acl
    
    Write-Host "✅ Permissões configuradas para Users" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Não foi possível configurar permissões detalhadas: $_" -ForegroundColor Yellow
    Write-Host "💡 O serviço pode precisar de permissões manuais para acessar os diretórios" -ForegroundColor Cyan
}

# Criar serviço com NSSM
Write-Host "🛠️  Criando serviço com NSSM..." -ForegroundColor Yellow
$serviceName = "BackupAgent"
$serviceDisplayName = "Backup Agent Service"
$serviceDescription = "Serviço de backup com interface web local"

# Parar e remover serviço existente
if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "🔄 Parando e removendo serviço existente..." -ForegroundColor Yellow
    Stop-Service $serviceName -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $nssmExe -ArgumentList @("remove", $serviceName, "confirm") -Wait -NoNewWindow
}

# Instalar novo serviço
try {
    # Instalar serviço
    Start-Process -FilePath $nssmExe -ArgumentList @("install", $serviceName, "$installDir\nssm_wrapper.cmd") -Wait -NoNewWindow
    
    # Criar wrapper atualizado
    $wrapperContent = @"
@echo off
set VIRTUAL_ENV=$venvDir
set PATH=%VIRTUAL_ENV%\Scripts;%PATH%
cd /d "$installDir"
"$pythonExe" agent.py
exit /b %errorlevel%
"@
    $wrapperPath = Join-Path $installDir "nssm_wrapper.cmd"
    $wrapperContent | Out-File -FilePath $wrapperPath -Encoding OEM -Force
    
    # Configurar serviço
    $configCommands = @(
        @("set", $serviceName, "DisplayName", $serviceDisplayName),
        @("set", $serviceName, "Description", $serviceDescription),
        @("set", $serviceName, "AppDirectory", $installDir),
        @("set", $serviceName, "AppStdout", (Join-Path $logDir "stdout.log")),
        @("set", $serviceName, "AppStderr", (Join-Path $logDir "stderr.log")),
        @("set", $serviceName, "AppRotateFiles", "1"),
        @("set", $serviceName, "AppRotateBytes", "10485760"),
        @("set", $serviceName, "Start", "SERVICE_AUTO_START"),
        @("set", $serviceName, "AppExit", "Default", "Restart"),
        @("set", $serviceName, "AppRestartDelay", "60000"),
        @("set", $serviceName, "AppNoConsole", "1")
    )
    
    foreach ($cmd in $configCommands) {
        Start-Process -FilePath $nssmExe -ArgumentList $cmd -Wait -NoNewWindow
    }
    
    Write-Host "✅ Serviço '$serviceName' instalado com sucesso!" -ForegroundColor Green
    
    # Iniciar serviço
    Write-Host "🔄 Iniciando serviço..." -ForegroundColor Yellow
    Start-Service $serviceName
    Start-Sleep -Seconds 5
    
    $service = Get-Service $serviceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Write-Host "✅ Serviço iniciado com sucesso! Status: $($service.Status)" -ForegroundColor Green
        Write-Host "`n🌐 Interface web disponível em: http://localhost:8080" -ForegroundColor Cyan
        Write-Host "📝 Logs do serviço: $logDir" -ForegroundColor Cyan
        
        # Testar comunicação com servidor central
        Write-Host "`n🔍 Testando comunicação com servidor central..." -ForegroundColor Yellow
        try {
            $testUrl = "$ServerUrl/register"
            $testResponse = Invoke-RestMethod -Uri $testUrl -Method Post -Body '{"hostname":"test-agent","ip_address":"127.0.0.1","os":"Windows"}' -ContentType "application/json" -TimeoutSec 10
            Write-Host "✅ Comunicação com servidor central estabelecida com sucesso!" -ForegroundColor Green
            Write-Host "✅ Resposta do servidor: $($testResponse | ConvertTo-Json)" -ForegroundColor Green
        } catch {
            Write-Host "⚠️  O serviço está rodando mas houve problema na comunicação com o servidor central: $_" -ForegroundColor Yellow
            Write-Host "💡 Verifique se o servidor central está acessível em $ServerUrl" -ForegroundColor Cyan
        }
    } else {
        Write-Host "❌ Serviço não está rodando. Verificando logs..." -ForegroundColor Red
        
        # Verificar logs de erro
        $stderrLog = Join-Path $logDir "stderr.log"
        if (Test-Path $stderrLog -and (Get-Item $stderrLog).Length -gt 0) {
            Write-Host "`n🔴 Últimas linhas do stderr.log:" -ForegroundColor Red
            Get-Content $stderrLog -Tail 20
        }
        
        # Tentar executar manualmente para debug
        Write-Host "`n🔍 Tentando executar o agente manualmente para debug..." -ForegroundColor Cyan
        Push-Location $installDir
        try {
            & $pythonExe agent.py
        } catch {
            Write-Host "❌ Erro ao executar agente manualmente: $_" -ForegroundColor Red
        } finally {
            Pop-Location
        }
    }
} catch {
    Write-Error "Falha ao criar serviço: $_"
    exit 1
}

Write-Host "`n🎉 Instalação concluída com sucesso!" -ForegroundColor Cyan
Write-Host "📋 Resumo da instalação:"
Write-Host "  • Diretório de instalação: $installDir"
Write-Host "  • Configuração: $configPath"
Write-Host "  • Interface web: http://localhost:8080"
Write-Host "  • Serviço Windows: $serviceName"
Write-Host "`n💡 Dicas:"
Write-Host "  • Para modificar configuração: edite $configPath e reinicie o serviço"
Write-Host "  • Para reiniciar o serviço: Restart-Service $serviceName -Force"
Write-Host "  • Logs detalhados: Get-Content '$logDir\agent.log' -Tail 50"
Write-Host "  • Status do serviço: Get-Service $serviceName"