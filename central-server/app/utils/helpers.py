"""
Funções auxiliares e utilitários
"""
import json
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union


def generate_config_hash(config: dict) -> str:
    """
    Gera hash único para configuração
    
    Args:
        config: Dicionário de configuração
        
    Returns:
        Hash MD5 da configuração
    """
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()


def format_size(size_bytes: float) -> str:
    """
    Formata tamanho em bytes para formato legível
    
    Args:
        size_bytes: Tamanho em bytes
        
    Returns:
        String formatada (ex: "1.5 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"


def format_duration(seconds: float) -> str:
    """
    Formata duração em segundos para formato legível
    
    Args:
        seconds: Duração em segundos
        
    Returns:
        String formatada (ex: "2 horas, 15 minutos")
    """
    if seconds < 60:
        return f"{seconds:.1f} segundos"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{int(minutes)} min, {int(remaining_seconds)} seg"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours < 24:
        return f"{int(hours)} horas, {int(remaining_minutes)} min"
    
    days = hours // 24
    remaining_hours = hours % 24
    
    return f"{int(days)} dias, {int(remaining_hours)} horas"


def get_current_timestamp() -> str:
    """
    Retorna timestamp atual em formato ISO 8601
    
    Returns:
        String com timestamp
    """
    return datetime.utcnow().isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Converte string ISO para datetime
    
    Args:
        timestamp_str: String com timestamp ISO
        
    Returns:
        Objeto datetime
    """
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))


def safe_dict_get(dictionary: dict, key: str, default: Any = None) -> Any:
    """
    Obtém valor de dicionário com tratamento de erros
    
    Args:
        dictionary: Dicionário
        key: Chave
        default: Valor padrão
        
    Returns:
        Valor da chave ou default
    """
    try:
        return dictionary.get(key, default)
    except (AttributeError, TypeError):
        return default


def merge_dicts(dict1: dict, dict2: dict) -> dict:
    """
    Mescla dois dicionários recursivamente
    
    Args:
        dict1: Primeiro dicionário
        dict2: Segundo dicionário
        
    Returns:
        Dicionário mesclado
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_email(email: str) -> bool:
    """
    Valida formato de email
    
    Args:
        email: String de email
        
    Returns:
        True se válido
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_hostname(hostname: str) -> bool:
    """
    Valida formato de hostname
    
    Args:
        hostname: String de hostname
        
    Returns:
        True se válido
    """
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, hostname))


def validate_ip_address(ip: str) -> bool:
    """
    Valida endereço IP (IPv4 ou IPv6)
    
    Args:
        ip: String de IP
        
    Returns:
        True se válido
    """
    # IPv4
    ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    # IPv6 (simplificado)
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){7}[0-9a-fA-F]{0,4}$'
    
    return bool(re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip))


def generate_random_string(length: int = 16, alphanumeric: bool = True) -> str:
    """
    Gera string aleatória segura
    
    Args:
        length: Comprimento da string
        alphanumeric: Se deve usar apenas alfanuméricos
        
    Returns:
        String aleatória
    """
    import secrets
    import string
    
    if alphanumeric:
        alphabet = string.ascii_letters + string.digits
    else:
        alphabet = string.ascii_letters + string.digits + string.punctuation
    
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def sanitize_filename(filename: str) -> str:
    """
    Remove caracteres perigosos de nome de arquivo
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        Nome sanitizado
    """
    # Remover caracteres perigosos
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    # Remover múltiplos espaços/underscores
    sanitized = re.sub(r'[\s_]+', '_', sanitized)
    return sanitized.strip('._')


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Trunca string se exceder tamanho máximo
    
    Args:
        text: Texto original
        max_length: Comprimento máximo
        suffix: Sufixo a adicionar
        
    Returns:
        Texto truncado
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def calculate_percentage(part: Union[int, float], total: Union[int, float]) -> float:
    """
    Calcula percentual com tratamento de divisão por zero
    
    Args:
        part: Parte
        total: Total
        
    Returns:
        Percentual arredondado
    """
    if total == 0:
        return 0.0
    
    return round((part / total) * 100, 2)


def parse_cron_expression(cron: str) -> dict:
    """
    Analisa expressão cron
    
    Args:
        cron: Expressão cron (ex: "0 2 * * *")
        
    Returns:
        Dicionário com componentes
    """
    parts = cron.split()
    
    if len(parts) != 5:
        raise ValueError("Expressão cron deve ter 5 partes")
    
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day_of_month": parts[2],
        "month": parts[3],
        "day_of_week": parts[4]
    }


def is_valid_json(json_str: str) -> bool:
    """
    Verifica se string é JSON válido
    
    Args:
        json_str: String JSON
        
    Returns:
        True se válido
    """
    try:
        json.loads(json_str)
        return True
    except (ValueError, TypeError):
        return False


def deep_update(base_dict: dict, update_dict: dict) -> dict:
    """
    Atualiza dicionário recursivamente
    
    Args:
        base_dict: Dicionário base
        update_dict: Dicionário com atualizações
        
    Returns:
        Dicionário atualizado
    """
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            base_dict[key] = deep_update(base_dict[key], value)
        else:
            base_dict[key] = value
    
    return base_dict


def chunks(lst: List, n: int):
    """
    Divide lista em chunks de tamanho n
    
    Args:
        lst: Lista
        n: Tamanho do chunk
        
    Yields:
        Chunks da lista
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """
    Achata dicionário aninhado
    
    Args:
        d: Dicionário aninhado
        parent_key: Chave pai (para recursão)
        sep: Separador
        
    Returns:
        Dicionário achatado
    """
    items = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)


def get_client_ip(request) -> str:
    """
    Obtém IP real do cliente considerando proxies
    
    Args:
        request: Request do FastAPI
        
    Returns:
        Endereço IP do cliente
    """
    # Verificar headers de proxy
    if hasattr(request, 'headers'):
        # X-Forwarded-For
        if "x-forwarded-for" in request.headers:
            return request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # X-Real-IP
        if "x-real-ip" in request.headers:
            return request.headers["x-real-ip"]
    
    # IP direto
    if hasattr(request, 'client') and request.client:
        return request.client.host
    
    return "unknown"


def seconds_until(target_time: datetime) -> float:
    """
    Calcula segundos até um horário específico
    
    Args:
        target_time: Horário alvo
        
    Returns:
        Segundos até o horário
    """
    now = datetime.utcnow()
    delta = target_time - now
    return max(0, delta.total_seconds())


def is_business_hours(start_hour: int = 9, end_hour: int = 18) -> bool:
    """
    Verifica se está em horário comercial
    
    Args:
        start_hour: Hora de início
        end_hour: Hora de fim
        
    Returns:
        True se em horário comercial
    """
    now = datetime.utcnow()
    return start_hour <= now.hour < end_hour and now.weekday() < 5


class Timer:
    """Context manager para medir tempo de execução"""
    
    def __init__(self):
        self.start = None
        self.end = None
        self.elapsed = None
    
    def __enter__(self):
        self.start = datetime.utcnow()
        return self
    
    def __exit__(self, *args):
        self.end = datetime.utcnow()
        self.elapsed = (self.end - self.start).total_seconds()
    
    def __str__(self):
        return f"{self.elapsed:.3f}s" if self.elapsed else "Not measured"