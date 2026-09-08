import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import warnings
from warnings import simplefilter

# HMM Learn ki warnings band karna
simplefilter(action='ignore', category=FutureWarning)
simplefilter(action='ignore', category=UserWarning)
warnings.filterwarnings('ignore')

HMM_AVAILABLE = False
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    pass

class MarketRegimeDetector:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        if HMM_AVAILABLE:
            self.model = GaussianHMM(n_components=3, covariance_type="full", n_iter=100, random_state=42, init_params="stmc")

    def get_regime(self, df):
        try:
            if df.empty or len(df) < 60: return "UNKNOWN"
            
            if HMM_AVAILABLE and self.model:
                try:
                    data = df.copy()
                    
                    data['returns'] = data['close'].pct_change()
                    data['range'] = (data['high'] - data['low']) / data['close']
                    data['volatility'] = data['returns'].rolling(window=10).std()
                    
                    # ✅ DHOKEBAJI FIX: Outlier Clipping (Freak trades ko cap karna)
                    data['returns'] = data['returns'].clip(lower=-0.03, upper=0.03)
                    data['range'] = data['range'].clip(upper=0.05)
                    
                    data = data.replace([np.inf, -np.inf], np.nan).dropna()
                    if len(data) < 50: return "UNKNOWN"
                    
                    X = data[['returns', 'range', 'volatility']].values
                    X_scaled = self.scaler.fit_transform(X)
                    self.model.fit(X_scaled)
                    
                    hidden_states = self.model.predict(X_scaled)
                    current_state = hidden_states[-1]
                    
                    state_stats = []
                    for i in range(3):
                        mask = (hidden_states == i)
                        if np.any(mask):
                            avg_ret = X[mask, 0].mean()
                            state_stats.append({'state': i, 'ret': avg_ret})
                        else:
                            state_stats.append({'state': i, 'ret': 0})
                    
                    state_stats.sort(key=lambda x: x['ret'])
                    bear_state = state_stats[0]['state']
                    bull_state = state_stats[2]['state']
                    
                    if current_state == bull_state: return "TRENDING UP 🚀"
                    elif current_state == bear_state: return "TRENDING DOWN 🔻"
                    else: return "CHOPPY / SIDEWAYS 🦀"

                except Exception as e:
                    return self.get_regime_fallback(df)
            else:
                return self.get_regime_fallback(df)

        except Exception as e:
            return "UNKNOWN"

    def get_regime_fallback(self, df):
        try:
            close = df['close']
            ema_50 = close.ewm(span=50).mean()
            
            last_price = close.iloc[-1]
            last_ema = ema_50.iloc[-1]
            prev_ema = ema_50.iloc[-5]
            
            slope = last_ema - prev_ema
            threshold = last_price * 0.0005
            
            if slope > threshold: return "TRENDING UP 🚀"
            elif slope < -threshold: return "TRENDING DOWN 🔻"
            else: return "CHOPPY / SIDEWAYS 🦀"
        except:
            return "UNKNOWN"

regime_detector = MarketRegimeDetector()