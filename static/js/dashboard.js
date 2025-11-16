/**
 * KuCoin Bot Analyzer - Dashboard JavaScript
 * Système avancé de filtrage, tri et recommandation
 */

// État global de l'application
const AppState = {
    bots: [],
    filteredBots: [],
    currentView: 'table',
    filters: {
        strategies: [],
        returnMin: null,
        returnMax: null,
        apr7Min: null,
        apr7Max: null,
        apr30Min: null,
        apr30Max: null,
        riskLevels: [],
        durationMin: null,
        copiersMin: null,
        pairs: []
    },
    sortBy: 'return_24h_desc',
    charts: {},
    updateInterval: null
};

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    loadBots();
    setupEventListeners();
    startAutoUpdate();
});

/**
 * Initialise l'application
 */
function initializeApp() {
    console.log('🚀 Initialisation du Dashboard KuCoin Bot Analyzer');
    
    // Initialiser les graphiques Chart.js
    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2A3441';
    Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
}

/**
 * Configure les écouteurs d'événements
 */
function setupEventListeners() {
    // Filtres de stratégie
    document.querySelectorAll('#strategy-filters input').forEach(checkbox => {
        checkbox.addEventListener('change', applyFilters);
    });
    
    // Filtres de performance
    ['return-min', 'return-max', 'apr7-min', 'apr7-max', 'apr30-min', 'apr30-max'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', debounce(applyFilters, 500));
        }
    });
    
    // Filtres de risque
    document.querySelectorAll('.risk-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.classList.toggle('active');
            applyFilters();
        });
    });
    
    // Durée et copieurs
    ['duration-min', 'copiers-min'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', debounce(applyFilters, 500));
        }
    });
    
    // Recherche de paires
    const pairSearch = document.getElementById('pair-search');
    if (pairSearch) {
        pairSearch.addEventListener('input', debounce(filterPairs, 300));
    }
}

/**
 * Charge les données des bots depuis l'API
 */
async function loadBots() {
    try {
        showLoading();
        
        // Charger les données des bots
        const response = await fetch('/api/bots');
        const data = await response.json();
        
        if (data.success) {
            AppState.bots = processBotsData(data.bots);
            AppState.filteredBots = [...AppState.bots];
            
            // Mettre à jour l'interface
            updateStats(data);
            generatePairsList();
            renderBots();
            generateRecommendations();
            updateCharts();
            
            console.log(`✅ ${AppState.bots.length} bots chargés avec succès`);
        } else {
            showError('Erreur lors du chargement des bots');
        }
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Impossible de charger les données');
    } finally {
        hideLoading();
    }
}

/**
 * Traite et enrichit les données des bots
 */
function processBotsData(bots) {
    return bots.map(bot => ({
        ...bot,
        // Calcul du score composite pour les recommandations
        compositeScore: calculateCompositeScore(bot),
        // Catégorisation du niveau de risque
        riskLevel: categorizeRisk(bot.risk_score || 5),
        // Parsing de la durée en jours
        durationDays: parseDuration(bot.duration),
        // Formatage des valeurs numériques
        return_24h_num: parseFloat(bot.return_24h) || 0,
        apr_7d_num: parseFloat(bot.apr_7d) || 0,
        apr_30d_num: parseFloat(bot.apr_30d) || 0
    }));
}

/**
 * Calcule un score composite pour le classement intelligent
 */
function calculateCompositeScore(bot) {
    const weights = {
        return_24h: 0.2,
        apr_7d: 0.25,
        apr_30d: 0.3,
        duration: 0.15,
        copiers: 0.05,
        risk: 0.05
    };
    
    // Normalisation des valeurs (0-100)
    const normalized = {
        return_24h: Math.min(100, Math.max(0, (parseFloat(bot.return_24h) || 0) + 50)),
        apr_7d: Math.min(100, Math.max(0, parseFloat(bot.apr_7d) || 0)),
        apr_30d: Math.min(100, Math.max(0, parseFloat(bot.apr_30d) || 0)),
        duration: Math.min(100, (parseDuration(bot.duration) / 365) * 100),
        copiers: Math.min(100, (parseInt(bot.copiers) || 0) / 10),
        risk: 100 - ((parseFloat(bot.risk_score) || 5) * 10)
    };
    
    // Calcul du score pondéré
    let score = 0;
    for (const [metric, weight] of Object.entries(weights)) {
        score += normalized[metric] * weight;
    }
    
    return Math.round(score);
}

/**
 * Catégorise le niveau de risque
 */
function categorizeRisk(riskScore) {
    if (riskScore <= 3) return 'low';
    if (riskScore <= 6) return 'medium';
    return 'high';
}

/**
 * Parse la durée en nombre de jours
 */
function parseDuration(durationStr) {
    if (!durationStr) return 0;
    
    const match = durationStr.match(/(\d+)D/);
    if (match) {
        return parseInt(match[1]);
    }
    return 0;
}

/**
 * Applique les filtres actuels
 */
function applyFilters() {
    // Collecter les filtres actifs
    const filters = collectActiveFilters();
    
    // Appliquer les filtres
    AppState.filteredBots = AppState.bots.filter(bot => {
        // Filtre par stratégie
        if (filters.strategies.length > 0 && !filters.strategies.includes(bot.strategy)) {
            return false;
        }
        
        // Filtre par rendement 24h
        if (filters.returnMin !== null && bot.return_24h_num < filters.returnMin) return false;
        if (filters.returnMax !== null && bot.return_24h_num > filters.returnMax) return false;
        
        // Filtre par APR 7 jours
        if (filters.apr7Min !== null && bot.apr_7d_num < filters.apr7Min) return false;
        if (filters.apr7Max !== null && bot.apr_7d_num > filters.apr7Max) return false;
        
        // Filtre par APR 30 jours
        if (filters.apr30Min !== null && bot.apr_30d_num < filters.apr30Min) return false;
        if (filters.apr30Max !== null && bot.apr_30d_num > filters.apr30Max) return false;
        
        // Filtre par niveau de risque
        if (filters.riskLevels.length > 0 && !filters.riskLevels.includes(bot.riskLevel)) {
            return false;
        }
        
        // Filtre par durée minimale
        if (filters.durationMin !== null && bot.durationDays < filters.durationMin) return false;
        
        // Filtre par nombre de copieurs
        if (filters.copiersMin !== null && (bot.copiers || 0) < filters.copiersMin) return false;
        
        // Filtre par paires
        if (filters.pairs.length > 0 && !filters.pairs.includes(bot.pair)) {
            return false;
        }
        
        return true;
    });
    
    // Appliquer le tri
    applySort();
    
    // Mettre à jour l'affichage
    renderBots();
    generateRecommendations();
    updateCharts();
}

/**
 * Collecte les filtres actifs depuis l'interface
 */
function collectActiveFilters() {
    const filters = {
        strategies: [],
        returnMin: null,
        returnMax: null,
        apr7Min: null,
        apr7Max: null,
        apr30Min: null,
        apr30Max: null,
        riskLevels: [],
        durationMin: null,
        copiersMin: null,
        pairs: []
    };
    
    // Stratégies
    document.querySelectorAll('#strategy-filters input:checked').forEach(checkbox => {
        filters.strategies.push(checkbox.value);
    });
    
    // Rendements
    filters.returnMin = parseFloat(document.getElementById('return-min')?.value) || null;
    filters.returnMax = parseFloat(document.getElementById('return-max')?.value) || null;
    filters.apr7Min = parseFloat(document.getElementById('apr7-min')?.value) || null;
    filters.apr7Max = parseFloat(document.getElementById('apr7-max')?.value) || null;
    filters.apr30Min = parseFloat(document.getElementById('apr30-min')?.value) || null;
    filters.apr30Max = parseFloat(document.getElementById('apr30-max')?.value) || null;
    
    // Niveaux de risque
    document.querySelectorAll('.risk-btn.active').forEach(btn => {
        filters.riskLevels.push(btn.dataset.risk);
    });
    
    // Durée et copieurs
    filters.durationMin = parseInt(document.getElementById('duration-min')?.value) || null;
    filters.copiersMin = parseInt(document.getElementById('copiers-min')?.value) || null;
    
    // Paires sélectionnées
    document.querySelectorAll('#pairs-list input:checked').forEach(checkbox => {
        filters.pairs.push(checkbox.value);
    });
    
    AppState.filters = filters;
    return filters;
}

/**
 * Applique le tri sur les bots filtrés
 */
function applySort() {
    const sortBy = document.getElementById('sort-select')?.value || AppState.sortBy;
    AppState.sortBy = sortBy;
    
    AppState.filteredBots.sort((a, b) => {
        switch (sortBy) {
            case 'return_24h_desc':
                return b.return_24h_num - a.return_24h_num;
            case 'return_24h_asc':
                return a.return_24h_num - b.return_24h_num;
            case 'apr_7d_desc':
                return b.apr_7d_num - a.apr_7d_num;
            case 'apr_30d_desc':
                return b.apr_30d_num - a.apr_30d_num;
            case 'risk_asc':
                return (a.risk_score || 5) - (b.risk_score || 5);
            case 'copiers_desc':
                return (b.copiers || 0) - (a.copiers || 0);
            case 'duration_desc':
                return b.durationDays - a.durationDays;
            default:
                return b.compositeScore - a.compositeScore;
        }
    });
}

/**
 * Génère des recommandations personnalisées
 */
function generateRecommendations() {
    const panel = document.getElementById('recommendations');
    if (!panel) return;
    
    // Analyser les bots filtrés pour générer des recommandations
    const recommendations = [];
    
    // Top performer global
    const topPerformer = AppState.filteredBots
        .filter(bot => bot.durationDays > 30)
        .sort((a, b) => b.compositeScore - a.compositeScore)[0];
    
    if (topPerformer) {
        recommendations.push({
            type: 'top-performer',
            title: '🏆 Meilleur Performer Global',
            bot: topPerformer,
            reason: `Score composite de ${topPerformer.compositeScore}/100 avec ${topPerformer.durationDays} jours d'historique`
        });
    }
    
    // Bot le plus sûr
    const safestBot = AppState.filteredBots
        .filter(bot => bot.riskLevel === 'low' && bot.durationDays > 90)
        .sort((a, b) => b.apr_30d_num - a.apr_30d_num)[0];
    
    if (safestBot) {
        recommendations.push({
            type: 'safest',
            title: '🛡️ Choix le Plus Sûr',
            bot: safestBot,
            reason: `Risque faible avec APR stable de ${safestBot.apr_30d_num}% sur 30 jours`
        });
    }
    
    // Meilleur ratio risque/rendement
    const bestRatio = AppState.filteredBots
        .filter(bot => bot.apr_7d_num > 50)
        .sort((a, b) => {
            const ratioA = a.apr_7d_num / (a.risk_score || 5);
            const ratioB = b.apr_7d_num / (b.risk_score || 5);
            return ratioB - ratioA;
        })[0];
    
    if (bestRatio) {
        recommendations.push({
            type: 'best-ratio',
            title: '⚖️ Meilleur Ratio Risque/Rendement',
            bot: bestRatio,
            reason: `APR de ${bestRatio.apr_7d_num}% avec un risque de ${bestRatio.risk_score || 5}/10`
        });
    }
    
    // Afficher les recommandations
    if (recommendations.length > 0) {
        panel.classList.add('active');
        const cardsContainer = panel.querySelector('.recommendation-cards');
        
        cardsContainer.innerHTML = recommendations.map(rec => `
            <div class="recommendation-card ${rec.type}">
                <h4>${rec.title}</h4>
                <div class="rec-bot-info">
                    <p class="bot-name">${rec.bot.bot_name || 'Bot #' + rec.bot.rank}</p>
                    <p class="bot-pair">${rec.bot.pair} - ${rec.bot.strategy}</p>
                </div>
                <div class="rec-metrics">
                    <span class="metric">
                        <label>24h:</label>
                        <value class="${rec.bot.return_24h_num >= 0 ? 'positive' : 'negative'}">
                            ${rec.bot.return_24h_num.toFixed(2)}%
                        </value>
                    </span>
                    <span class="metric">
                        <label>APR 7j:</label>
                        <value>${rec.bot.apr_7d_num.toFixed(0)}%</value>
                    </span>
                </div>
                <p class="rec-reason">${rec.reason}</p>
                <button class="btn-view-details" onclick="showBotDetails(${rec.bot.id})">
                    Voir les détails
                </button>
            </div>
        `).join('');
    } else {
        panel.classList.remove('active');
    }
}

/**
 * Affiche les bots selon la vue active
 */
function renderBots() {
    const view = AppState.currentView;
    
    switch (view) {
        case 'table':
            renderTableView();
            break;
        case 'cards':
            renderCardsView();
            break;
        case 'analytics':
            renderAnalyticsView();
            break;
    }
}

/**
 * Affiche la vue tableau
 */
function renderTableView() {
    const tbody = document.getElementById('bots-tbody');
    if (!tbody) return;
    
    if (AppState.filteredBots.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; padding: 2rem;">
                    <p style="color: var(--text-secondary);">Aucun bot ne correspond aux filtres sélectionnés</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = AppState.filteredBots.map((bot, index) => `
        <tr>
            <td>
                <span class="rank">#${index + 1}</span>
            </td>
            <td>
                <div class="bot-info">
                    <span class="bot-name">${bot.bot_name || 'N/A'}</span>
                    <span class="creator">${bot.creator || bot.username || 'Anonyme'}</span>
                </div>
            </td>
            <td>${bot.pair}</td>
            <td>
                <span class="badge badge-info">${bot.strategy}</span>
            </td>
            <td>
                <span class="${bot.return_24h_num >= 0 ? 'positive' : 'negative'}">
                    ${bot.return_24h_num.toFixed(2)}%
                </span>
            </td>
            <td>${bot.apr_7d_num ? bot.apr_7d_num.toFixed(0) + '%' : 'N/A'}</td>
            <td>${bot.apr_30d_num ? bot.apr_30d_num.toFixed(0) + '%' : 'N/A'}</td>
            <td>${bot.duration || 'N/A'}</td>
            <td>${bot.copiers || 0}</td>
            <td>
                <span class="risk-score risk-${bot.riskLevel}">
                    ${bot.risk_score || 5}/10
                </span>
            </td>
            <td>
                <button class="btn-action" onclick="showBotDetails(${bot.id})">
                    📊
                </button>
                <button class="btn-action" onclick="copyBot(${bot.id})">
                    📋
                </button>
            </td>
        </tr>
    `).join('');
}

/**
 * Affiche la vue cartes
 */
function renderCardsView() {
    const container = document.getElementById('bots-cards');
    if (!container) return;
    
    if (AppState.filteredBots.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem;">
                <p style="color: var(--text-secondary);">Aucun bot ne correspond aux filtres sélectionnés</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = AppState.filteredBots.slice(0, 20).map((bot, index) => `
        <div class="bot-card" onclick="showBotDetails(${bot.id})">
            <div class="card-header">
                <span class="card-rank">#${index + 1}</span>
                <span class="card-strategy">${bot.strategy}</span>
            </div>
            
            <div class="card-body">
                <h3>${bot.bot_name || 'Bot #' + bot.rank}</h3>
                <p class="card-pair">${bot.pair}</p>
                
                <div class="card-metric">
                    <span class="metric-label">Rendement 24h</span>
                    <span class="metric-value ${bot.return_24h_num >= 0 ? 'positive' : 'negative'}">
                        ${bot.return_24h_num.toFixed(2)}%
                    </span>
                </div>
                
                <div class="card-metric">
                    <span class="metric-label">APR 7 jours</span>
                    <span class="metric-value">${bot.apr_7d_num ? bot.apr_7d_num.toFixed(0) + '%' : 'N/A'}</span>
                </div>
                
                <div class="card-metric">
                    <span class="metric-label">Score de risque</span>
                    <span class="metric-value risk-${bot.riskLevel}">
                        ${bot.risk_score || 5}/10
                    </span>
                </div>
                
                <div class="card-metric">
                    <span class="metric-label">Durée</span>
                    <span class="metric-value">${bot.duration || 'N/A'}</span>
                </div>
            </div>
            
            <div class="card-footer">
                <span class="copiers">👥 ${bot.copiers || 0} copieurs</span>
                <span class="score">Score: ${bot.compositeScore}/100</span>
            </div>
        </div>
    `).join('');
}

/**
 * Met à jour les graphiques
 */
function updateCharts() {
    if (AppState.currentView !== 'analytics') return;
    
    // Graphique de distribution des performances
    updatePerformanceChart();
    
    // Graphique risque/rendement
    updateRiskReturnChart();
    
    // Graphique par stratégie
    updateStrategyChart();
    
    // Graphique des paires
    updatePairsChart();
}

/**
 * Met à jour le graphique de performance
 */
function updatePerformanceChart() {
    const ctx = document.getElementById('performance-chart');
    if (!ctx) return;
    
    // Préparer les données
    const ranges = [
        { label: '< 0%', min: -100, max: 0 },
        { label: '0-10%', min: 0, max: 10 },
        { label: '10-25%', min: 10, max: 25 },
        { label: '25-50%', min: 25, max: 50 },
        { label: '> 50%', min: 50, max: 200 }
    ];
    
    const data = ranges.map(range => {
        return AppState.filteredBots.filter(bot => 
            bot.return_24h_num >= range.min && bot.return_24h_num < range.max
        ).length;
    });
    
    // Détruire le graphique existant
    if (AppState.charts.performance) {
        AppState.charts.performance.destroy();
    }
    
    // Créer le nouveau graphique
    AppState.charts.performance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ranges.map(r => r.label),
            datasets: [{
                label: 'Nombre de bots',
                data: data,
                backgroundColor: 'rgba(0, 208, 133, 0.5)',
                borderColor: 'rgba(0, 208, 133, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            }
        }
    });
}

/**
 * Met à jour le graphique risque/rendement
 */
function updateRiskReturnChart() {
    const ctx = document.getElementById('risk-return-chart');
    if (!ctx) return;
    
    // Préparer les données
    const data = AppState.filteredBots.slice(0, 50).map(bot => ({
        x: bot.risk_score || 5,
        y: bot.apr_7d_num || 0,
        label: bot.bot_name || bot.pair
    }));
    
    // Détruire le graphique existant
    if (AppState.charts.riskReturn) {
        AppState.charts.riskReturn.destroy();
    }
    
    // Créer le nouveau graphique
    AppState.charts.riskReturn = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Bots',
                data: data,
                backgroundColor: 'rgba(99, 102, 241, 0.5)',
                borderColor: 'rgba(99, 102, 241, 1)',
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Risque (1-10)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'APR 7 jours (%)'
                    }
                }
            }
        }
    });
}

/**
 * Met à jour le graphique par stratégie
 */
function updateStrategyChart() {
    const ctx = document.getElementById('strategy-chart');
    if (!ctx) return;
    
    // Compter les bots par stratégie
    const strategyCounts = {};
    AppState.filteredBots.forEach(bot => {
        strategyCounts[bot.strategy] = (strategyCounts[bot.strategy] || 0) + 1;
    });
    
    // Détruire le graphique existant
    if (AppState.charts.strategy) {
        AppState.charts.strategy.destroy();
    }
    
    // Créer le nouveau graphique
    AppState.charts.strategy = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(strategyCounts),
            datasets: [{
                data: Object.values(strategyCounts),
                backgroundColor: [
                    'rgba(0, 208, 133, 0.7)',
                    'rgba(99, 102, 241, 0.7)',
                    'rgba(239, 68, 68, 0.7)',
                    'rgba(245, 158, 11, 0.7)',
                    'rgba(59, 130, 246, 0.7)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

/**
 * Met à jour le graphique des paires
 */
function updatePairsChart() {
    const ctx = document.getElementById('pairs-chart');
    if (!ctx) return;
    
    // Compter les bots par paire (top 10)
    const pairCounts = {};
    AppState.filteredBots.forEach(bot => {
        pairCounts[bot.pair] = (pairCounts[bot.pair] || 0) + 1;
    });
    
    const sortedPairs = Object.entries(pairCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    // Détruire le graphique existant
    if (AppState.charts.pairs) {
        AppState.charts.pairs.destroy();
    }
    
    // Créer le nouveau graphique
    AppState.charts.pairs = new Chart(ctx, {
        type: 'horizontalBar',
        data: {
            labels: sortedPairs.map(p => p[0]),
            datasets: [{
                label: 'Nombre de bots',
                data: sortedPairs.map(p => p[1]),
                backgroundColor: 'rgba(245, 158, 11, 0.5)',
                borderColor: 'rgba(245, 158, 11, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            }
        }
    });
}

/**
 * Génère la liste des paires disponibles
 */
function generatePairsList() {
    const container = document.getElementById('pairs-list');
    if (!container) return;
    
    // Extraire les paires uniques
    const pairs = [...new Set(AppState.bots.map(bot => bot.pair))].sort();
    
    container.innerHTML = pairs.map(pair => `
        <label class="checkbox-label">
            <input type="checkbox" value="${pair}" onchange="applyFilters()">
            <span>${pair}</span>
        </label>
    `).join('');
}

/**
 * Filtre la liste des paires
 */
function filterPairs(event) {
    const searchTerm = event.target.value.toLowerCase();
    const labels = document.querySelectorAll('#pairs-list .checkbox-label');
    
    labels.forEach(label => {
        const pair = label.querySelector('span').textContent.toLowerCase();
        label.style.display = pair.includes(searchTerm) ? 'flex' : 'none';
    });
}

/**
 * Applique un preset de filtres
 */
function applyPreset(preset) {
    // Réinitialiser d'abord
    resetFilters();
    
    // Mettre à jour les boutons
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    switch (preset) {
        case 'top-performers':
            // Top performers : rendement élevé
            document.getElementById('return-min').value = 5;
            document.getElementById('apr7-min').value = 100;
            break;
            
        case 'safe':
            // Sécurisé : faible risque, longue durée
            document.querySelector('.risk-btn[data-risk="low"]').classList.add('active');
            document.getElementById('duration-min').value = 90;
            document.getElementById('copiers-min').value = 10;
            break;
            
        case 'aggressive':
            // Agressif : haut rendement acceptant plus de risque
            document.getElementById('apr7-min').value = 200;
            document.querySelector('.risk-btn[data-risk="high"]').classList.add('active');
            break;
    }
    
    applyFilters();
}

/**
 * Réinitialise tous les filtres
 */
function resetFilters() {
    // Réinitialiser les checkboxes
    document.querySelectorAll('#strategy-filters input').forEach(cb => cb.checked = true);
    
    // Réinitialiser les inputs
    ['return-min', 'return-max', 'apr7-min', 'apr7-max', 'apr30-min', 'apr30-max', 
     'duration-min', 'copiers-min'].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.value = '';
    });
    
    // Réinitialiser les boutons de risque
    document.querySelectorAll('.risk-btn').forEach(btn => btn.classList.remove('active'));
    
    // Réinitialiser les paires
    document.querySelectorAll('#pairs-list input').forEach(cb => cb.checked = false);
    
    // Réinitialiser les boutons quick
    document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.quick-btn').classList.add('active');
    
    applyFilters();
}

/**
 * Change la vue active
 */
function setView(view) {
    AppState.currentView = view;
    
    // Mettre à jour les boutons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Masquer toutes les vues
    document.querySelectorAll('.view-container').forEach(container => {
        container.classList.add('hidden');
    });
    
    // Afficher la vue sélectionnée
    const viewContainer = document.getElementById(`${view}-view`);
    if (viewContainer) {
        viewContainer.classList.remove('hidden');
    }
    
    // Mettre à jour le contenu
    renderBots();
    if (view === 'analytics') {
        updateCharts();
    }
}

/**
 * Affiche les détails d'un bot
 */
function showBotDetails(botId) {
    const bot = AppState.bots.find(b => b.id === botId);
    if (!bot) return;
    
    const modal = document.getElementById('bot-modal');
    const modalBody = document.getElementById('modal-body');
    
    modalBody.innerHTML = `
        <h2>Détails du Bot</h2>
        <div class="bot-details">
            <div class="detail-section">
                <h3>Informations générales</h3>
                <p><strong>Nom:</strong> ${bot.bot_name || 'N/A'}</p>
                <p><strong>Créateur:</strong> ${bot.creator || bot.username || 'Anonyme'}</p>
                <p><strong>Paire:</strong> ${bot.pair}</p>
                <p><strong>Stratégie:</strong> ${bot.strategy}</p>
            </div>
            
            <div class="detail-section">
                <h3>Performance</h3>
                <p><strong>Rendement 24h:</strong> ${bot.return_24h_num.toFixed(2)}%</p>
                <p><strong>APR 7 jours:</strong> ${bot.apr_7d_num ? bot.apr_7d_num.toFixed(0) + '%' : 'N/A'}</p>
                <p><strong>APR 30 jours:</strong> ${bot.apr_30d_num ? bot.apr_30d_num.toFixed(0) + '%' : 'N/A'}</p>
            </div>
            
            <div class="detail-section">
                <h3>Statistiques</h3>
                <p><strong>Durée:</strong> ${bot.duration || 'N/A'}</p>
                <p><strong>Copieurs:</strong> ${bot.copiers || 0}</p>
                <p><strong>Score de risque:</strong> ${bot.risk_score || 5}/10</p>
                <p><strong>Score composite:</strong> ${bot.compositeScore}/100</p>
            </div>
        </div>
        
        <div class="modal-actions">
            <button class="btn btn-primary" onclick="copyBot(${bot.id})">
                Copier ce bot
            </button>
            <button class="btn" onclick="closeModal()">
                Fermer
            </button>
        </div>
    `;
    
    modal.style.display = 'block';
}

/**
 * Ferme la modal
 */
function closeModal() {
    document.getElementById('bot-modal').style.display = 'none';
}

/**
 * Copie les informations d'un bot
 */
function copyBot(botId) {
    const bot = AppState.bots.find(b => b.id === botId);
    if (!bot) return;
    
    const text = `
Bot: ${bot.bot_name || 'N/A'}
Paire: ${bot.pair}
Stratégie: ${bot.strategy}
Rendement 24h: ${bot.return_24h_num.toFixed(2)}%
APR 7j: ${bot.apr_7d_num ? bot.apr_7d_num.toFixed(0) + '%' : 'N/A'}
APR 30j: ${bot.apr_30d_num ? bot.apr_30d_num.toFixed(0) + '%' : 'N/A'}
    `.trim();
    
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Informations copiées dans le presse-papier!');
    });
}

/**
 * Exporte les données
 */
function exportData() {
    const data = AppState.filteredBots.map(bot => ({
        rang: bot.rank,
        nom: bot.bot_name,
        createur: bot.creator || bot.username,
        paire: bot.pair,
        strategie: bot.strategy,
        rendement_24h: bot.return_24h_num,
        apr_7j: bot.apr_7d_num,
        apr_30j: bot.apr_30d_num,
        duree: bot.duration,
        copieurs: bot.copiers,
        risque: bot.risk_score,
        score_composite: bot.compositeScore
    }));
    
    const csv = convertToCSV(data);
    downloadCSV(csv, 'kucoin_bots_export.csv');
}

/**
 * Convertit les données en CSV
 */
function convertToCSV(data) {
    const headers = Object.keys(data[0]);
    const rows = data.map(obj => headers.map(header => obj[header]));
    
    return [
        headers.join(','),
        ...rows.map(row => row.join(','))
    ].join('\n');
}

/**
 * Télécharge un fichier CSV
 */
function downloadCSV(csv, filename) {
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Actualise les données
 */
function refreshData() {
    loadBots();
    showNotification('Données actualisées!');
}

/**
 * Met à jour les statistiques globales
 */
function updateStats(data) {
    document.getElementById('total-bots').textContent = data.total || AppState.bots.length;
    document.getElementById('last-update').textContent = formatDateTime(data.last_update || new Date());
    
    const statusText = document.getElementById('status-text');
    const statusDot = document.querySelector('.status-dot');
    
    if (data.scraper_status === 'running') {
        statusText.textContent = 'En cours';
        statusDot.style.background = 'var(--warning)';
    } else if (data.is_fallback) {
        statusText.textContent = 'Données de secours';
        statusDot.style.background = 'var(--danger)';
    } else {
        statusText.textContent = 'Actif';
        statusDot.style.background = 'var(--success)';
    }
}

/**
 * Formate une date/heure
 */
function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit'
    });
}

/**
 * Affiche une notification
 */
function showNotification(message, type = 'success') {
    // Créer l'élément de notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Ajouter au body
    document.body.appendChild(notification);
    
    // Animer l'entrée
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Retirer après 3 secondes
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

/**
 * Affiche un indicateur de chargement
 */
function showLoading() {
    const tbody = document.getElementById('bots-tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="11"><div class="spinner"></div></td></tr>';
    }
}

/**
 * Cache l'indicateur de chargement
 */
function hideLoading() {
    // Le chargement est automatiquement caché lors du rendu des bots
}

/**
 * Affiche un message d'erreur
 */
function showError(message) {
    const tbody = document.getElementById('bots-tbody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; padding: 2rem;">
                    <p style="color: var(--danger);">❌ ${message}</p>
                </td>
            </tr>
        `;
    }
    showNotification(message, 'error');
}

/**
 * Démarre la mise à jour automatique
 */
function startAutoUpdate() {
    // Actualiser toutes les 5 minutes
    AppState.updateInterval = setInterval(() => {
        loadBots();
    }, 5 * 60 * 1000);
}

/**
 * Utilitaire de debounce
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Gestion des événements globaux
window.onclick = function(event) {
    if (event.target.className === 'modal') {
        event.target.style.display = 'none';
    }
};

// Style pour les notifications
const style = document.createElement('style');
style.textContent = `
    .notification {
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: var(--radius-md);
        color: white;
        font-weight: 500;
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s;
        z-index: 10000;
    }
    
    .notification.show {
        opacity: 1;
        transform: translateY(0);
    }
    
    .notification-success {
        background: var(--success);
    }
    
    .notification-error {
        background: var(--danger);
    }
    
    .positive {
        color: var(--success);
    }
    
    .negative {
        color: var(--danger);
    }
    
    .bot-info {
        display: flex;
        flex-direction: column;
    }
    
    .bot-name {
        font-weight: 600;
    }
    
    .creator {
        font-size: 0.75rem;
        color: var(--text-secondary);
    }
    
    .btn-action {
        padding: 0.25rem 0.5rem;
        background: var(--bg-hover);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        color: var(--text-primary);
        cursor: pointer;
        margin: 0 0.25rem;
    }
    
    .btn-action:hover {
        background: var(--primary);
        color: var(--bg-primary);
    }
    
    .recommendation-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        padding: 1rem;
        transition: all 0.3s;
    }
    
    .recommendation-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    .recommendation-card h4 {
        margin-bottom: 0.5rem;
        color: var(--primary);
    }
    
    .rec-bot-info {
        margin: 0.5rem 0;
    }
    
    .rec-metrics {
        display: flex;
        gap: 1rem;
        margin: 0.5rem 0;
    }
    
    .rec-reason {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin: 0.5rem 0;
    }
    
    .btn-view-details {
        width: 100%;
        padding: 0.5rem;
        background: var(--primary);
        color: var(--bg-primary);
        border: none;
        border-radius: var(--radius-sm);
        cursor: pointer;
        font-weight: 600;
    }
    
    .btn-view-details:hover {
        background: var(--primary-dark);
    }
    
    .bot-details {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin: 1.5rem 0;
    }
    
    .detail-section h3 {
        color: var(--primary);
        margin-bottom: 0.5rem;
    }
    
    .detail-section p {
        margin: 0.25rem 0;
        color: var(--text-secondary);
    }
    
    .detail-section strong {
        color: var(--text-primary);
    }
    
    .modal-actions {
        display: flex;
        gap: 1rem;
        justify-content: center;
        margin-top: 1.5rem;
    }
    
    .btn-primary {
        background: var(--primary);
        color: var(--bg-primary);
    }
    
    .btn-primary:hover {
        background: var(--primary-dark);
    }
`;
document.head.appendChild(style);
