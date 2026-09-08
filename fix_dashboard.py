# FILE NAME: fix_dashboard.py

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

# Database Connection
DB_NAME = "trademaster_pro.db"

def fix_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Table banao agar nahi hai
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

    print("🚑 Starting Emergency Repair...")

    # List of missing indices
    indices = {
        "NIFTY_50": "^NSEI",
        "BANKNIFTY": "^NSEBANK"
    }

    for db_symbol, y_symbol in indices.items():
        print(f"\n⏳ Downloading Data for {db_symbol} from Yahoo...")
        try:
            # 60 din ka data download karo (kaafi hai trend ke liye)
            df = yf.download(y_symbol, period="60d", interval="15m", progress=False)
            
            if df.empty:
                print(f"❌ Failed to fetch {db_symbol}")
                continue

            # Cleaning Data
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = df.reset_index()
            df.rename(columns={
                "Datetime": "timestamp", "Open": "open", "High": "high", 
                "Low": "low", "Close": "close", "Volume": "volume"
            }, inplace=True)
            
            # Timezone hatao (Database clean rakhne ke liye)
            df['timestamp'] = df['timestamp'].astype(str).str.replace(r'\+.*', '', regex=True)

            records = []
            for _, row in df.iterrows():
                records.append((
                    db_symbol, row['timestamp'], row['open'], 
                    row['high'], row['low'], row['close'], row['volume']
                ))

            # Database me bharo
            cursor.executemany("INSERT OR IGNORE INTO historical_data VALUES (?,?,?,?,?,?,?)", records)
            conn.commit()
            print(f"✅ {db_symbol}: Repaired! ({len(records)} candles added)")

        except Exception as e:
            print(f"❌ Error: {e}")

    conn.close()
    print("\n🎉 FIX COMPLETE! Ab 'python run.py' chalayein.")

if __name__ == "__main__":
    fix_data()