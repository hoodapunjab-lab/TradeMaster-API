# FILE NAME: update_system.py

import os
import sys
import subprocess
from colorama import Fore, Style, init

# Init Colors
init(autoreset=True)

def auto_learn():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print(Fore.YELLOW + Style.BRIGHT + "="*60)
    print(Fore.YELLOW + Style.BRIGHT + "      🤖 TRADEMASTER PRO - SELF LEARNING SYSTEM      ")
    print(Fore.YELLOW + Style.BRIGHT + "="*60 + "\n")

    # --- STEP 1: Smart Data Sync ---
    print(Fore.CYAN + "⏳ [STEP 1/2] Syncing New Market Data...")
    print(Style.DIM + "   (Checking for new candles & appending to database...)")
    
    try:
        # ✅ FIX: Hum 'import' nahi use karenge. Seedha file chalayenge.
        # Ye tarika sabse safe hai aur kabhi error nahi deta.
        subprocess.check_call([sys.executable, "db_manager.py", "--once"])
        
        print(Fore.GREEN + "✅ Data Sync Complete! (Knowledge Updated)\n")
    except Exception as e:
        print(Fore.RED + f"❌ Data Sync Failed: {e}")
        print(Fore.YELLOW + "⚠️ Note: Make sure db_manager.py is updated properly.")
    
    # --- STEP 2: Retrain AI Brain ---
    print(Fore.CYAN + "⏳ [STEP 2/2] Retraining AI Brain (XGBoost + LSTM)...")
    print(Style.DIM + "   (Reading full history & making the brain smarter...)")

    try:
        subprocess.check_call([sys.executable, "train_ai.py"])
        print(Fore.GREEN + "✅ AI Training Complete! (Brain Upgraded)\n")
    except Exception as e:
        print(Fore.RED + f"❌ AI Training Failed: {e}")
        return

    print(Fore.YELLOW + "="*60)
    print(Fore.GREEN + Style.BRIGHT + "🎉 SUCCESS: System is now updated with latest market logic!")
    print(Fore.YELLOW + "="*60)
    print(Fore.WHITE + "Ab aap 'python run.py' chala sakte hain.\n")

if __name__ == "__main__":
    auto_learn()