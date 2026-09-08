import time
import pandas as pd
from datetime import datetime, timedelta
import pytz 
import json
import os
import sys 
import concurrent.futures
from smart_session import session_manager 
from data_engine import db_engine            
import symbols

IST = pytz.timezone('Asia/Kolkata')

class DataManager:
    def __init__(self):
        print("📂 Initializing Data Manager...")
        if not session_manager.token_map:
            session_manager.load_token_map()
            
    def get_last_timestamp(self, symbol, timeframe):
        try:
            conn = db_engine.get_conn()
            clean_sym = symbol.replace(".NS", "").replace("-EQ", "").replace("&", "_").replace("-", "_")
            table_name = f"{clean_sym}_{timeframe}"
            
            cursor = conn.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone()[0] == 0:
                conn.close()
                return None
            
            query = f"SELECT MAX(timestamp) FROM {table_name}"
            last_time = conn.execute(query).fetchone()[0]
            conn.close()
            
            if last_time:
                return datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
        except:
            pass
        return None

    def fetch_stock_data(self, symbol):
        api = session_manager.get_session()
        if not api: return

        token = session_manager.get_token(symbol)
        if not token: return

        current_time = datetime.now(IST)

        for tf in ["15m", "1h"]:
            retry_count = 0
            max_retries = 3 
            
            while retry_count < max_retries:
                try:
                    interval = "FIFTEEN_MINUTE" if tf == "15m" else "ONE_HOUR"
                    last_db_time = self.get_last_timestamp(symbol, tf)
                    
                    from_date = None
                    if last_db_time:
                        last_db_time = last_db_time.replace(tzinfo=None)
                        curr_naive = current_time.replace(tzinfo=None)
                        if last_db_time >= curr_naive - timedelta(minutes=15):
                            break 
                        from_date = last_db_time + timedelta(minutes=1)
                    else:
                        from_date = current_time.replace(tzinfo=None) - timedelta(days=100)

                    from_str = from_date.strftime("%Y-%m-%d %H:%M")
                    to_str = current_time.strftime("%Y-%m-%d %H:%M")

                    # ✅ NEW: Exchange Auto-Detect Logic (MCX, BSE, NSE)
                    exchange_name = "NSE"
                    if symbol == "SENSEX":
                        exchange_name = "BSE"
                    elif hasattr(symbols, 'COMMODITIES') and symbol in symbols.COMMODITIES:
                        exchange_name = "MCX"

                    params = {
                        "exchange": exchange_name, 
                        "symboltoken": token, 
                        "interval": interval, 
                        "fromdate": from_str, 
                        "todate": to_str
                    }
                    
                    # ✅ RATE LIMIT FIX: Delay badha kar 1.5 seconds kar diya taaki AB1021 error block na kare
                    time.sleep(1.5) 
                    data = api.getCandleData(params)

                    if data and data.get('status'):
                        if data.get('data'):
                            df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            df['timestamp'] = pd.to_datetime(df['timestamp'])
                            
                            # ✅ SECTOR FIX: Indices me volume nahi hota, use 0 set karo taaki crash na ho
                            if 'volume' not in df.columns or df['volume'].isnull().all():
                                df['volume'] = 0
                                
                            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                            db_engine.save_data(df, symbol, tf)
                            print(f"✅ {symbol} [{tf}]: Saved {len(df)} candles.")
                        break
                    else:
                        msg = data.get('message', '') if data else ''
                        if 'rate' in msg.lower() or 'access denied' in msg.lower() or 'too many requests' in msg.lower() or 'ab1021' in msg.lower():
                            print(f"⚠️ Rate Limit ({symbol}). Waiting 3s to cool down...")
                            time.sleep(3) # Agar block hua toh bot 3 second ruk kar dobara try karega
                            retry_count += 1
                            continue
                        else:
                            break
                except Exception as e:
                    time.sleep(2)
                    retry_count += 1
            
            # Har timeframe ke beech mein bhi thoda araam
            time.sleep(1)

    def sync_data(self):
        if not session_manager.get_session():
            print("❌ Login Failed. Retrying...")
            time.sleep(5)
            if not session_manager.get_session(): return

        print(f"\n⏳ Syncing Data for {len(symbols.ALL_STOCKS)} Symbols (Including Sectors & Commodities)...")
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.map(self.fetch_stock_data, symbols.ALL_STOCKS)
        
        duration = time.time() - start_time
        print(f"✅ Sync Complete in {duration:.2f} seconds.")

    def is_market_open(self):
        """✅ MARKET HOURS FIX: Updated to support MCX timings (Mon-Fri, 9:15 to 23:55)"""
        now = datetime.now(IST)
        if now.weekday() > 4: return False
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=23, minute=55, second=0, microsecond=0) # MCX chalta hai raat tak!
        return market_start <= now <= market_end

    def run_scheduler(self):
        print("🔄 Data Manager Started (Smart Market Mode)...")
        while True:
            if self.is_market_open():
                self.sync_data()
                print("💤 Market Open: Sleeping 3 minutes...")
                time.sleep(180)
            else:
                print("🛑 Market Closed. Sleeping for 15 minutes to save resources...")
                time.sleep(900)

if __name__ == "__main__":
    dm = DataManager()
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        dm.sync_data()
        print("🚀 Single Sync Finished. Exiting...")
    else:
        dm.run_scheduler()