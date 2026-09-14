import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.volatility import AverageTrueRange
import requests
import time
from datetime import datetime, time as dtime
import threading
import warnings
import config
import pytz
import traceback

# Database Import
from data_engine import db_engine
from ai_brain import TradeBrain

warnings.filterwarnings('ignore')
brain = TradeBrain()

# Cache System (Memory)
cache_data = {
    "NIFTY": {"last_update": 0, "data": None, "last_alert_time": 0, "last_score": 50}, 
    "BANKNIFTY": {"last_update": 0, "data": None, "last_alert_time": 0, "last_score": 50}
}

def get_atm_strike(symbol, spot_price):
    try:
        step = 50 if "NIFTY" in symbol and "BANK" not in symbol else 100
        strike = round(spot_price / step) * step
        return int(strike)
    except: return 0

# ✅ FIXED: Default timeframe changed from "15m" to "5m"
def fetch_data_smart(symbol, timeframe="5m"):
    """
    ✅ 100% ANGEL ONE DATABASE FETCH
    """
    if "NIFTY" in symbol and "BANK" not in symbol and symbol == "NIFTY":
        db_sym = "NIFTY 50"
    elif "BANK" in symbol and symbol == "BANKNIFTY":
        db_sym = "BANK NIFTY"
    else:
        db_sym = symbol
        
    try:
        df = db_engine.fetch_data(db_sym, timeframe, limit=500)
        
        if df.empty:
            df = db_engine.fetch_data(symbol, timeframe, limit=500)
            
        if not df.empty:
            df.columns = [str(c).lower() for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            return df
            
    except Exception as e:
        print(f"⚠️ DB Read Error {symbol}: {e}")

    return pd.DataFrame()

def is_market_open():
    try:
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        if now.weekday() > 4: return False 
        return dtime(9, 15) <= now.time() <= dtime(15, 30)
    except: return False

def send_telegram_thread(symbol, signal, price, atm_strike, score, reason, sl, tgt):
    try:
        if not config.TELEGRAM_TOKEN: return
        emoji = "🟢" if "CE" in signal else "🔴"
        opt_type = "CE" if "CE" in signal else "PE"
        
        msg = (
            f"{emoji} **INDEX OPTION ALERT** {emoji}\n\n"
            f"⚡ **{symbol} {atm_strike} {opt_type}**\n"
            f"Signal: {signal}\n"
            f"📊 Score: {score}/100\n"
            f"💰 Spot: {price}\n"
            f"🛑 SL: {sl} | 🎯 TGT: {tgt}\n"
            f"💡 Logic: {reason}"
        )
        requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage", 
                     params={'chat_id': config.TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=5)
    except: pass

def get_scalar(val):
    if isinstance(val, pd.Series):
        return float(val.iloc[-1])
    if isinstance(val, np.ndarray):
        return float(val[-1])
    return float(val)

def analyze_option_chain(symbol):
    global cache_data
    current_time_epoch = time.time()
    
    if symbol not in cache_data:
        cache_data[symbol] = {"last_update": 0, "data": None, "last_alert_time": 0, "last_score": 50}

    if (current_time_epoch - cache_data[symbol]["last_update"]) < 2 and cache_data[symbol]["data"]: 
        return cache_data[symbol]["data"]

    try:
        # ✅ FIXED: Now strictly fetching 5m data to match our fast system
        df = fetch_data_smart(symbol, "5m")
        
        # ✅ FIXED: Requires at least 60 candles because EMA-50 will fail otherwise
        if df.empty or len(df) < 60: 
            return {"pcr": "Wait", "trend": "LOADING...", "support": 0, "resistance": 0, "signal": "WAITING", "color": "gray", "strike": 0, "sentiment": "Neutral", "sentiment_color": "gray", "gap_prediction": {"prediction": "Wait", "color": "gray"}}

        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        current_price = get_scalar(close)
        
        # --- Indicators ---
        try:
            ema_20 = get_scalar(EMAIndicator(close, window=20).ema_indicator())
            ema_50 = get_scalar(EMAIndicator(close, window=50).ema_indicator())
            macd = get_scalar(MACD(close).macd_diff())
            atr = get_scalar(AverageTrueRange(high, low, close, window=14).average_true_range())
            adx = get_scalar(ADXIndicator(high, low, close, window=14).adx())
            rsi = get_scalar(RSIIndicator(close, window=14).rsi())
        except Exception as e:
            adx = 20; rsi = 50; atr = current_price * 0.01; ema_20 = current_price; ema_50 = current_price

        # Pivot Points
        high_5 = get_scalar(high.rolling(5).max())
        low_5 = get_scalar(low.rolling(5).min())
        
        pivot = (high_5 + low_5 + current_price) / 3
        
        r1 = int((2 * pivot) - low_5)
        s1 = int((2 * pivot) - high_5)

        # AI Prediction
        ai_score = 0
        ai_signal = "NEUTRAL"
        try:
            brain_sym = symbol.replace("NIFTY", "NIFTY 50").replace("BANKNIFTY", "BANK NIFTY")
            ai_msg = brain.predict_signal(brain_sym)
            ai_signal = ai_msg.get('signal', "NEUTRAL")
        except: pass

        # --- SCORING LOGIC ---
        raw_score = 50
        trend = "SIDEWAYS"
        
        if current_price > ema_20:
            raw_score += 10
            if current_price > ema_50: raw_score += 10
        elif current_price < ema_20:
            raw_score -= 10
            if current_price < ema_50: raw_score -= 10
        
        if macd > 0: raw_score += 10
        else: raw_score -= 10
        
        if rsi > 55: raw_score += 10
        elif rsi < 45: raw_score -= 10
        
        if ai_signal == "BUY": raw_score += 15
        elif ai_signal == "SELL": raw_score -= 15

        if adx < 20:
            trend = "CHOPPY"
            if raw_score > 50: raw_score -= 10
            elif raw_score < 50: raw_score += 10

        # Smoothing
        last_score = cache_data[symbol].get("last_score", 50)
        final_score = int((raw_score * 0.7) + (last_score * 0.3))
        cache_data[symbol]["last_score"] = final_score
        score = final_score

        # Signals
        signal = "NEUTRAL"; color = "gray"
        sl = 0; tgt = 0
        atm_strike = get_atm_strike(symbol, current_price)

        if score >= 65: 
            signal = "BUY CE 🚀"
            color = "#00ff88"
            trend = "BULLISH"
            sl = round(current_price - (1.5 * atr), 2)
            tgt = round(current_price + (3 * atr), 2)
            
        elif score <= 35:
            signal = "BUY PE 🩸"
            color = "#ff4d4d"
            trend = "BEARISH"
            sl = round(current_price + (1.5 * atr), 2)
            tgt = round(current_price - (3 * atr), 2)

        # Alert Logic
        if is_market_open() and ("CE" in signal or "PE" in signal):
            # ✅ FIXED: Changed 900 (15 mins) to 300 (5 mins). Ab delay nahi hoga!
            if (current_time_epoch - cache_data[symbol]["last_alert_time"]) > 300: 
                t = threading.Thread(target=send_telegram_thread, args=(symbol, signal, current_price, atm_strike, score, "Trend Follow", sl, tgt))
                t.start()
                cache_data[symbol]["last_alert_time"] = current_time_epoch

        trend_strength = int(abs(score - 50) * 2)
        if trend_strength == 0: trend_strength = 5

        result = {
            "pcr": f"{trend_strength}%",
            "trend": trend,
            "support": s1,
            "resistance": r1,
            "signal": signal,
            "color": color,
            "strike": atm_strike,
            "sentiment": trend,
            "sentiment_color": color if trend != "SIDEWAYS" else "orange",
            "gap_prediction": {"prediction": "Active", "color": "white"}
        }
        
        cache_data[symbol]["data"] = result
        cache_data[symbol]["last_update"] = current_time_epoch
        return result

    except Exception as e:
        print(f"❌ CRITICAL ERROR in {symbol}: {e}")
        return {"pcr": "ERR", "trend": "ERROR", "support": 0, "resistance": 0, "signal": "WAIT", "color": "yellow", "strike": 0, "sentiment": "Error", "sentiment_color": "yellow", "gap_prediction": {"prediction": "Wait", "color": "yellow"}}