#!/usr/bin/env python3
"""
Script de lancement unifié pour KuCoin Bot Dashboard
Version avec scraping immédiat
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def wait_for_scraper(max_wait=120):
    """Attend que le scraper ait terminé son premier cycle"""
    print("⏳ Attente du premier scraping...")
    
    for i in range(max_wait):
        # Vérifier si la base contient des données
        try:
            import sqlite3
            conn = sqlite3.connect('kucoin_bots.db')
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM bots')
            count = c.fetchone()[0]
            conn.close()
            
            if count > 0:
                print(f"✅ {count} bots trouvés dans la base de données")
                return True
        except:
            pass
        
        if i % 10 == 0:  # Afficher un message toutes les 10 secondes
            print(f"⏱️  Attente... ({i}s/{max_wait}s)")
        
        time.sleep(1)
    
    print("⚠️  Timeout - Le scraping prend plus de temps que prévu")
    return False

def main():
    # Activer l'environnement virtuel si nécessaire
    venv_path = Path(__file__).parent / 'venv'
    
    if venv_path.exists():
        if sys.platform.startswith('win'):
            activate = venv_path / 'Scripts' / 'activate.bat'
            print(f"💡 Activez l'environnement avec: {activate}")
        else:
            activate = venv_path / 'bin' / 'activate'
            print(f"💡 Activez l'environnement avec: source {activate}")
    
    # Lancer l'application
    print("\n🚀 Lancement de KuCoin Bot Dashboard...")
    print("="*50)
    
    try:
        # Lancer l'application en arrière-plan
        process = subprocess.Popen([sys.executable, 'app.py'])
        
        # Attendre un peu que l'application démarre
        time.sleep(5)
        
        # Attendre que le scraper ait fini son premier cycle
        if wait_for_scraper():
            print("\n🎉 Prêt ! L'application est disponible avec des données fraîches")
        else:
            print("\n⚠️  L'application démarre avec des données d'exemple")
        
        print("🌐 Accédez à: http://localhost:5000")
        print("\nAppuyez sur Ctrl+C pour arrêter l'application")
        
        # Attendre que l'utilisateur arrête l'application
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n✋ Application arrêtée")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        print(f"❌ Erreur: {e}")
        if 'process' in locals():
            process.terminate()

if __name__ == "__main__":
    main()