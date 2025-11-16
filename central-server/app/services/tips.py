import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .. import models, schemas
from ..services import agents, backup, events, reports

TIPS_DATABASE = [
    {
        "id": "backup_slow_performance",
        "title": "Melhorar Performance de Backup Lento",
        "condition": {
            "category": "agent",
            "metrics": {
                "avg_duration_seconds": {"operator": ">", "value": 3600},  # Mais de 1 hora
                "success_rate": {"operator": "<", "value": 90}
            }
        },
        "solutions": [
            {
                "title": "Otimizar Exclusões",
                "description": "Configure padrões de exclusão para arquivos temporários, caches e downloads que não precisam ser backupados",
                "priority": "high"
            },
            {
                "title": "Ajustar Compressão",
                "description": "Reduza o nível de compressão ou desative para diretórios com arquivos já comprimidos (imagens, vídeos, zips)",
                "priority": "medium"
            },
            {
                "title": "Verificar Conexão de Rede",
                "description": "Teste a velocidade da conexão de rede entre o agente e o destino de backup",
                "priority": "medium"
            }
        ],
        "resources": [
            {
                "title": "Documentação de Otimização",
                "url": "https://backup-system.docs/optimization"
            }
        ]
    },
    {
        "id": "backup_high_failure_rate",
        "title": "Reduzir Taxa de Falhas nos Backups",
        "condition": {
            "category": "agent",
            "metrics": {
                "success_rate": {"operator": "<", "value": 80},
                "failed_backups": {"operator": ">", "value": 3}
            }
        },
        "solutions": [
            {
                "title": "Verificar Permissões de Acesso",
                "description": "Certifique-se de que o serviço do agente tem permissões de leitura em todas as pastas de origem",
                "priority": "critical"
            },
            {
                "title": "Aumentar Timeout",
                "description": "Aumente o tempo limite de execução para backups de grandes volumes de dados",
                "priority": "high"
            },
            {
                "title": "Verificar Espaço em Disco",
                "description": "Confira se há espaço suficiente tanto na origem quanto no destino do backup",
                "priority": "critical"
            }
        ],
        "resources": [
            {
                "title": "Guia de Solução de Problemas",
                "url": "https://backup-system.docs/troubleshooting"
            }
        ]
    },
    {
        "id": "agent_offline",
        "title": "Agente Offline por Longo Período",
        "condition": {
            "category": "agent",
            "metrics": {
                "status": {"operator": "==", "value": "offline"},
                "last_seen": {"operator": "<", "value": "1h"}  # Mais de 1 hora sem heartbeat
            }
        },
        "solutions": [
            {
                "title": "Verificar Serviço do Agente",
                "description": "Reinicie o serviço do agente backup no Windows",
                "priority": "critical"
            },
            {
                "title": "Verificar Conectividade de Rede",
                "description": "Confira se a máquina pode se comunicar com o servidor central",
                "priority": "high"
            },
            {
                "title": "Verificar Firewall",
                "description": "Certifique-se de que as portas 9200 (API) e 8080 (interface web) estão liberadas",
                "priority": "high"
            }
        ],
        "resources": [
            {
                "title": "Manual de Instalação do Agente",
                "url": "https://backup-system.docs/agent-installation"
            }
        ]
    },
    {
        "id": "storage_low_space",
        "title": "Espaço em Disco Insuficiente",
        "condition": {
            "category": "system",
            "metrics": {
                "storage_usage_percent": {"operator": ">", "value": 90}
            }
        },
        "solutions": [
            {
                "title": "Aumentar Capacidade de Storage",
                "description": "Adicione mais espaço de armazenamento ao servidor ou migre para storage externo",
                "priority": "critical"
            },
            {
                "title": "Limpar Backups Antigos",
                "description": "Configure políticas de retenção para remover backups antigos automaticamente",
                "priority": "high"
            },
            {
                "title": "Otimizar Deduplicação",
                "description": "Habilite ou ajuste configurações de deduplicação de dados para reduzir uso de espaço",
                "priority": "medium"
            }
        ],
        "resources": [
            {
                "title": "Configuração de Retenção",
                "url": "https://backup-system.docs/retention-policies"
            }
        ]
    }
]

def analyze_agent_health(db: Session, agent_id: str):
    """Analisa a saúde de um agente e retorna dicas personalizadas"""
    agent_stats = agents.get_agent_stats(db, agent_id)
    agent_performance = agents.get_agent_performance(db, agent_id, days=7)
    
    if not agent_stats or not agent_performance:
        return []
    
    # Preparar métricas para análise
    metrics = {
        "success_rate": agent_performance["success_rate"],
        "avg_duration_seconds": agent_performance["avg_duration"],
        "failed_backups": agent_stats["failed_backups"],
        "total_backups": agent_stats["total_backups"],
        "status": agent_stats["status"],
        "last_seen": agent_stats.get("last_seen", datetime.utcnow().isoformat())
    }
    
    # Calcular tempo offline se aplicável
    if metrics["status"] == "offline":
        last_seen = datetime.fromisoformat(metrics["last_seen"])
        offline_duration = datetime.utcnow() - last_seen
        metrics["offline_duration"] = offline_duration.total_seconds()
    
    # Analisar condições e gerar dicas
    applicable_tips = []
    
    for tip in TIPS_DATABASE:
        condition = tip["condition"]
        
        if condition["category"] != "agent":
            continue
        
        # Verificar métricas
        matches = True
        for metric_name, condition_value in condition["metrics"].items():
            if metric_name not in metrics:
                matches = False
                break
            
            metric_value = metrics[metric_name]
            
            # Tratar casos especiais
            if metric_name == "last_seen" and isinstance(condition_value["value"], str):
                # Converter duração para segundos
                duration_str = condition_value["value"]
                if duration_str.endswith("h"):
                    duration_seconds = float(duration_str[:-1]) * 3600
                elif duration_str.endswith("m"):
                    duration_seconds = float(duration_str[:-1]) * 60
                else:
                    duration_seconds = float(duration_str)
                
                last_seen = datetime.fromisoformat(metric_value)
                time_diff = datetime.utcnow() - last_seen
                actual_value = time_diff.total_seconds()
                
                if condition_value["operator"] == "<":
                    if actual_value >= duration_seconds:
                        matches = False
                elif condition_value["operator"] == ">":
                    if actual_value <= duration_seconds:
                        matches = False
            
            elif metric_name == "status":
                if condition_value["operator"] == "==" and metric_value != condition_value["value"]:
                    matches = False
                elif condition_value["operator"] == "!=" and metric_value == condition_value["value"]:
                    matches = False
            
            else:
                # Operadores numéricos
                if condition_value["operator"] == ">" and metric_value <= condition_value["value"]:
                    matches = False
                elif condition_value["operator"] == "<" and metric_value >= condition_value["value"]:
                    matches = False
                elif condition_value["operator"] == "==" and metric_value != condition_value["value"]:
                    matches = False
        
        if matches:
            applicable_tips.append({
                "id": tip["id"],
                "title": tip["title"],
                "description": "Soluções recomendadas para melhorar a performance do seu agente",
                "solutions": tip["solutions"],
                "resources": tip["resources"],
                "priority": max(sol["priority"] for sol in tip["solutions"]),
                "agent_id": agent_id
            })
    
    return applicable_tips

def analyze_system_health(db: Session):
    """Analisa a saúde do sistema e retorna dicas gerais"""
    system_overview = agents.get_system_overview(db)
    
    if not system_overview:
        return []
    
    metrics = {
        "storage_usage_percent": system_overview["storage"]["usage_percent"],
        "total_agents": system_overview["total_agents"],
        "online_agents": system_overview["online_agents"],
        "success_rate": system_overview["success_rate"]
    }
    
    applicable_tips = []
    
    for tip in TIPS_DATABASE:
        condition = tip["condition"]
        
        if condition["category"] != "system":
            continue
        
        # Verificar métricas do sistema
        matches = True
        for metric_name, condition_value in condition["metrics"].items():
            if metric_name not in metrics:
                matches = False
                break
            
            metric_value = metrics[metric_name]
            
            if condition_value["operator"] == ">" and metric_value <= condition_value["value"]:
                matches = False
            elif condition_value["operator"] == "<" and metric_value >= condition_value["value"]:
                matches = False
        
        if matches:
            applicable_tips.append({
                "id": tip["id"],
                "title": tip["title"],
                "description": "Soluções recomendadas para melhorar a saúde do sistema",
                "solutions": tip["solutions"],
                "resources": tip["resources"],
                "priority": max(sol["priority"] for sol in tip["solutions"]),
                "system_wide": True
            })
    
    return applicable_tips

def get_all_applicable_tips(db: Session):
    """Obtém todas as dicas aplicáveis para o sistema e agentes"""
    tips = []
    
    # Dicas para o sistema como um todo
    system_tips = analyze_system_health(db)
    tips.extend(system_tips)
    
    # Dicas para cada agente
    agents_list = agents.get_agents(db)
    for agent in agents_list:
        agent_tips = analyze_agent_health(db, agent.agent_id)
        tips.extend(agent_tips)
    
    # Remover duplicatas e ordenar por prioridade
    unique_tips = {}
    for tip in tips:
        tip_id = tip["id"] + (tip.get("agent_id", "") if tip.get("system_wide") else tip["agent_id"])
        unique_tips[tip_id] = tip
    
    sorted_tips = sorted(
        unique_tips.values(),
        key=lambda x: {"critical": 4, "high": 3, "medium": 2, "low": 1}[x["priority"]],
        reverse=True
    )
    
    return sorted_tips

def apply_tip_solution(db: Session, tip_id: str, solution_index: int, agent_id: Optional[str] = None):
    """Aplica uma solução recomendada e registra o evento"""
    from ..utils import notifications
    
    # Encontrar a dica
    applicable_tips = get_all_applicable_tips(db)
    tip = next((t for t in applicable_tips if t["id"] == tip_id and (not agent_id or t.get("agent_id") == agent_id)), None)
    
    if not tip:
        raise ValueError("Dica não encontrada ou não aplicável")
    
    if solution_index >= len(tip["solutions"]):
        raise ValueError("Índice de solução inválido")
    
    solution = tip["solutions"][solution_index]
    
    # Registrar evento de aplicação de solução
    events.create_event(
        db,
        category="system",
        event_type="config_update",
        description=f"Solução aplicada: {solution['title']} - {solution['description']}",
        agent_id=agent_id,
        related_id=tip_id,
        details={
            "tip_id": tip_id,
            "solution_index": solution_index,
            "solution_title": solution["title"],
            "solution_description": solution["description"],
            "priority": solution["priority"]
        },
        priority="medium"
    )
    
    # Enviar notificação
    notifications.send_notification(
        db,
        title=f"Solução Aplicada: {solution['title']}",
        message=f"A solução '{solution['title']}' foi aplicada com sucesso para o problema '{tip['title']}'.",
        category="system",
        priority="low",
        related_id=agent_id or tip_id
    )
    
    return {
        "success": True,
        "tip_id": tip_id,
        "solution_applied": solution,
        "agent_id": agent_id,
        "timestamp": datetime.utcnow().isoformat()
    }