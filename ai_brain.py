import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
import joblib
import os
import warnings
import optuna
from data_engine import db_engine 
import symbols

# Logging & Warnings Off
optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings('ignore')
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow not found! Running in ML Mode only.")

MODEL_XGB = "brain_xgboost.pkl"
MODEL_LGBM = "brain_lightgbm.pkl"
MODEL_LSTM = "brain_lstm.keras"
SCALER_FILE = "brain_scaler.pkl"

class TradeBrain:
    def __init__(self):
        self.xgb_model = None
        self.lgbm_model = None
        self.lstm_model = None
        self.scaler = StandardScaler()
        self.is_ready = False 
        self.features_list = []
        self.load_models()

    def load_models(self):
        try:
            if os.path.exists(MODEL_XGB) and os.path.exists(SCALER_FILE):
                data = joblib.load(MODEL_XGB)
                self.xgb_model = data['model']
                self.features_list = data.get('features', [])
                self.scaler = joblib.load(SCALER_FILE)
                
                if os.path.exists(MODEL_LGBM):
                    self.lgbm_model = joblib.load(MODEL_LGBM)

                if TF_AVAILABLE and os.path.exists(MODEL_LSTM):
                    try: self.lstm_model = load_model(MODEL_LSTM)
                    except: pass
                
                self.is_ready = True
        except Exception as e:
            self.is_ready = False

    def engineer_features(self, df):
        df = df.copy()
        
        # 1. Returns & Basics
        df['return'] = df['close'].pct_change()
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # 2. Institutional Activity (VWAP proxy added)
        df['vol_ma'] = df['volume'].rolling(window=20).mean()
        df['rel_vol'] = df['volume'] / (df['vol_ma'] + 1e-9) 
        df['price_vol'] = df['close'] * df['volume']
        df['vwap_proxy'] = df['price_vol'].rolling(window=14).sum() / (df['volume'].rolling(window=14).sum() + 1e-9)
        df['dist_vwap'] = (df['close'] - df['vwap_proxy']) / df['vwap_proxy']
        
        # 3. Trend & Volatility (ATR proxy added)
        df['ma_50'] = df['close'].rolling(window=50).mean()
        df['dist_ma'] = (df['close'] - df['ma_50']) / df['ma_50']
        df['high_low'] = df['high'] - df['low']
        df['atr_proxy'] = df['high_low'].rolling(window=14).mean() / df['close']
        
        # ✅ ROC ADDED: Fast momentum for quicker entries
        df['roc'] = df['close'].pct_change(periods=3) 
        
        # 4. Standard Indicators
        try:
            rsi_ind = RSIIndicator(close=df['close'], window=14)
            df['rsi'] = rsi_ind.rsi() / 100.0
            
            macd = MACD(close=df['close'])
            df['macd_diff'] = macd.macd_diff()
            
            bb = BollingerBands(close=df['close'], window=20, window_dev=2)
            df['bb_width'] = (bb.bollinger_hband() - bb.bollinger_lband()) / df['close']
            df['bb_pos'] = (df['close'] - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband() + 1e-9)
        except: 
            pass 
        
        return df.dropna()

    def train_brain(self):
        print("🧠 Brain: Connecting to Knowledge Base...")
        all_data = []
        
        stock_list = getattr(symbols, 'WATCHLIST', [])
        for sym in stock_list:
            # ✅ TIMEFRAME FIX: Using "5m" to sync perfectly with our fast system
            df = db_engine.fetch_data(sym, "5m", limit=2000)
            if not df.empty and len(df) > 100:
                df = self.engineer_features(df)
                
                # ✅ NEW MULTI-CLASS FIX: BUY, SELL aur NEUTRAL teeno ko pehchano
                future_return = (df['close'].shift(-1) - df['close']) / df['close']
                # 2 = BUY (0.2% up), 0 = SELL (0.2% down), 1 = NEUTRAL (Sideways)
                conditions = [
                    (future_return > 0.002),   # Upar jayega
                    (future_return < -0.002)   # Neeche girega
                ]
                choices = [2, 0]
                df['target'] = np.select(conditions, choices, default=1)
                all_data.append(df)
        
        if not all_data:
            print("❌ No Data found!")
            return

        print(f"🧠 Training on {len(all_data)} Stocks...")
        full_df = pd.concat(all_data)
        
        # Updated Feature List (ROC Added)
        features = ['return', 'log_return', 'rel_vol', 'dist_vwap', 'atr_proxy', 'dist_ma', 'rsi', 'macd_diff', 'bb_width', 'bb_pos', 'roc']
        self.features_list = [f for f in features if f in full_df.columns]
        
        X = full_df[self.features_list]
        y = full_df['target']
        
        X_scaled = self.scaler.fit_transform(X)
        joblib.dump(self.scaler, SCALER_FILE)

        print("🚀 Training XGBoost (Multi-Class)...")
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=150, 
            learning_rate=0.05, 
            max_depth=5, 
            objective='multi:softprob', 
            num_class=3, 
            n_jobs=-1, 
            random_state=42
        )
        self.xgb_model.fit(X_scaled, y)
        joblib.dump({'model': self.xgb_model, 'features': self.features_list}, MODEL_XGB)

        print("⚡ Training LightGBM (Multi-Class)...")
        self.lgbm_model = lgb.LGBMClassifier(
            n_estimators=150, 
            learning_rate=0.05, 
            num_leaves=31, 
            objective='multiclass', 
            num_class=3, 
            n_jobs=-1, 
            random_state=42, 
            verbose=-1
        )
        self.lgbm_model.fit(X_scaled, y)
        joblib.dump(self.lgbm_model, MODEL_LGBM)

        if TF_AVAILABLE:
            try:
                print("🧠 Training LSTM (Multi-Class)...")
                X_lstm = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
                model = Sequential([
                    LSTM(50, return_sequences=False, input_shape=(1, X_scaled.shape[1])),
                    Dropout(0.2),
                    Dense(3, activation='softmax') # 3 output neurons (Buy, Sell, Neutral)
                ])
                # Loss function change for multi-class
                model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
                model.fit(X_lstm, y, epochs=3, batch_size=64, verbose=0)
                model.save(MODEL_LSTM)
            except Exception as e:
                print(f"⚠️ LSTM Error: {e}")

        self.is_ready = True
        print("🎉 Brain Upgrade Complete! (XGB + LGBM + LSTM + Advanced Features)")

    def predict_signal(self, symbol):
        if not self.is_ready: return {"signal": "WAITING", "prob": 0}

        try:
            # ✅ TIMEFRAME FIX: "5m" for lightning-fast live market inputs
            df = db_engine.fetch_data(symbol, "5m", limit=100)
            if len(df) < 50: return {"signal": "NEUTRAL", "prob": 0}

            df_eng = self.engineer_features(df)
            missing = set(self.features_list) - set(df_eng.columns)
            if missing: return {"signal": "NEUTRAL", "prob": 0}

            last_row = df_eng.iloc[[-1]][self.features_list]
            last_row_scaled = self.scaler.transform(last_row)

            # Returns array of [Prob_Sell, Prob_Neutral, Prob_Buy]
            prob_xgb = self.xgb_model.predict_proba(last_row_scaled)[0] 
            
            prob_lgbm = [0.33, 0.33, 0.33]
            if self.lgbm_model:
                prob_lgbm = self.lgbm_model.predict_proba(last_row_scaled)[0]

            prob_lstm = [0.33, 0.33, 0.33]
            if self.lstm_model and TF_AVAILABLE:
                try:
                    X_input = last_row_scaled.reshape((1, 1, last_row_scaled.shape[1]))
                    # ✅ SPEED FIX: Using predict_on_batch for faster execution in loops
                    prediction_tensor = self.lstm_model.predict_on_batch(X_input)
                    if hasattr(prediction_tensor, 'numpy'):
                        prob_lstm = prediction_tensor.numpy()[0]
                    else:
                        prob_lstm = prediction_tensor[0]
                except: pass

            # Ensemble Average [Sell, Neutral, Buy]
            avg_probs = (prob_xgb * 0.4) + (np.array(prob_lgbm) * 0.4) + (np.array(prob_lstm) * 0.2)

            # Class 0: Sell, Class 1: Neutral, Class 2: Buy
            sell_prob = avg_probs[0] * 100
            neutral_prob = avg_probs[1] * 100
            buy_prob = avg_probs[2] * 100

            signal = "NEUTRAL"
            confidence = neutral_prob

            if buy_prob >= 65: # Agar 65% se zyada lag raha hai ki upar jayega
                signal = "BUY"
                confidence = buy_prob
            elif sell_prob >= 65: # Agar 65% se zyada lag raha hai ki neeche girega
                signal = "SELL"
                confidence = sell_prob

            return {"signal": signal, "prob": float(round(confidence, 2))}

        except Exception as e:
            return {"signal": "ERROR", "prob": 0.0}