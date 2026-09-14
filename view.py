import time
from datetime import datetime
import sys
import io
import colorama
from colorama import Fore, Style
import requests

# Force UTF-8 encoding for CMD (Emojis aur Dotted Bars ke liye zaroori)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
colorama.init(autoreset=True)

INDICES = ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTY IT", "NIFTY AUTO", "NIFTY METAL", "NIFTY PHARMA"]
COMMODITIES = ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"]

# ✅ NEW: Terminal ke liye Dotted Progress Bar Generator
def get_progress_bar(score, length=10):
    try:
        val = float(str(score).replace('%', ''))
        val = min(abs(val), 100) # Cap at 100
        filled = int((val / 100) * length)
        return f"[{'■' * filled}{'·' * (length - filled)}]"
    except:
        return f"[{'·' * length}]"

def print_dashboard(stock_results, option_results):
    print("\033c", end="")
    
    print(Fore.CYAN + "="*85)
    print(Fore.YELLOW + Style.BRIGHT + "        🚀 TRADEMASTER PRO V2.0 (AI + GARCH + NSE + MCX) 🚀")
    print(Fore.CYAN + "="*85)
    
    print(Fore.WHITE + "\n📊 LIVE INDICES & SECTORS (TOP-DOWN ANALYSIS):")
    print("-" * 85)
    for idx in INDICES:
        data = option_results.get(idx)
        if not data: continue
        trend = data.get('trend', 'UNKNOWN')
        col = Fore.GREEN if "BULL" in trend else Fore.RED if "BEAR" in trend else Fore.YELLOW
        
        # Parse & Cap Score
        raw_pcr = str(data.get('pcr', '0')).replace('%', '')
        score_val = min(int(raw_pcr) if raw_pcr.isdigit() else 0, 100)
        pcr_text = f"{score_val}%" if data.get('pcr') != 'Wait' else "--"
        
        # Generate Bar
        bar = get_progress_bar(score_val)
        
        print(f"{idx:<15} : {col}{trend:<15}{Fore.WHITE} | Signal: {data.get('signal','WAIT'):<10} | Score: {pcr_text:<4} {Fore.CYAN}{bar}{Fore.WHITE}")

    print(Fore.WHITE + "\n🛢️ LIVE MCX COMMODITIES:")
    print("-" * 85)
    for comm in COMMODITIES:
        data = option_results.get(comm)
        if not data: continue
        trend = data.get('trend', 'UNKNOWN')
        col = Fore.GREEN if "BULL" in trend else Fore.RED if "BEAR" in trend else Fore.YELLOW
        
        # Parse & Cap Score
        raw_pcr = str(data.get('pcr', '0')).replace('%', '')
        score_val = min(int(raw_pcr) if raw_pcr.isdigit() else 0, 100)
        pcr_text = f"{score_val}%" if data.get('pcr') != 'Wait' else "--"
        
        # Generate Bar
        bar = get_progress_bar(score_val)
        
        print(f"{comm:<15} : {col}{trend:<15}{Fore.WHITE} | Signal: {data.get('signal','WAIT'):<10} | Score: {pcr_text:<4} {Fore.CYAN}{bar}{Fore.WHITE}")

    print(Fore.WHITE + "\n📈 STOCK & ASSET SCANNER RESULTS:")
    print("-" * 105)
    print(f"{'SYMBOL':<15} {'PRICE':<10} {'SIGNAL':<18} {'SCORE & BAR':<18} {'RISK (GARCH)':<14} {'AI CONF'}")
    print("-" * 105)
    
    if not stock_results or "error" in stock_results:
        print(Style.DIM + "    Scanning markets... Waiting for API & AI to sync.")
    else:
        if isinstance(stock_results, list):
            for res in stock_results[:15]: 
                col = Fore.WHITE
                if "GOD" in res['Signal']: col = Fore.GREEN + Style.BRIGHT
                elif "BUY" in res['Signal']: col = Fore.GREEN
                elif "SELL" in res['Signal']: col = Fore.RED
                elif "TRAP" in res['Signal']: col = Fore.MAGENTA
                
                risk_txt = res.get('Risk', 'Stable')
                risk_col = Fore.RED if "HIGH" in risk_txt else Fore.GREEN
                
                # Parse Score, Cap at 100, and Add Bar for Stocks
                score_val = min(abs(res['Score']), 100)
                bar = get_progress_bar(score_val, length=8)
                score_display = f"{score_val:<3} {bar}"
                
                print(col + f"{res['Symbol']:<15} {res['Price']:<10} {res['Signal']:<18} {score_display:<18} " + 
                      risk_col + f"{risk_txt:<14} " + 
                      Fore.CYAN + f"{res.get('Accuracy', '--')}%")
    
    print(Fore.CYAN + "\n" + "="*85)
    print(Style.DIM + f"Last Sync: {datetime.now().strftime('%H:%M:%S')} | Live API Connected | Press Ctrl+C to Stop")

def main():
    print("🔄 Connecting to TradeMaster API Server...")
    time.sleep(5) # API server ko start hone ka time dena
    
    while True:
        try:
            # API se JSON data lana
            option_res = requests.get("http://127.0.0.1:8080/option_chain", timeout=10).json()
            stock_res = requests.get("http://127.0.0.1:8080/scan/5m", timeout=15).json()
            
            # Print function ko call karna
            print_dashboard(stock_res, option_res)
            
            time.sleep(10) 
        except requests.exceptions.ConnectionError:
            print(Fore.RED + "⏳ Waiting for API Server to start... Make sure run.py is running.")
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ View Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()