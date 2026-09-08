import sqlite3
import pandas as pd
from datetime import datetime
import threading
import os
import numpy as np

DB_NAME = "trademaster_pro.db"

class DataEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DataEngine, cls).__new__(cls)
                    cls._instance.init_db()
        return cls._instance

    def get_conn(self):
        conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)
        return conn

    def init_db(self):
        try:
            conn = self.get_conn()
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA cache_size = -64000;") 
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;") 
            conn.commit()
            conn.close()
        except Exception as e:
            pass

    # ✅ BSE AUR MCX FIX
    def _sanitize_name(self, symbol):
        clean = symbol.replace(".NS", "").replace(".BSE", "").replace(".MCX", "").replace("-EQ", "").replace("&", "_").replace("-", "_")
        return "".join(c for c in clean if c.isalnum() or c == '_')

    def create_table_if_not_exists(self, conn, table_name):
        query = f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                timestamp DATETIME PRIMARY KEY,
                open REAL, high REAL, low REAL, close REAL, volume INTEGER
            )
        '''
        conn.execute(query)

    def save_data(self, df, symbol, timeframe):
        if df is None or df.empty: return

        df = df.copy()
        clean_sym = self._sanitize_name(symbol)
        table_name = f"{clean_sym}_{timeframe}" 

        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        cols_numeric = ['open', 'high', 'low', 'close', 'volume']
        for c in cols_numeric:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df = df.dropna(subset=cols_numeric) 
        
        df['price_change_pct'] = abs((df['close'] - df['open']) / (df['open'] + 1e-9))
        df = df[df['price_change_pct'] < 0.05] 
        df = df.drop(columns=['price_change_pct'])
        
        final_df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        data_tuples = list(final_df.itertuples(index=False, name=None))

        with self._lock:
            try:
                conn = self.get_conn()
                self.create_table_if_not_exists(conn, table_name)
                
                conn.executemany(f'''
                    INSERT OR REPLACE INTO "{table_name}" 
                    (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', data_tuples)
                
                conn.commit()
                conn.close()
            except Exception as e:
                pass

    def fetch_data(self, symbol, timeframe="15m", limit=500):
        try:
            clean_sym = self._sanitize_name(symbol)
            table_name = f"{clean_sym}_{timeframe}"
            
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone()[0] == 0:
                conn.close()
                return pd.DataFrame() 

            query = f'SELECT * FROM "{table_name}" ORDER BY timestamp DESC LIMIT {limit}'
            df = pd.read_sql(query, conn, parse_dates=['timestamp'])
            conn.close()
            
            if not df.empty:
                df = df.sort_values('timestamp') 
                df = df.set_index('timestamp')
                
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata').tz_localize(None)

                df = df[~df.index.duplicated(keep='last')]
                df['volume'] = df['volume'].replace(0, np.nan).ffill()
                df = df.ffill() 
                
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            return pd.DataFrame()

db_engine = DataEngine()