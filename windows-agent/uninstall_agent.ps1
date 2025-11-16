<#
.SYNOPSIS
    Desinstala o Backup Agent do Windows
.DESCRIPTION
    Remove completamente o serviço e arquivos do agente de backup
.EXAMPLE
    .\uninstall_agent.ps1
#>

# Verificar permissões de administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Este script precisa ser executado como Administrador"
    exit 1
}

Write-Host "🚨 Iniciando desinstalação do Backup Agent..." -ForegroundColor Red

$serviceName = "BackupAgent"
$installDir = "C:\Program Files\BackupAgent"
$configDir = "C:\ProgramData\BackupAgent"
$nssmExe = "$installDir\nssm.exe"

# Parar e remover serviço
Write-Host "⏹️  Parando e removendo serviço..." -ForegroundColor Yellow
if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    Stop-Service $serviceName -Force -ErrorAction SilentlyContinue
    if (Test-Path $nssmExe) {
        & $nssmExe remove $serviceName confirm
    } else {
        sc.exe delete $serviceName | Out-Null
    }
}

# Remover diretórios de instalação
Write-Host "🗑️  Removendo diretórios de instalação..." -ForegroundColor Yellow
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Diretório de instalação removido: $installDir" -ForegroundColor Green
}

# Remover logs (manter configurações por padrão)
$logsDir = "$configDir\logs"
if (Test-Path $logsDir) {
    Remove-Item $logsDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Diretório de logs removido: $logsDir" -ForegroundColor Green
}

Write-Host "`n✅ Desinstalação concluída!" -ForegroundColor Green
Write-Host "ℹ️  Os arquivos de configuração permanecem em: $configDir" -ForegroundColor Cyan
Write-Host "   Para removê-los completamente, exclua manualmente o diretório." -ForegroundColor Cyan
Write-Host "`n🔍 Status final:"
Write-Host "   Serviço $serviceName: $(if (Get-Service $serviceName -ErrorAction SilentlyContinue) { 'EXISTE' } else { 'REMOVIDO' })"
Write-Host "   Diretório de instalação: $(if (Test-Path $installDir) { 'EXISTE' } else { 'REMOVIDO' })"