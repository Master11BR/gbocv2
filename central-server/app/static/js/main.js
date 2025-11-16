document.addEventListener('DOMContentLoaded', function() {
    // Inicializar componentes
    initSidebarToggle();
    initThemeToggle();
    initNotifications();
    initToasts();
    
    // Carregar dados iniciais
    loadDashboardData();
    
    // Configurar intervalos de atualização
    setInterval(loadDashboardData, 60000); // Atualizar a cada minuto
});

function initSidebarToggle() {
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('collapsed');
        });
    }
    
    // Fechar sidebar em telas pequenas ao clicar fora
    document.addEventListener('click', (e) => {
        if (window.innerWidth < 768 && 
            !sidebar.contains(e.target) && 
            !sidebarToggle.contains(e.target) &&
            !sidebar.classList.contains('collapsed')) {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('collapsed');
        }
    });
}

function initThemeToggle() {
    const themeToggle = document.querySelector('.theme-toggle');
    const body = document.body;
    const savedTheme = localStorage.getItem('theme');
    
    if (savedTheme) {
        body.classList.add(savedTheme);
        if (themeToggle) {
            themeToggle.innerHTML = savedTheme === 'dark' ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
        }
    }
    
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            if (body.classList.contains('dark')) {
                body.classList.remove('dark');
                localStorage.setItem('theme', 'light');
                themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            } else {
                body.classList.add('dark');
                localStorage.setItem('theme', 'dark');
                themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            }
        });
    }
}

function initNotifications() {
    const notificationsBtn = document.getElementById('notifications-btn');
    
    if (notificationsBtn) {
        notificationsBtn.addEventListener('click', () => {
            toggleNotificationsDropdown();
        });
        
        // Carregar contagem de notificações inicial
        loadNotificationsCount();
        
        // Atualizar contagem periodicamente
        setInterval(loadNotificationsCount, 30000);
    }
}

function loadNotificationsCount() {
    fetch('/api/notifications/unread')
        .then(response => response.json())
        .then(data => {
            const countEl = document.getElementById('notifications-count');
            if (countEl) {
                countEl.textContent = data.count;
                if (data.count > 0) {
                    countEl.classList.add('bg-danger');
                } else {
                    countEl.classList.remove('bg-danger');
                }
            }
        })
        .catch(error => console.error('Erro ao carregar notificações:', error));
}

function toggleNotificationsDropdown() {
    const dropdown = document.querySelector('.dropdown-menu[aria-labelledby="notifications-btn"]');
    if (dropdown) {
        dropdown.classList.toggle('show');
        
        // Fechar dropdown ao clicar fora
        document.addEventListener('click', function closeDropdown(e) {
            if (!dropdown.contains(e.target) && !document.getElementById('notifications-btn').contains(e.target)) {
                dropdown.classList.remove('show');
                document.removeEventListener('click', closeDropdown);
            }
        });
    }
}

function initToasts() {
    // Função para mostrar toast notifications
    window.showToast = function(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
                <div class="toast-message">${message}</div>
                <button class="toast-close">&times;</button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Mostrar toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Remover toast após 5 segundos
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toastContainer.contains(toast)) {
                    toastContainer.removeChild(toast);
                }
            }, 300);
        }, 5000);
        
        // Fechar ao clicar no botão
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toastContainer.contains(toast)) {
                    toastContainer.removeChild(toast);
                }
            }, 300);
        });
    };
}

function loadDashboardData() {
    Promise.all([
        fetch('/api/dashboard'),
        fetch('/api/agents'),
        fetch('/api/backups?limit=10')
    ])
    .then(([dashboardRes, agentsRes, backupsRes]) => Promise.all([
        dashboardRes.json(),
        agentsRes.json(),
        backupsRes.json()
    ]))
    .then(([dashboardData, agentsData, backupsData]) => {
        updateStatsCards(dashboardData);
        updateAgentsList(agentsData);
        updateRecentBackups(backupsData);
        updateCharts(dashboardData);
    })
    .catch(error => {
        console.error('Erro ao carregar dados do dashboard:', error);
        showToast('Erro ao carregar dados do dashboard', 'error');
    });
}

function updateStatsCards(data) {
    document.getElementById('total-agents').textContent = data.total_agents || 0;
    document.getElementById('success-backups').textContent = data.backup_summary?.success || 0;
    document.getElementById('failed-backups').textContent = data.backup_summary?.failed || 0;
    
    const storagePercent = data.storage_usage?.usage_percent || 0;
    document.getElementById('storage-percent').textContent = `${storagePercent}%`;
    document.getElementById('storage-progress').style.width = `${storagePercent}%`;
    
    // Atualizar cor do progress bar baseado no percentual
    const progressBar = document.getElementById('storage-progress');
    if (storagePercent > 90) {
        progressBar.className = 'progress-bar bg-danger';
    } else if (storagePercent > 75) {
        progressBar.className = 'progress-bar bg-warning';
    } else {
        progressBar.className = 'progress-bar bg-info';
    }
}

function updateAgentsList(agents) {
    const tableBody = document.querySelector('#agents-table tbody');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    agents.forEach(agent => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${agent.hostname}</td>
            <td>${agent.ip_address}</td>
            <td>${agent.os}</td>
            <td>
                <span class="status ${agent.status}">${agent.status}</span>
            </td>
            <td>${new Date(agent.last_seen).toLocaleString('pt-BR')}</td>
            <td>
                <button class="action-btn" onclick="viewAgentDetails('${agent.agent_id}')">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="action-btn ${agent.enabled ? 'success' : 'warning'}" 
                        onclick="toggleAgentStatus('${agent.agent_id}', ${agent.enabled})">
                    <i class="fas ${agent.enabled ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
                </button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function viewAgentDetails(agentId) {
    window.location.href = `/agents/${agentId}`;
}

function toggleAgentStatus(agentId, currentStatus) {
    if (confirm(`Tem certeza que deseja ${currentStatus ? 'desativar' : 'ativar'} este agente?`)) {
        fetch(`/api/agents/${agentId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ enabled: !currentStatus })
        })
        .then(response => {
            if (!response.ok) throw new Error('Falha ao atualizar status do agente');
            return response.json();
        })
        .then(() => {
            showToast(`Agente ${currentStatus ? 'desativado' : 'ativado'} com sucesso!`, 'success');
            loadDashboardData();
        })
        .catch(error => {
            console.error('Erro ao atualizar status do agente:', error);
            showToast('Erro ao atualizar status do agente', 'error');
        });
    }
}

function updateRecentBackups(backups) {
    const tableBody = document.querySelector('#backups-table tbody');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    backups.forEach(backup => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${backup.agent_id}</td>
            <td>${backup.source}</td>
            <td>
                <span class="status ${backup.status}">${backup.status}</span>
            </td>
            <td>${backup.tool}</td>
            <td>${backup.size_mb.toFixed(2)} MB</td>
            <td>${backup.duration_sec ? backup.duration_sec.toFixed(1) : '-'}</td>
            <td>${new Date(backup.start_time).toLocaleString('pt-BR')}</td>
        `;
        tableBody.appendChild(row);
    });
}

function updateCharts(dashboardData) {
    // Chart.js para backups
    const backupsCtx = document.getElementById('backupsChart');
    if (backupsCtx) {
        new Chart(backupsCtx, {
            type: 'doughnut',
            data: {
                labels: ['Sucesso', 'Falhados', 'Executando', 'Pendentes'],
                datasets: [{
                    data: [
                        dashboardData.backup_summary?.success || 0,
                        dashboardData.backup_summary?.failed || 0,
                        dashboardData.backup_summary?.running || 0,
                        dashboardData.backup_summary?.pending || 0
                    ],
                    backgroundColor: [
                        '#28a745',
                        '#dc3545',
                        '#17a2b8',
                        '#ffc107'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                    }
                }
            }
        });
    }
    
    // Chart.js para agentes online
    const agentsCtx = document.getElementById('agentsChart');
    if (agentsCtx) {
        const onlineAgents = dashboardData.online_agents || 0;
        const offlineAgents = dashboardData.total_agents - onlineAgents;
        
        new Chart(agentsCtx, {
            type: 'bar',
            data: {
                labels: ['Online', 'Offline'],
                datasets: [{
                    label: 'Agentes',
                    data: [onlineAgents, offlineAgents],
                    backgroundColor: [
                        '#28a745',
                        '#dc3545'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }
}

// Função para logout
function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
}

// Função para verificar autenticação
function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
        return false;
    }
    return true;
}

// Função para formatar datas
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('pt-BR');
}

// Função para formatar tamanhos
function formatSize(bytes) {
    if (!bytes) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let unitIndex = 0;
    
    while (bytes >= 1024 && unitIndex < units.length - 1) {
        bytes /= 1024;
        unitIndex++;
    }
    
    return `${bytes.toFixed(2)} ${units[unitIndex]}`;
}

// Função para formatar duração
function formatDuration(seconds) {
    if (!seconds) return '-';
    
    if (seconds < 60) return `${seconds.toFixed(1)} seg`;
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (minutes < 60) return `${minutes} min ${remainingSeconds.toFixed(0)} seg`;
    
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    
    return `${hours}h ${remainingMinutes}min`;
}

// Adicionar evento de logout ao botão
document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
    
    // Verificar autenticação
    checkAuth();
});