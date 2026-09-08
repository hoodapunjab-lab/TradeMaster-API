from db_manager import DataFeeder
import symbols
import time

def start_backfill():
    print("\n" + "="*50)
    print("   📥 INITIAL DATA DOWNLOADER (Backfill System)")
    print("="*50 + "\n")
    
    print("⏳ Connecting to Angel One...")
    feeder = DataFeeder()
    
    total_stocks = len(symbols.WATCHLIST)
    print(f"✅ Connection Successful! Found {total_stocks} stocks in Watchlist.\n")
    
    print("🚀 Starting Download (History: 100 Days)...")
    
    start_time = time.time()
    
    for i, stock in enumerate(symbols.WATCHLIST):
        try:
            print(f"[{i+1}/{total_stocks}] Fetching {stock}...")
            # Ye function smart hai, agar data nahi hai to 100 din ka layega
            feeder.fetch_smart_data(stock) 
        except Exception as e:
            print(f"❌ Error downloading {stock}: {e}")
            
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*50)
    print(f"🎉 DOWNLOAD COMPLETE in {int(duration)} seconds!")
    print("📂 Data saved to 'trademaster_pro.db'")
    print("👉 Ab aap 'python run.py' chala sakte hain.")
    print("="*50)

if __name__ == "__main__":
    start_backfill()