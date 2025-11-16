#!/bin/bash
set -e

echo "🚀 Iniciando Servidor Central de Backup no WSL2..."

# Navegar para o diretório do projeto
cd /mnt/d/Novo/Servidor\ GBOC/central-server

# Parar e remover containers existentes
echo "⏹️  Parando containers existentes..."
docker-compose down

# Limpar cache do builder
echo "🧹 Limpando cache do builder..."
docker builder prune -f

# Reconstruir e iniciar
echo "🏗️  Reconstruindo e iniciando servidor..."
docker-compose up -d --build

# Aguardar um momento para o container iniciar
echo "⏳ Aguardando o servidor iniciar..."
sleep 10

# Verificar se o container está funcionando
echo "🔍 Verificando status do container..."
docker ps

# Testar endpoint de saúde
echo "✅ Testando endpoint de saúde..."
curl -v http://localhost:8000/health

echo "🎉 Servidor central iniciado com sucesso!"
echo "🌐 Acesse: http://localhost:8000"
echo "🔧 API: http://localhost:8000/health"