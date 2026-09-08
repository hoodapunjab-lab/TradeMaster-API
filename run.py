import subprocess
import time
import os
import sys
import requests

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

import config

def send_alert(msg):
    if not config.TELEGRAM_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={'chat_id': config.TELEGRAM_CHAT_ID, 'text': msg}, timeout=5)
    except: pass

def start_system():
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"{GREEN}" + "="*60)
    print(f"        🚀 TRADEMASTER PRO V2.0 - MASTER LAUNCHER        ")
    print("="*60 + f"{RESET}\n")

    processes = {}

    print(f"{YELLOW}🟢 Starting Database Manager (Data Feed)...{RESET}")
    processes['db'] = subprocess.Popen([sys.executable, "db_manager.py"])
    
    # ✅ WARM-UP DELAY: Give DB manager 15 seconds to fetch initial Sector data
    print(f"{CYAN}⏳ Warming up data streams for 15 seconds...{RESET}")
    time.sleep(15) 

    print(f"{YELLOW}🟢 Starting API Server (Dashboard)...{RESET}")
    processes['api'] = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8080", "--log-level", "error"])
    time.sleep(3)

    print(f"{YELLOW}🤖 Starting Order Manager (Trading Bot)...{RESET}")
    processes['bot'] = subprocess.Popen([sys.executable, "order_manager.py"])
    time.sleep(2)

    print(f"{YELLOW}📊 Launching Live Dashboard (view.py)...{RESET}")
    if os.name == 'nt': 
        subprocess.Popen(f'start cmd /k "{sys.executable} view.py"', shell=True)
    else: 
        subprocess.Popen([sys.executable, "view.py"])

    print(f"\n{GREEN}✅ ALL SYSTEMS GO!{RESET}")
    print(f"👉 Web Panel:  {CYAN}http://127.0.0.1:8080/static/index.html{RESET}")
    print(f"{RED}🛑 Press Ctrl+C to Stop All.{RESET}\n")

    bot_crashed_alerted = False

    try:
        while True:
            time.sleep(3)
            
            # Watchdog: DB
            if processes['db'].poll() is not None:
                print(f"{RED}⚠️ DB Manager Crashed! Restarting...{RESET}")
                processes['db'] = subprocess.Popen([sys.executable, "db_manager.py"])

            # Watchdog: API
            if processes['api'].poll() is not None:
                print(f"{RED}⚠️ API Server Crashed! Restarting...{RESET}")
                processes['api'] = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8080"])

            # ✅ Watchdog: BOT CRASH ALERT (The Blind-Spot Fix)
            if processes['bot'].poll() is not None and not bot_crashed_alerted:
                print(f"{RED}🚨 BOT CRASHED! Open trades are not being monitored!{RESET}")
                send_alert("🚨 CRITICAL: Order Manager has crashed! Check terminal & open trades manually immediately!")
                bot_crashed_alerted = True 

    except KeyboardInterrupt:
        print(f"\n\n{RED}🛑 Stopping System...{RESET}")
        for name, proc in processes.items():
            if proc.poll() is None: 
                proc.terminate()
        print(f"{GREEN}✅ All processes gracefully stopped.{RESET}")

if __name__ == "__main__":
    start_system()