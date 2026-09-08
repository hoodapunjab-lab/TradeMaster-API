# FILE NAME: debug_dashboard.py

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

# Database Name
DB_NAME = "trademaster_pro.db"

def check_and_fix():
    print("🕵️‍♂️ DEBUG MODE: Checking Database Health...\n")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Check Existing Data
    symbols_to_check = ["NIFTY_50", "BANKNIFTY"]
    
    for sym in symbols_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM historical_data WHERE symbol='{sym}'")
            count = cursor.fetchone()[0]
            print(f"📊 {sym} in Database: {count} candles found.")
            
            if count < 50:
                print(f"⚠️ {sym} is EMPTY! Attempting to fix...")
                download_and_fill(sym)
            else:
                print(f"✅ {sym} is GOOD. (Problem might be in run.py logic)")
                
        except Exception as e:
            print(f"❌ Error checking {sym}: {e}")
            # Agar table hi nahi hai, to banayenge
            create_table(cursor)
            download_and_fill(sym)

    conn.close()
    print("\n🔍 DIAGNOSIS COMPLETE.")

def create_table(cursor):
    print("🛠️ Creating missing table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_data (
            symbol TEXT,
            timestamp DATETIME,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, timestamp)
        )
    ''')

def download_and_fill(db_symbol):
    y_symbol = "^NSEI" if db_symbol == "NIFTY_50" else "^NSEBANK"
    print(f"⬇️ Downloading fresh data for {db_symbol} from Yahoo ({y_symbol})...")
    
    try:
        # Download Data
        df = yf.download(y_symbol, period="5d", interval="15m", progress=False)
        
        if df.empty:
            print(f"❌ Yahoo Finance returned EMPTY data for {y_symbol}. Internet check karein.")
            return

        # Fix MultiIndex Columns (New yfinance update fix)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        
        # Rename Columns (Case insensitive fix)
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={"datetime": "timestamp"}, inplace=True)
        
        # Prepare Data for Insert
        records = []
        for _, row in df.iterrows():
            # Timezone hata kar string banana
            ts = str(row['timestamp']).replace('+05:30', '').replace('+00:00', '')
            records.append((
                db_symbol, ts, row['open'], 
                row['high'], row['low'], row['close'], row['volume']
            ))
        
        # Insert into DB
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.executemany("INSERT OR IGNORE INTO historical_data VALUES (?,?,?,?,?,?,?)", records)
        conn.commit()
        
        # Verify Insert
        cursor.execute(f"SELECT COUNT(*) FROM historical_data WHERE symbol='{db_symbol}'")
        new_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✅ SUCCESS: Now Database has {new_count} candles for {db_symbol}.")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR downloading {db_symbol}: {e}")

if __name__ == "__main__":
    check_and_fix()