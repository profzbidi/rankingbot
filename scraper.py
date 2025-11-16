"""
KuCoin Trading Bot Leaderboard Scraper - Version parallélisée
- Résolution problèmes Rebalance et DCA  
- Gestion des caractères spéciaux dans les nombres
- Correction Rebalance 7 jours
- Multithreading pour accélérer le scraping
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class KuCoinMultiStrategyScraper:
    def __init__(self, headless=True, retries=3, wait_time=3):
        self.driver = None
        self.headless = headless
        self.retries = retries
        self.wait_time = wait_time
        self._lock = threading.Lock()
        
        self.strategy_urls = {
            "Grid": "https://www.kucoin.com/fr/trading-bot/spot",
            "Martingale": "https://www.kucoin.com/fr/trading-bot/martingale", 
            "Rebalance": "https://www.kucoin.com/fr/trading-bot/rebalance",
            "Infinity Grid": "https://www.kucoin.com/fr/trading-bot/infinity/grid",
            "DCA": "https://www.kucoin.com/fr/trading-bot/dca"
        }

    def start_driver(self):
        """Démarre Firefox headless"""
        try:
            options = Options()
            options.headless = self.headless
            options.set_preference("permissions.default.image", 2)
            options.set_preference("dom.webnotifications.enabled", False)
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            print("✅ Driver Firefox démarré")
            return True
        except Exception as e:
            print(f"❌ Erreur driver: {e}")
            return False

    def open_strategy_page(self, strategy):
        """Ouvre la page d'une stratégie spécifique"""
        if strategy not in self.strategy_urls:
            print(f"❌ Stratégie inconnue: {strategy}")
            return False
            
        url = self.strategy_urls[strategy]
        print(f"🔍 Chargement {strategy}: {url}")
        self.driver.get(url)
        
        wait = WebDriverWait(self.driver, 20)
        
        try:
            # Attendre que la page soit chargée
            time.sleep(self.wait_time * 2)
            
            # Pour DCA - sélecteur spécifique
            if strategy == "DCA":
                print("🔄 Tentative de sélecteur DCA...")
                dca_selectors = [
                    "//div[contains(@class, 'automaticinverst-ranking-tab')]",
                    "//div[@role='tab']//div[contains(text(), 'Classement')]"
                ]
                
                for selector in dca_selectors:
                    try:
                        ranking_tab = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        self.driver.execute_script("arguments[0].click();", ranking_tab)
                        print(f"✅ DCA - Onglet Classement cliqué: {selector}")
                        break
                    except Exception as e:
                        print(f"⚠️ Sélecteur DCA échoué {selector}: {e}")
                        continue
                else:
                    print("❌ DCA - Aucun sélecteur d'onglet trouvé")
                    return False
                    
                # Attendre le chargement du contenu DCA
                time.sleep(self.wait_time * 3)
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'automaticinverst-rankinglist')]")))
                    print("✅ DCA - Contenu ranking chargé")
                except Exception as e:
                    print(f"⚠️ DCA - Contenu ranking non détecté: {e}")
            
            else:
                # Pour les autres stratégies, utiliser le sélecteur standard
                ranking_tab_xpaths = [
                    "//div[@role='tab']//div[contains(text(),'Classement')]",
                    "//div[contains(@class, 'smarttrade-ranking-tab')]",
                    "//div[contains(text(), 'Classement')]"
                ]
                
                ranking_tab = None
                for xpath in ranking_tab_xpaths:
                    try:
                        ranking_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                        break
                    except:
                        continue
                
                if ranking_tab:
                    self.driver.execute_script("arguments[0].click();", ranking_tab)
                    print(f"✅ {strategy} - Onglet Classement cliqué")
                else:
                    print(f"⚠️ {strategy} - Onglet Classement non trouvé, continuation...")
            
            time.sleep(self.wait_time * 2)
            
            # Vérifier que le contenu est chargé selon la stratégie
            if strategy == "Rebalance":
                content_loaded = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'smarttrade-rankinglist')]")))
            elif strategy == "DCA":
                content_loaded = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'automaticinverst-rankinglist')]")))
            else:
                # Pour Grid, Martingale, Infinity Grid
                content_selectors = [
                    "//div[contains(@class, 'leaderBoard-content')]",
                    "//div[contains(@class, 'rankinglist')]",
                    "//div[contains(@class, 'rankItem-')]"
                ]
                for selector in content_selectors:
                    try:
                        content_loaded = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                        break
                    except:
                        continue

            print(f"✅ {strategy} - Page chargée")
            return True
            
        except Exception as e:
            print(f"❌ Erreur chargement {strategy}: {e}")
            return False

    def switch_period_tab(self, strategy, period="24h"):
        """Change entre les périodes selon la stratégie - Version corrigée pour Rebalance"""
        try:
            wait = WebDriverWait(self.driver, 15)
            
            if period == "24h":
                if strategy == "DCA":
                    print("ℹ️  DCA n'a pas de classement 24h")
                    return False
                tab_name = "Bénéfices journaliers"
            else:
                tab_name = "Bénéfices sur 7 jours" if strategy != "DCA" else "Bénéfices sur 7 jours"
            
            print(f"🔄 Changement vers: {tab_name}")
            
            # Sélecteurs adaptés à chaque stratégie - version améliorée pour Rebalance
            if strategy == "Rebalance":
                tab_selectors = [
                    f"//div[@role='tab' and contains(., '{tab_name}')]",
                    f"//div[contains(@class, 'KuxTab-TabItem') and contains(., '{tab_name}')]",
                    f"//div[contains(text(), '{tab_name}')]"
                ]
            else:
                tab_selectors = [
                    f"//div[contains(@class, 'e1fugzh511') and contains(., '{tab_name}')]",
                    f"//div[@role='tab' and contains(., '{tab_name}')]",
                ]
            
            tab = None
            for selector in tab_selectors:
                try:
                    tab = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except:
                    continue
            
            if not tab:
                print(f"❌ Onglet {tab_name} non trouvé pour {strategy}")
                return False
            
            self.driver.execute_script("arguments[0].click();", tab)
            
            # Attendre que le contenu se charge - important pour Rebalance
            time.sleep(self.wait_time * 2)
            
            # Vérifier que le changement a bien eu lieu
            if strategy == "Rebalance":
                try:
                    if period == "24h":
                        expected_header = "Rendement sur 24h"
                    else:
                        expected_header = "APR sur 7 jours"
                    
                    header_xpath = f"//div[contains(@class, 'lrtcss-mgz5l9') and contains(., '{expected_header}')]"
                    wait.until(EC.presence_of_element_located((By.XPATH, header_xpath)))
                    print(f"✅ En-tête {expected_header} détecté pour Rebalance")
                except Exception as e:
                    print(f"⚠️ En-tête non détecté après changement d'onglet: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur changement onglet {period}: {e}")
            return False

    def get_active_table_rows(self, strategy, period="24h"):
        """Récupère les lignes du tableau selon la stratégie - Version corrigée pour Rebalance"""
        try:
            # Approche robuste de l'ancienne version : trouver l'en-tête puis le conteneur
            if strategy == "Rebalance":
                # Structure spécifique pour Rebalance - CORRECTION
                if period == "24h":
                    # Pour 24h, chercher l'en-tête "Rendement sur 24h"
                    header_text = "Rendement sur 24h"
                else:
                    # Pour 7j, chercher l'en-tête "APR sur 7 jours"  
                    header_text = "APR sur 7 jours"
                
                # Chercher l'en-tête du tableau Rebalance
                header_selectors = [
                    f"//div[contains(@class, 'lrtcss-mgz5l9') and contains(., '{header_text}')]",
                    f"//div[contains(., '{header_text}')]"
                ]
                
                header = None
                for selector in header_selectors:
                    try:
                        header = self.driver.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
                
                if not header:
                    print(f"⚠️ En-tête '{header_text}' non trouvé pour Rebalance {period}")
                    # Fallback : chercher les lignes directement
                    rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rankItem-')]")
                    return rows
                
                # Remonter au conteneur parent du tableau Rebalance
                table_container_selectors = [
                    "./ancestor::div[contains(@class, 'tab-slide')][1]",
                    "./ancestor::div[contains(@class, 'smarttrade-rankinglist')][1]",
                    "./ancestor::div[contains(@class, 'leaderBoard-content')][1]"
                ]
                
                table_container = None
                for selector in table_container_selectors:
                    try:
                        table_container = header.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
                
                if not table_container:
                    print(f"⚠️ Conteneur tableau Rebalance non trouvé pour {period}")
                    # Fallback : chercher les lignes directement
                    rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rankItem-')]")
                    return rows
                
                # Extraire les lignes du conteneur
                rows = table_container.find_elements(By.XPATH, ".//div[contains(@class, 'rankItem-')]")
                return rows
                
            elif strategy == "DCA":
                # Structure spécifique pour DCA
                rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'automaticinverst-rankinglist')]//div[contains(@class, 'rankItem-')]")
                return rows
                
            else:
                # Structure standard pour Grid, Martingale, Infinity Grid - APPROCHE ROBUSTE
                if period == "24h":
                    header_text = "Rendement sur 24h"
                else:
                    header_text = "APR sur 7 jours"
                
                # Chercher l'en-tête du tableau
                header_selectors = [
                    f"//div[contains(@class, 'lrtcss-1ul72f') and contains(., '{header_text}')]",
                    f"//div[contains(., '{header_text}')]"
                ]
                
                header = None
                for selector in header_selectors:
                    try:
                        header = self.driver.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
                
                if not header:
                    print(f"⚠️ En-tête '{header_text}' non trouvé pour {strategy}")
                    # Fallback : chercher les lignes directement
                    rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rankItem-')]")
                    return rows
                
                # Remonter au conteneur du tableau
                table_container_selectors = [
                    "./ancestor::div[contains(@class, 'tab-slide')][1]",
                    "./ancestor::div[contains(@class, 'leaderBoard-content')][1]",
                    "./ancestor::div[contains(@class, 'rankinglist')][1]"
                ]
                
                table_container = None
                for selector in table_container_selectors:
                    try:
                        table_container = header.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
                
                if not table_container:
                    print(f"⚠️ Conteneur tableau non trouvé pour {strategy}")
                    # Fallback : chercher les lignes directement
                    rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rankItem-')]")
                    return rows
                
                # Extraire les lignes du conteneur
                rows = table_container.find_elements(By.XPATH, ".//div[contains(@class, 'rankItem-')]")
                return rows
                
        except Exception as e:
            print(f"❌ Erreur recherche tableau {strategy} {period}: {e}")
            # Fallback final
            try:
                rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rankItem-')]")
                return rows
            except:
                return []

    def extract_bot_data(self, row, strategy, period="24h"):
        """Extrait les données selon la structure de la stratégie"""
        try:
            # Extraire le rang (commun à toutes les stratégies)
            rank_selectors = [
                ".//div[contains(@class, 'num')]//em",
                ".//em"
            ]
            
            rank_element = None
            for selector in rank_selectors:
                try:
                    rank_element = row.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if not rank_element:
                return None
                
            rank_text = rank_element.text.strip()
            if not rank_text:
                return None
            rank = int(rank_text)
            
            if strategy == "Rebalance":
                # Structure spécifique Rebalance
                user_pair_section = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-13h0cp0')]")
                content_div = user_pair_section.find_elements(By.XPATH, "./div")[1]
                
                # Paire est dans le premier div
                pair = content_div.find_element(By.XPATH, "./div[1]").text.strip()
                
                # Durée et utilisateur sont dans le deuxième div
                duration_user = content_div.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-99oq02')]").text.strip()
                
                # Séparer durée et utilisateur
                if "|" in duration_user:
                    duration_part, username = duration_user.split("|", 1)
                    duration = duration_part.strip()
                    username = username.strip()
                else:
                    duration = duration_user
                    username = "N/A"
                
                # Valeur
                value_element = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-mgz5l9')]//span")
                
            elif strategy == "DCA":
                # Structure spécifique DCA
                user_pair_section = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1o2nlwk')]")
                content_div = user_pair_section.find_elements(By.XPATH, "./div")[1]
                username_elements = content_div.find_elements(By.XPATH, "./div")
                
                username = username_elements[0].text.strip() if len(username_elements) > 0 else "N/A"
                pair_element = content_div.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-99oq02')]")
                pair = pair_element.text.strip()
                
                duration_element = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1egv4bd')]")
                duration = duration_element.text.strip()
                
                value_element = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1ul72f')]//span")
                
            else:
                # Structure standard pour Grid, Martingale, Infinity Grid
                user_pair_section = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1o2nlwk')]")
                content_div = user_pair_section.find_elements(By.XPATH, "./div")[1]
                username_elements = content_div.find_elements(By.XPATH, "./div")
                
                username = username_elements[0].text.strip() if len(username_elements) > 0 else "N/A"
                pair_element = content_div.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-99oq02')]")
                pair = pair_element.text.strip()
                
                duration_element = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1egv4bd')]")
                duration = duration_element.text.strip()
                
                value_element = row.find_element(By.XPATH, ".//div[contains(@class, 'lrtcss-1ul72f')]//span")
            
            # Extraire la valeur numérique - CORRECTION CARACTÈRES SPÉCIAUX
            value_text = value_element.text.strip()
            # Nettoyer la valeur : supprimer +, %, espaces, espaces insécables, et remplacer virgules
            value_text = value_text.replace("+", "").replace("%", "").replace(" ", "").replace(" ", "").replace(",", ".")
            if not value_text:
                return None
            
            # Gérer les cas où la valeur pourrait être vide ou non numérique
            try:
                value_num = float(value_text)
            except ValueError as e:
                print(f"⚠️ Erreur conversion valeur '{value_text}': {e}")
                return None
            
            bot_data = {
                "rank": rank,
                "username": username,
                "pair": pair,
                "duration": duration,
                "return_24h": value_num if period == "24h" else None,
                "apr_7d": value_num if period == "7d" else None,
                "strategy": strategy
            }
            
            value_display = bot_data['return_24h'] or bot_data['apr_7d']
            print(f"  ✅ {strategy} - Rang {rank}: {username} - {pair} - {value_display}%")
            return bot_data
            
        except Exception as e:
            print(f"⚠️ Erreur extraction {strategy}: {e}")
            return None

    def scrape_ranking(self, strategy, top_n=10, period="24h"):
        """Scrape le classement pour une stratégie"""
        print(f"📈 Extraction {strategy} - {period}...")
        
        if not self.switch_period_tab(strategy, period):
            print(f"❌ Impossible de changer vers {period} pour {strategy}")
            return []
        
        time.sleep(2)
        
        bots = []
        rows = self.get_active_table_rows(strategy, period)
        
        for i, row in enumerate(rows[:top_n]):
            bot_data = self.extract_bot_data(row, strategy, period)
            if bot_data:
                bots.append(bot_data)
        
        print(f"✅ {len(bots)} bots {strategy} - {period} récupérés")
        return bots

    def scrape_strategy(self, strategy, top_n=10):
        """Scrape toutes les données pour une stratégie"""
        print(f"\n🎯 Début du scraping pour: {strategy}")
        
        if not self.open_strategy_page(strategy):
            return {"24h": [], "7d": []}
        
        data = {"24h": [], "7d": []}
        
        # Scraper selon les périodes disponibles
        if strategy != "DCA":  # DCA n'a pas de 24h
            data["24h"] = self.scrape_ranking(strategy, top_n=top_n, period="24h")
        
        data["7d"] = self.scrape_ranking(strategy, top_n=top_n, period="7d")
        
        print(f"🎯 {strategy} terminé: {len(data['24h'])} bots 24h, {len(data['7d'])} bots 7j")
        return data

    def close(self):
        if self.driver:
            self.driver.quit()
            print("✅ Driver fermé")


def scrape_single_strategy(strategy, top_n=10):
    """
    Fonction pour scraper une seule stratégie dans un thread séparé
    Chaque thread a son propre driver Selenium
    """
    print(f"🧵 Lancement du thread pour {strategy}")
    
    scraper = KuCoinMultiStrategyScraper(headless=True, retries=3, wait_time=2)
    if not scraper.start_driver():
        return {"24h": [], "7d": []}
    
    try:
        strategy_data = scraper.scrape_strategy(strategy, top_n=top_n)
        return strategy_data
    except Exception as e:
        print(f"❌ Erreur dans le thread {strategy}: {e}")
        return {"24h": [], "7d": []}
    finally:
        scraper.close()


def scrape_kucoin_data_parallel(top_n=10, max_workers=5):
    """
    Fonction principale parallélisée - compatible avec l'application existante
    """
    print("🚀 Démarrage du scraping PARALLÉLISÉ...")
    start_time = time.time()
    
    strategies = ["Grid", "Martingale", "Rebalance", "Infinity Grid", "DCA"]
    all_data = {"24h": [], "7d": []}
    
    # Utiliser ThreadPoolExecutor pour le parallélisme
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Lancer tous les scrapings en parallèle
        future_to_strategy = {
            executor.submit(scrape_single_strategy, strategy, top_n): strategy 
            for strategy in strategies
        }
        
        # Collecter les résultats au fur et à mesure
        for future in as_completed(future_to_strategy):
            strategy = future_to_strategy[future]
            try:
                strategy_data = future.result()
                all_data["24h"].extend(strategy_data["24h"])
                all_data["7d"].extend(strategy_data["7d"])
                print(f"✅ {strategy} - Données récupérées avec succès")
            except Exception as e:
                print(f"❌ Erreur pour {strategy}: {e}")
    
    # Statistiques finales
    total_bots = len(all_data["24h"]) + len(all_data["7d"])
    elapsed_time = time.time() - start_time
    print(f"\n📊 RÉSUMÉ PARALLÈLE: {total_bots} bots sur {len(strategies)} stratégies en {elapsed_time:.2f} secondes")
    
    # Ajouter hot_pairs vide pour compatibilité
    all_data["hot_pairs"] = []
    return all_data


def scrape_kucoin_data(top_n=10):
    """
    Fonction principale - choisit automatiquement entre version parallèle et séquentielle
    """
    # Utiliser la version parallélisée par défaut
    return scrape_kucoin_data_parallel(top_n=top_n, max_workers=5)


if __name__ == "__main__":
    top_n = 10
    
    print("🧪 TEST DE PERFORMANCE - Version parallélisée vs séquentielle")
    
    # Test version parallélisée
    print("\n" + "="*50)
    print("🚀 VERSION PARALLÉLISÉE")
    print("="*50)
    start_time = time.time()
    data_parallel = scrape_kucoin_data_parallel(top_n=top_n, max_workers=5)
    parallel_time = time.time() - start_time
    
    print(f"\n⏱️  Temps version parallélisée: {parallel_time:.2f} secondes")
    
    # Sauvegarde JSON
    with open("kucoin_bots_ranking_parallel.json", "w", encoding="utf-8") as f:
        json.dump(data_parallel, f, indent=2, ensure_ascii=False)
    print(f"💾 Données sauvegardées dans kucoin_bots_ranking_parallel.json")