"""
KuCoin Bot Trading Dashboard - Application Flask Optimisée
Version avec interface d'analyse avancée
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime, timedelta
import threading
import time
from pathlib import Path
import sys

# Configuration
app = Flask(__name__)
CORS(app)

DATABASE = 'kucoin_bots.db'
SCRAPER_INTERVAL = 3600  # Scraper toutes les heures
USE_MODERN_UI = True  # Utiliser l'interface moderne

# =======================
# DATABASE MANAGEMENT
# =======================

def init_db():
    """Initialise la base de données avec structure étendue"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Table principale des bots
    c.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rank INTEGER,
            bot_name TEXT,
            creator TEXT,
            pair TEXT,
            strategy TEXT,
            return_24h REAL,
            apr_7d REAL,
            apr_30d REAL,
            duration TEXT,
            duration_days INTEGER,
            copiers INTEGER,
            investment_min INTEGER,
            grid_range TEXT,
            risk_score REAL,
            scraped_at TIMESTAMP,
            UNIQUE(bot_name, pair, strategy, scraped_at)
        )
    ''')
    
    # Migration : Ajouter la colonne 'duration' si elle n'existe pas
    c.execute("PRAGMA table_info(bots)")
    columns = [col[1] for col in c.fetchall()]
    if 'duration' not in columns:
        print("📝 Migration : Ajout de la colonne 'duration'...")
        c.execute("ALTER TABLE bots ADD COLUMN duration TEXT")
        print("✅ Colonne 'duration' ajoutée !")
    
    # Table de statut du scraper
    c.execute('''
        CREATE TABLE IF NOT EXISTS scraper_status (
            id INTEGER PRIMARY KEY,
            last_scrape TIMESTAMP,
            status TEXT,
            total_bots INTEGER,
            message TEXT,
            is_fallback BOOLEAN DEFAULT 0
        )
    ''')
    
    # Initialiser le statut si n'existe pas
    c.execute('SELECT COUNT(*) FROM scraper_status')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO scraper_status (id, last_scrape, status, total_bots, message, is_fallback)
            VALUES (1, ?, 'idle', 0, 'En attente du premier scraping', 0)
        ''', (datetime.now(),))
    
    conn.commit()
    conn.close()
    print("✅ Base de données initialisée avec succès")

def get_db_connection():
    """Crée une connexion à la base de données"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# =======================
# DATA PROCESSING - AMÉLIORATIONS
# =======================

def calculate_risk_score(bot):
    """Calcule un score de risque pour un bot"""
    try:
        # Facteurs de risque
        volatility = abs(float(bot.get('return_24h', 0))) * 0.3
        duration_factor = min(int(bot.get('duration_days', 1)), 365) / 365
        copiers_factor = min(int(bot.get('copiers', 0)), 1000) / 1000
        
        # Score inversé (plus c'est stable, moins c'est risqué)
        risk = max(1, min(10, 10 - (duration_factor * 5 + copiers_factor * 3 - volatility)))
        return round(risk, 1)
    except:
        return 5.0

def calculate_missing_returns(bot):
    """Calcule les valeurs manquantes de façon intelligente"""
    try:
        return_24h = bot.get('return_24h')
        apr_7d = bot.get('apr_7d')
        apr_30d = bot.get('apr_30d')
        
        # Si ROI 7j manquant mais ROI 24h présent
        if (not apr_7d or apr_7d == 0) and return_24h:
            stability_factor = min(bot.get('duration_days', 1) / 30, 1.0)
            copiers_factor = min(bot.get('copiers', 0) / 100, 1.0)
            volatility_adjustment = 0.85 + (stability_factor * 0.3)
            calculated_7d = return_24h * 7 * volatility_adjustment
            bot['apr_7d'] = round(calculated_7d, 2)
            bot['calculated_7d'] = True
        
        # Si ROI 24h manquant mais ROI 7j présent
        if (not return_24h or return_24h == 0) and apr_7d:
            recent_performance_factor = 1.1
            calculated_24h = (apr_7d / 7) * recent_performance_factor
            bot['return_24h'] = round(calculated_24h, 2)
            bot['calculated_24h'] = True
        
        return bot
    except Exception as e:
        print(f"⚠️ Erreur calcul valeurs manquantes: {e}")
        return bot

def enhance_bot_data(bots_data):
    """Améliore les données des bots avec des calculs intelligents"""
    enhanced_bots = []
    
    for bot in bots_data:
        try:
            # Calcul des valeurs manquantes
            bot = calculate_missing_returns(bot)
            
            # Calcul du score de risque
            bot['risk_score'] = calculate_risk_score(bot)
            
            enhanced_bots.append(bot)
        except Exception as e:
            print(f"⚠️ Erreur amélioration bot: {e}")
            enhanced_bots.append(bot)
    
    return enhanced_bots

def save_bots_to_db(bots_data, is_fallback=False):
    """Sauvegarde les bots avec le schéma existant - VERSION COMPLÈTEMENT CORRIGÉE"""
    if not bots_data:
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    scraped_at = datetime.now()
    
    # Nettoyer les anciennes données
    c.execute('DELETE FROM bots WHERE scraped_at < ?', 
              (scraped_at - timedelta(days=7),))
    
    # Améliorer les données avec calculs intelligents
    enhanced_bots = enhance_bot_data(bots_data)
    
    for bot in enhanced_bots:
        try:
            # CORRECTION : Parser correctement la durée depuis le scraper
            duration_str = bot.get('duration', '0j')
            duration_days = parse_duration_from_scraper(duration_str)
            
            # Vérifier quelles colonnes existent dans la base
            c.execute("PRAGMA table_info(bots)")
            columns = [col[1] for col in c.fetchall()]
            
            # Champs de base
            fields = ['rank', 'bot_name', 'pair', 'strategy', 'return_24h', 'apr_7d', 'scraped_at']
            values = [
                bot.get('rank', 0),
                bot.get('bot_name', f"Bot_{bot.get('rank', 0)}"),
                bot.get('pair', 'USDT'),
                bot.get('strategy', 'Grid'),
                float(bot.get('return_24h', 0)),
                float(bot.get('apr_7d', 0)),
                scraped_at
            ]
            
            # Champs optionnels - AVEC DURÉE CORRECTE
            optional_fields = {
                'duration': duration_str,
                'duration_days': duration_days,
                'copiers': bot.get('copiers', 0),
                'investment_min': bot.get('investment_min', 100),
                'risk_score': bot.get('risk_score', 5.0),
                'apr_30d': bot.get('apr_30d', 0)
            }
            
            for field, value in optional_fields.items():
                if field in columns:
                    fields.append(field)
                    values.append(value)
            
            # Construction dynamique de la requête
            placeholders = ','.join(['?' for _ in values])
            field_names = ','.join(fields)
            
            query = f'INSERT OR REPLACE INTO bots ({field_names}) VALUES ({placeholders})'
            c.execute(query, values)
            
        except Exception as e:
            print(f"⚠️ Erreur insertion bot: {e}")
            continue
    
    # Mettre à jour le statut
    c.execute('''
        UPDATE scraper_status 
        SET last_scrape = ?, status = 'success', total_bots = ?, 
            message = ?, is_fallback = ?
        WHERE id = 1
    ''', (scraped_at, len(enhanced_bots), 
          f"{'Données simulées' if is_fallback else 'Données réelles'} - {len(enhanced_bots)} bots", 
          is_fallback))
    
    conn.commit()
    conn.close()
    print(f"✅ {len(enhanced_bots)} bots sauvegardés dans la base de données")

def parse_duration_from_scraper(duration_str):
    """Parse la durée du format KuCoin (ex: '1388D 20H 13M') en jours - VERSION CORRIGÉE"""
    try:
        # Cas spécial pour "0j" et formats vides
        if not duration_str or duration_str == '0j':
            return 0
        
        total_days = 0
        
        # Extraire les jours
        if 'D' in duration_str:
            days_part = duration_str.split('D')[0]
            # Nettoyer la partie jours (enlever les espaces, etc.)
            days_part = ''.join(filter(str.isdigit, days_part))
            if days_part:
                total_days += int(days_part)
        
        # Extraire les heures si présentes
        if 'H' in duration_str:
            # Prendre la partie après 'D' si elle existe, sinon toute la string
            hours_part = duration_str.split('D')[1] if 'D' in duration_str else duration_str
            hours_part = hours_part.split('H')[0].strip()
            # Nettoyer la partie heures
            hours_part = ''.join(filter(str.isdigit, hours_part))
            if hours_part:
                total_days += int(hours_part) / 24
        
        # Extraire les minutes si présentes
        if 'M' in duration_str:
            # Prendre la partie après 'H' si elle existe, sinon après 'D', sinon toute la string
            if 'H' in duration_str:
                minutes_part = duration_str.split('H')[1]
            elif 'D' in duration_str:
                minutes_part = duration_str.split('D')[1]
            else:
                minutes_part = duration_str
            minutes_part = minutes_part.split('M')[0].strip()
            # Nettoyer la partie minutes
            minutes_part = ''.join(filter(str.isdigit, minutes_part))
            if minutes_part:
                total_days += int(minutes_part) / (24 * 60)
                
        return total_days
    except Exception as e:
        print(f"⚠️ Erreur parsing durée '{duration_str}': {e}")
        return 0
        
# =======================
# SCRAPER INTEGRATION
# =======================

def run_scraper():
    """Lance le scraper principal - VERSION AMÉLIORÉE"""
    try:
        print(f"⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Lancement du scraping...")
        
        # Utiliser le scraper fonctionnel
        from scraper import scrape_kucoin_data
        
        data = scrape_kucoin_data(top_n=10)
        
        # Adapter les données au format attendu par la base
        all_bots = []
        for period in ['24h', '7d']:
            for bot in data.get(period, []):
                try:
                    # Convertir la durée en jours si nécessaire
                    duration_str = bot.get('duration', '0j')
                    duration_days = parse_duration_from_scraper(duration_str)
                    
                    # Gérer les valeurs None
                    return_24h = bot.get('return_24h')
                    apr_7d = bot.get('apr_7d')
                    
                    adapted_bot = {
                        'rank': bot.get('rank', 0),
                        'bot_name': bot.get('username', 'N/A'),
                        'pair': bot.get('pair', 'USDT'),
                        'strategy': bot.get('strategy', 'Grid'),
                        'return_24h': float(return_24h) if return_24h is not None else 0.0,
                        'apr_7d': float(apr_7d) if apr_7d is not None else 0.0,
                        'duration': bot.get('duration', '0j'),
                        'duration_days': duration_days,
                        'copiers': bot.get('copiers', 0),
                        'investment_min': bot.get('investment_min', 100)
                    }
                    all_bots.append(adapted_bot)
                except Exception as e:
                    print(f"⚠️ Erreur adaptation bot: {e}")
                    continue
        
        if all_bots:
            save_bots_to_db(all_bots, is_fallback=False)
            print(f"✅ Scraping terminé avec succès - {len(all_bots)} bots récupérés")
            return True
        else:
            print("⚠️ Aucune donnée récupérée par le scraping")
            return False
            
    except Exception as e:
        print(f"❌ Erreur scraper: {e}")
        return False

def generate_fallback_data():
    """Génère des données de test réalistes"""
    import random
    
    print("📊 Génération de données fallback...")
    
    strategies = ["Grid", "DCA", "Smart Rebalance", "Martingale", "Infinity Grid"]
    pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    
    bots = []
    for i in range(1, 71):
        strategy = random.choice(strategies)
        
        # Générer des performances cohérentes
        base_perf = random.uniform(-2, 15)
        
        bot = {
            "rank": i,
            "bot_name": f"Bot_{strategy.replace(' ', '_')}_{i:03d}",
            "creator": f"Trader_{random.randint(100, 999)}",
            "strategy": strategy,
            "pair": random.choice(pairs),
            "duration_days": random.randint(1, 365),
            "return_24h": round(base_perf + random.uniform(-2, 2), 2),
            "apr_7d": round(base_perf * 7 + random.uniform(-5, 5), 2),
            "apr_30d": round(base_perf * 30 + random.uniform(-10, 10), 2),
            "investment_min": random.choice([10, 50, 100, 200, 500]),
            "copiers": random.randint(0, 5000),
            "grid_range": f"{random.randint(5, 30)}%" if "Grid" in strategy else None
        }
        bots.append(bot)
    
    save_bots_to_db(bots, is_fallback=True)
    print(f"✅ {len(bots)} bots fallback générés")

def scraper_loop():
    """Boucle du scraper - VERSION AMÉLIORÉE"""
    first_run = True
    
    while True:
        try:
            success = run_scraper()
            
            if not success and first_run:
                print("📊 Premier scraping échoué, génération de données d'exemple...")
                generate_fallback_data()
                first_run = False
                
        except Exception as e:
            print(f"❌ Erreur dans la boucle scraper: {e}")
            
            if first_run:
                print("📊 Erreur lors du premier scraping, génération de données d'exemple...")
                generate_fallback_data()
                first_run = False
        
        print(f"⏳ Prochaine mise à jour dans {SCRAPER_INTERVAL // 60} minutes...")
        time.sleep(SCRAPER_INTERVAL)
        first_run = False  # Après le premier cycle, on ne génère plus de fallback

# =======================
# API ROUTES AMÉLIORÉES
# =======================

@app.route('/api/bots')
def api_bots():
    """API pour récupérer les bots avec filtres avancés - VERSION AMÉLIORÉE"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Paramètres de requête
    strategy = request.args.get('strategy', 'all')
    ranking_type = request.args.get('ranking_type', '24h')
    limit = int(request.args.get('limit', 100))
    
    # Construire la requête SQL
    query = '''
        SELECT * FROM bots 
        WHERE scraped_at = (SELECT MAX(scraped_at) FROM bots)
    '''
    
    params = []
    
    # Filtre par stratégie
    if strategy != 'all':
        query += ' AND strategy = ?'
        params.append(strategy)
    
    # Tri selon le type de ranking
    order_map = {
        '24h': 'return_24h DESC',
        '7d': 'apr_7d DESC',
        '30d': 'apr_30d DESC',
        'duration': 'duration_days DESC',
        'copiers': 'copiers DESC',
        'risk': 'risk_score ASC',
        'score': '(return_24h * 0.35 + apr_7d * 0.4 + duration_days * 0.15 + copiers * 0.1) DESC'
    }
    
    query += f' ORDER BY {order_map.get(ranking_type, "return_24h DESC")}'
    query += ' LIMIT ?'
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    
    # Convertir en JSON
    bots = []
    for row in rows:
        bot = dict(row)
        bot['scraped_at'] = str(bot['scraped_at'])
        bots.append(bot)
    
    conn.close()
    
    return jsonify({
        'success': True,
        'count': len(bots),
        'bots': bots,
        'filters': {
            'strategy': strategy,
            'ranking_type': ranking_type,
            'limit': limit
        }
    })

@app.route('/api/status')
def api_status():
    """Retourne le statut du scraper"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT * FROM scraper_status WHERE id = 1')
    row = c.fetchone()
    
    if row:
        status = dict(row)
        
        # Calculer le temps depuis le dernier scrape
        last_scrape = datetime.fromisoformat(str(status['last_scrape']))
        time_since = (datetime.now() - last_scrape).total_seconds()
        
        status['last_scrape'] = str(last_scrape)
        status['time_since_minutes'] = int(time_since / 60)
        status['next_scrape_minutes'] = max(0, int((SCRAPER_INTERVAL - time_since) / 60))
    else:
        status = {
            'status': 'error',
            'message': 'Statut non disponible'
        }
    
    conn.close()
    return jsonify(status)

@app.route('/api/strategies')
def api_strategies():
    """Retourne les stratégies disponibles"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT DISTINCT strategy FROM bots WHERE strategy IS NOT NULL')
    strategies = [row[0] for row in c.fetchall()]
    
    conn.close()
    return jsonify(strategies)

@app.route('/api/metrics')
def api_metrics():
    """Retourne des métriques agrégées"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Métriques globales
    c.execute('''
        SELECT 
            COUNT(*) as total_bots,
            AVG(return_24h) as avg_roi_24h,
            AVG(apr_7d) as avg_roi_7d,
            AVG(risk_score) as avg_risk,
            MAX(return_24h) as max_roi_24h,
            MAX(copiers) as max_copiers
        FROM bots 
        WHERE scraped_at = (SELECT MAX(scraped_at) FROM bots)
    ''')
    
    metrics = dict(c.fetchone())
    
    conn.close()
    return jsonify(metrics)

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Force un nouveau scraping"""
    threading.Thread(target=run_scraper, daemon=True).start()
    return jsonify({'success': True, 'message': 'Scraping lancé en arrière-plan'})

# =======================
# WEB ROUTES
# =======================

@app.route('/')
def index():
    """Page principale avec nouveau dashboard optimisé"""
    return render_template('dashboard.html')

@app.route('/analyzer')
def analyzer():
    """Ancienne interface d'analyse (conservée pour compatibilité)"""
    return render_template('analyzer.html')

@app.route('/classic')
def classic():
    """Ancienne interface classique"""
    return render_template('index.html')

@app.route('/modern')
def modern():
    """Ancienne interface moderne"""
    return render_template('index_modern.html')

@app.route('/admin')
def admin():
    """Page d'administration"""
    return render_template('admin.html')



# =======================
# ERROR HANDLERS
# =======================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint non trouvé'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Erreur serveur interne'}), 500

# =======================
# MAIN - VERSION SANS FALLBACK AUTOMATIQUE
# =======================

if __name__ == '__main__':
    print("="*70)
    print("🚀 KUCOIN BOT TRADING DASHBOARD - ANALYZER EDITION")
    print("="*70)
    
    # Initialiser la base de données
    init_db()
    
    # Vérifier si on a des données
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM bots')
    bot_count = c.fetchone()[0]
    conn.close()
    
    if bot_count == 0:
        print("📊 Base de données vide, lancement immédiat du scraping...")
        # Lancer le scraping immédiatement au lieu de générer des fallbacks
        try:
            run_scraper()
        except Exception as e:
            print(f"❌ Erreur lors du scraping initial: {e}")
            print("📊 Génération de données d'exemple en attendant le prochain scraping...")
            generate_fallback_data()
    else:
        print(f"✅ {bot_count} bots trouvés dans la base de données")
    
    # Lancer le scraper en arrière-plan
    print("🤖 Démarrage du scraper en arrière-plan...")
    scraper_thread = threading.Thread(target=scraper_loop, daemon=True)
    scraper_thread.start()
    
    # Informations de démarrage
    print("\n" + "="*70)
    print("✨ Application démarrée avec succès!")
    print("="*70)
    print("\n📍 ACCÈS:")
    print("   🎯 Nouvel Analyzer: http://localhost:5000")
    print("   📊 Interface Classique: http://localhost:5000/classic")
    print("   ⚙️  Admin: http://localhost:5000/admin")
    print("   📈 Analytics: http://localhost:5000/analytics")
    print("\n🔌 API ENDPOINTS:")
    print("   GET  /api/bots       - Liste des bots avec scoring")
    print("   GET  /api/status     - Statut du scraper")
    print("   GET  /api/strategies - Stratégies disponibles")
    print("   GET  /api/metrics    - Métriques globales")
    print("   POST /api/scrape     - Forcer un scraping")
    print("\n" + "="*70)
    
    # Lancer Flask
    app.run(
        debug=False,
        host='0.0.0.0',
        port=5000,
        use_reloader=False
    )