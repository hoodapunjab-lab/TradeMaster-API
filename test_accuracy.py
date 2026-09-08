import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report
from ai_brain import TradeBrain
from data_engine import db_engine
import warnings

warnings.filterwarnings('ignore')

def check_brain_health():
    print("🏥 AI DOCTOR: Checking Brain Health & Accuracy...")
    
    # 1. Brain Load karo
    brain = TradeBrain()
    if not brain.is_ready:
        print("❌ Brain abhi ready nahi hai. Pehle 'run.py' chala kar train hone dein.")
        return

    # 2. Test Data Lao (Random 5 stocks)
    conn = db_engine.get_conn()
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_15m'", conn)
    stocks = tables['name'].tolist()[:5] # Top 5 stocks par test karenge
    conn.close()

    total_accuracy = []

    print(f"\n📝 Taking Exam on {len(stocks)} Stocks...\n")
    print(f"{'STOCK':<15} | {'ACCURACY':<10} | {'STATUS'}")
    print("-" * 40)

    for stock_table in stocks:
        symbol = stock_table.replace("_15m", "")
        
        # Data fetch
        df = db_engine.fetch_data(symbol, "15m", limit=500)
        if len(df) < 200: continue

        # Features banao
        df_eng = brain.engineer_features(df)
        
        # Asli Jawab (Ground Truth)
        # 1 = Price Upar gaya, 0 = Neeche gaya
        y_true = (df_eng['close'].shift(-1) > df_eng['close']).astype(int)
        
        # AI ka Jawab (Prediction)
        y_pred = []
        
        # Har candle par AI se pucho
        # (Yeh thoda slow hoga kyunki hum ek-ek karke test kar rahe hain)
        features = brain.features_list
        
        # Fast Vectorized Check (Sirf XGBoost ka check karenge speed ke liye)
        try:
            X = df_eng[features]
            preds = brain.xgb_model.predict(X)
            
            # Accuracy Score
            score = accuracy_score(y_true, preds) * 100
            total_accuracy.append(score)
            
            status = "🔥 GOD MODE" if score > 70 else "✅ GOOD" if score > 55 else "⚠️ WEAK"
            print(f"{symbol:<15} | {score:.2f}%    | {status}")
            
        except Exception as e:
            print(f"{symbol:<15} | ERROR      | {e}")

    if total_accuracy:
        avg = sum(total_accuracy) / len(total_accuracy)
        print("-" * 40)
        print(f"\n🧠 OVERALL BRAIN ACCURACY: {avg:.2f}%")
        
        if avg > 80:
            print("🚀 CONCLUSION: System is Over-Trained (Thoda Risk hai).")
        elif avg > 60:
            print("✅ CONCLUSION: System is HEALTHY & REALISTIC.")
        else:
            print("⚠️ CONCLUSION: Needs more data or retraining.")
    else:
        print("❌ No data found to test.")

if __name__ == "__main__":
    check_brain_health()