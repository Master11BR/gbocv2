from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

class AgentBase(BaseModel):
    hostname: str
    ip_address: str
    os: str
    agent_id: str
    enabled: bool = True

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    enabled: bool
    config: Optional[Dict[str, Any]] = None

class Agent(AgentBase):
    id: int
    last_seen: datetime
    config_hash: str
    
    class Config:
        from_attributes = True

class BackupJobBase(BaseModel):
    agent_id: str
    status: str
    tool: str
    source: str
    destination: str
    size_bytes: float = 0
    logs: Optional[str] = None
    error_message: Optional[str] = None

class BackupJobCreate(BackupJobBase):
    start_time: datetime
    end_time: Optional[datetime] = None

class BackupJob(BackupJobBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AgentConfigBase(BaseModel):
    agent_id: str
    config: Dict[str, Any]

class SystemStats(BaseModel):
    total_agents: int
    active_agents: int
    backup_summary: Dict[str, int]
    recent_backups: List[Dict[str, Any]]
    storage_usage: Dict[str, Any]

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None