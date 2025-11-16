import os
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# IMPORTS ABSOLUTOS (corrigidos)
from app.database import engine, Base
import app.models as models

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar diretórios necessários
os.makedirs("/app/data", exist_ok=True)

# Inicializar banco de dados
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Backup Central Server",
    description="Servidor central de gerenciamento de backups",
    version="1.0.0"
)

# CORS - permitir todas as origens em desenvolvimento
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {"message": "Backup Central Server está funcionando!"}

if __name__ == "__main__":
    logger.info("🚀 Servidor iniciando em modo de produção")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)