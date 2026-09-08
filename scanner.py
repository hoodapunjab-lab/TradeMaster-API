import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from arch import arch_model 

from ai_brain import TradeBrain
from data_engine import db_engine
import symbols 
import config
import requests
import threading
import warnings
import time
from datetime import datetime, time as dt_time  

warnings.filterwarnings('ignore')

try:
    from market_regime import MarketRegimeDetector 
    REGIME_AVAILABLE = True
except ImportError:
    REGIME_AVAILABLE = False

brain = TradeBrain()
if REGIME_AVAILABLE:
    regime_detector = MarketRegimeDetector() 

alert_history = {} 

# ✅ VIJAY'S MASTER LOGIC: Yahan hum market ka aakhri mood save karenge
# Taaki market band hone par AI ko faltu me na chalana pade
last_scan_cache = {} 

class MarketScanner:
    def __init__(self):
        self.trap_model = IsolationForest(n_estimators=50, contamination=0.02, random_state=42, n_jobs=-1)
        self.scaler = StandardScaler()

    def calculate_garch_risk(self, df):
        try:
            returns = 100 * df['close'].pct_change().dropna()
            if len(returns) < 50: return False

            model = arch_model(returns, vol='Garch', p=1, q=1, rescale=False)
            res = model.fit(disp='off')
            
            forecast = res.forecast(horizon=1)
            next_vol = np.sqrt(forecast.variance.values[-1, :][0])
            
            recent_vol = returns.rolling(window=20).std().iloc[-1]
            
            if next_vol > (recent_vol * 2.0):
                return True 
            return False
        except:
            return False

    def detect_trap_ml(self, df):
        try:
            if len(df) < 50: return False
            
            last = df.iloc[-1]
            body = abs(last['close'] - last['open'])
            upper_wick = last['high'] - max(last['close'], last['open'])
            
            if upper_wick > (3 * body) and last['high'] > df['high'].iloc[-10:].max():
                return True

            data = df[['close', 'volume']].copy()
            data['returns'] = data['close'].pct_change().fillna(0)
            data['vol_change'] = data['volume'].pct_change().fillna(0)
            data['range'] = (df['high'] - df['low']) / df['close']
            
            recent_data = data[['returns', 'vol_change', 'range']].values
            scaled_features = self.scaler.fit_transform(recent_data)
            self.trap_model.fit(scaled_features)
            
            prediction = self.trap_model.predict(scaled_features[-1].reshape(1, -1))
            
            return bool(prediction[0] == -1)

        except Exception as e:
            return False

    def analyze_stock(self, symbol, timeframe="15m"):
        global alert_history, last_scan_cache
        
        current_time = datetime.now().time()
        mcx_symbols = getattr(symbols, 'COMMODITIES', ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "COPPER", "ZINC"])
        is_mcx = symbol in mcx_symbols
        
        if is_mcx:
            market_open = dt_time(9, 0) <= current_time <= dt_time(23, 30)
            closed_label = "🔴 MCX CLOSED"
        else:
            market_open = dt_time(9, 15) <= current_time <= dt_time(15, 30)
            closed_label = "🔴 NSE CLOSED"
        
        # ==========================================
        # ✅ SMART CACHE BYPASS (As you suggested)
        # Agar market band hai aur humare paas aaj ka aakhri data (last mood) pehle se save hai,
        # toh bina AI ko chalaye seedha wahi purana data return kar do! (CPU usage 0%)
        # ==========================================
        if not market_open and symbol in last_scan_cache:
            cached_data = last_scan_cache[symbol].copy()
            # Bas naam ke aage CLOSED likh denge taaki user ko pata chale
            if closed_label not in cached_data["Pattern"]:
                cached_data["Pattern"] = f"{closed_label} (EOD Mood) | " + cached_data["Pattern"]
            return cached_data

        try:
            # Agar market LIVE hai (ya phir cache khali hai), tabhi yeh heavy calculation hogi
            df = db_engine.fetch_data(symbol, timeframe, limit=200)
            if df.empty or len(df) < 100: return None
            
            close = df['close']
            high = df['high']
            low = df['low']
            
            ema_200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
            ema_50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            macd = MACD(close).macd_diff().iloc[-1]
            adx = ADXIndicator(high, low, close, window=14).adx().iloc[-1]
            atr = AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]
            
            current_price = close.iloc[-1]
            
            ai_res = brain.predict_signal(symbol)
            ai_score = ai_res.get('prob', 0)
            ai_signal = ai_res.get('signal', "NEUTRAL")
            
            is_trap = self.detect_trap_ml(df)
            is_high_risk = self.calculate_garch_risk(df)
            risk_label = "⚠️ HIGH VOLATILITY" if is_high_risk else "Stable"
            
            score = 50 
            reasons = []
            
            if not market_open:
                reasons.append(f"{closed_label} (EOD Mood)")

            regime_score = 0
            if REGIME_AVAILABLE:
                stock_regime = regime_detector.get_regime(df)
                if "CHOPPY" in stock_regime: regime_score -= 20
                if "TRENDING UP" in stock_regime: regime_score += 10
                
                stock_sector = symbols.get_sector(symbol)
                if stock_sector:
                    sector_df = db_engine.fetch_data(stock_sector, timeframe, limit=100)
                    if not sector_df.empty:
                        sector_regime = regime_detector.get_regime(sector_df)
                        if "TRENDING UP" in sector_regime:
                            regime_score += 20
                            reasons.append(f"Sector ({stock_sector}) Bullish")
                        elif "TRENDING DOWN" in sector_regime or "CHOPPY" in sector_regime:
                            regime_score -= 20
                            reasons.append(f"Sector Weak")

            if current_price > ema_200: 
                score += 15
                if current_price > ema_50: score += 10
            else: 
                score -= 25

            if 55 <= rsi <= 75: score += 15
            elif rsi < 45: score -= 15
            
            if macd > 0: score += 10
            else: score -= 10

            if ai_signal == "BUY":
                if ai_score > 75: 
                    score += 30
                    reasons.append(f"AI Strong Buy ({ai_score}%)")
                elif ai_score > 55: score += 15
            elif ai_signal == "SELL": 
                score -= 30

            score += regime_score
            if regime_score < 0: reasons.append("Market Choppy")

            if is_trap:
                score -= 30
                reasons.append("⚠️ ML Anomaly (Trap Risk)")

            if is_high_risk:
                score -= 20
                reasons.append("⚠️ GARCH Risk High")

            signal = "NEUTRAL"
            color = "gray"
            
            if score >= 80:
                signal = "GOD MODE 🚀"
                color = "#00ff88"
            elif score >= 60:
                signal = "BUY"
                color = "#00cc00"
            elif score <= 35:
                signal = "SELL"
                color = "#ff3366"
            
            if is_high_risk and "BUY" in signal:
                 signal = "RISKY BUY ⚠️"
                 color = "yellow"

            sl = current_price - (2 * atr)
            target = current_price + (4 * atr)

            if score >= 80 and not is_high_risk and market_open: 
                current_time_stamp = time.time()
                last_alert = alert_history.get(symbol, 0)
                if (current_time_stamp - last_alert) > 2700:
                    t = threading.Thread(target=self.send_telegram, args=(symbol, signal, current_price, sl, target, reasons, risk_label))
                    t.start()
                    alert_history[symbol] = current_time_stamp

            result_data = {
                "Symbol": str(symbol),
                "Price": float(round(current_price, 2)),
                "Signal": str(signal),
                "Score": int(score),
                "Pattern": str(", ".join(reasons)) if reasons else "Normal Price Action",
                "Color": str(color),
                "Accuracy": float(ai_score),
                "Risk": str(risk_label) 
            }
            
            # ✅ Save this result in memory so we don't have to calculate again when market is closed
            last_scan_cache[symbol] = result_data
            
            return result_data

        except Exception as e:
            return None

    def scan_market(self, timeframe="15m"):
        results = []
        stock_list = getattr(symbols, 'WATCHLIST', [])
        
        for symbol in stock_list[:60]: 
            data = self.analyze_stock(symbol, timeframe)
            if data:
                results.append(data)
        
        results.sort(key=lambda x: x['Score'], reverse=True)
        return results

    def send_telegram(self, symbol, signal, price, sl, tgt, reasons, risk_label):
        if not config.TELEGRAM_TOKEN: return
        try:
            reason_str = "\n".join([f"• {r}" for r in reasons])
            msg = (
                f"🚀 *TRADE ALERT: {symbol}*\n"
                f"Signal: {signal}\n"
                f"Price: {price}\n"
                f"🛡️ Volatility: {risk_label}\n" 
                f"SL: {sl:.2f} | TGT: {tgt:.2f}\n"
                f"Logic:\n{reason_str}"
            )
            requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage", params={'chat_id': config.TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=5)
        except: pass

bot = MarketScanner() 
scan_market = bot.scan_market 
analyze_stock = bot.analyze_stock