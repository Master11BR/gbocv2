#Requires -RunAsAdministrator

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Atualizar o Gerenciador de Pacotes NuGet para poder baixar a ultima versao do Docker.
Write-Host "Atualizando o Gerenciador de Pacotes Nuget"
Install-PackageProvider -Name NuGet -Force

# Instalar a Função de Container requerimento necessário para usar o Docker
Write-Host "Instalando o Containers Feature"
Install-WindowsFeature -Name Containers

# Instalar o Docker Engine Enterprise no Servidor
Write-Host "Instalando o Docker Engine Enterprise"
Install-Module -Name DockerProvider -Repository PSGallery -Force

# Instalar a interface cliente para gerenciar o Docker Engine Enterprise
Write-Host "Instalando a Interface de Gerenciamento do Docker"
Install-Package -Name docker -ProviderName DockerProvider

# Uma reinicialização é requerida, devido a instalação do Windows Feature Containers e alterações pertinentes no sistema.
pause

Write-Host "O Servidor será reiniciado"
Restart-Computer

