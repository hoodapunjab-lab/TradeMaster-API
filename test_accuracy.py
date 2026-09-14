import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score
from ai_brain import TradeBrain
from data_engine import db_engine
import warnings

warnings.filterwarnings('ignore')

def check_brain_health():
    print("🏥 AI DOCTOR: Checking Brain Health & Accuracy...")
    
    brain = TradeBrain()
    if not brain.is_ready:
        print("❌ Brain abhi ready nahi hai. Pehle 'run.py' chala kar train hone dein.")
        return

    conn = db_engine.get_conn()
    # ✅ FIX 1: 5m timeframe table check
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_5m'", conn)
    stocks = tables['name'].tolist()[:5] 
    conn.close()

    total_accuracy = []

    print(f"\n📝 Taking Exam on {len(stocks)} Stocks...\n")
    print(f"{'STOCK':<15} | {'ACCURACY':<10} | {'STATUS'}")
    print("-" * 40)

    for stock_table in stocks:
        symbol = stock_table.replace("_5m", "")
        
        df = db_engine.fetch_data(symbol, "5m", limit=500)
        if len(df) < 200: continue

        df_eng = brain.engineer_features(df)
        
        # ✅ FIX 2: 3-Class Target Logic (Matched with ai_brain.py)
        future_return = (df_eng['close'].shift(-1) - df_eng['close']) / df_eng['close']
        conditions = [(future_return > 0.002), (future_return < -0.002)]
        choices = [2, 0]
        y_true = np.select(conditions, choices, default=1)
        
        # Remove the last row because its future_return is NaN
        y_true = y_true[:-1]
        df_eng = df_eng.iloc[:-1]
        
        features = brain.features_list
        
        try:
            X = df_eng[features]
            # ✅ FIX 3: Apply the saved Scaler before prediction!
            X_scaled = brain.scaler.transform(X)
            
            preds = brain.xgb_model.predict(X_scaled)
            
            score = accuracy_score(y_true, preds) * 100
            total_accuracy.append(score)
            
            status = "🔥 GOD MODE" if score > 75 else "✅ GOOD" if score > 55 else "⚠️ WEAK"
            print(f"{symbol:<15} | {score:.2f}%    | {status}")
            
        except Exception as e:
            print(f"{symbol:<15} | ERROR      | {e}")

    if total_accuracy:
        avg = sum(total_accuracy) / len(total_accuracy)
        print("-" * 40)
        print(f"\n🧠 OVERALL XGBOOST ACCURACY: {avg:.2f}%")
        
        if avg > 80:
            print("🚀 CONCLUSION: System is Highly Optimized.")
        elif avg > 60:
            print("✅ CONCLUSION: System is HEALTHY & REALISTIC.")
        else:
            print("⚠️ CONCLUSION: Needs more data or retraining.")
    else:
        print("❌ No data found to test.")

if __name__ == "__main__":
    check_brain_health()