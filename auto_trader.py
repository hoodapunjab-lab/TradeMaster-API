# FILE NAME: order_manager.py

import time
import json
import os
import threading
import requests
import pandas as pd
from datetime import datetime

# --- CUSTOM MODULES ---
import scanner          
import symbols
import config
from smart_session import session_manager
from ai_brain import TradeBrain

# ✅ RISK MANAGER IMPORT (Ab ye nayi file se connect ho gaya)
from risk_manager import risk_manager as rm

# --- SETTINGS ---
# ⚠️ WARNING: Ise 'False' karne se ASLI PAISA lagna shuru ho jayega!
PAPER_MODE = True  

MAX_TRADES = 5     # Ek time par max kitne trade open rahenge
TRADES_FILE = "current_trades.json"

# Initialize AI
brain = TradeBrain()

# --- AUTO TRADER CLASS ---
class AutoTrader:
    def __init__(self):
        self.active_trades = self.load_trades()
        self.lock = threading.Lock() # Thread safety ke liye
        
    def load_trades(self):
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, "r") as f:
                    return json.load(f)
            except: return []
        return []

    def save_trades(self):
        try:
            with open(TRADES_FILE, "w") as f:
                json.dump(self.active_trades, f, indent=4)
        except Exception as e:
            print(f"⚠️ Save Error: {e}")

    def send_telegram(self, msg):
        if not config.TELEGRAM_TOKEN: return
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
            requests.get(url, params={'chat_id': config.TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=5)
        except: pass

    def place_buy_order(self, symbol, price, sl, target, ai_conf):
        with self.lock:
            # 1. Check Duplicates
            for t in self.active_trades:
                if t['symbol'] == symbol: return

            # 2. Calculate Quantity (Using External Risk Manager)
            # AI Score bhej rahe hain taaki agar confidence high ho to risk badhaye
            qty = rm.calculate_quantity(symbol, price, sl, ai_score=ai_conf)
            
            if qty == 0: 
                print(f"🚫 Risk Manager rejected trade for {symbol} (Qty 0)")
                return

            print(f"🚀 EXECUTING BUY: {symbol} | Qty: {qty} | Price: {price}")
            
            # 3. EXECUTION (Paper vs Real)
            order_id = "PAPER_ID_123"
            if not PAPER_MODE:
                # Asli Order
                order_id = session_manager.place_order(symbol, "BUY", qty)
                if not order_id: 
                    print("❌ Broker Error: Order failed")
                    return

            # 4. Save to List
            trade = {
                "symbol": symbol,
                "type": "BUY",
                "entry_price": price,
                "qty": qty,
                "sl": sl,
                "target": target,
                "order_id": order_id,
                "status": "OPEN",
                "highest_price": price, # Trailing ke liye
                "ai_conf": ai_conf,
                "timestamp": str(datetime.now())
            }
            self.active_trades.append(trade)
            self.save_trades()
            
            # 5. Alert
            mode_txt = "📝 PAPER TRADE" if PAPER_MODE else "💸 REAL MONEY"
            msg = (f"🔵 **BUY INITIATED ({mode_txt})**\n"
                   f"Symbol: {symbol}\n"
                   f"Qty: {qty}\n"
                   f"Price: {price}\n"
                   f"SL: {sl:.2f} | TGT: {target:.2f}\n"
                   f"AI Confidence: {ai_conf}%")
            self.send_telegram(msg)

    def close_trade(self, trade, exit_price, reason):
        with self.lock:
            print(f"🔴 CLOSING TRADE: {trade['symbol']} | Reason: {reason} | Price: {exit_price}")
            
            # Real Order Exit
            if not PAPER_MODE:
                session_manager.place_order(trade['symbol'], "SELL", trade['qty'])
            
            # PnL Calculation
            pnl = (exit_price - trade['entry_price']) * trade['qty']
            
            self.active_trades.remove(trade)
            self.save_trades()
            
            emoji = "✅" if pnl > 0 else "❌"
            msg = (f"{emoji} **TRADE CLOSED**\n"
                   f"Symbol: {trade['symbol']}\n"
                   f"Reason: {reason}\n"
                   f"Exit Price: {exit_price}\n"
                   f"PnL: ₹{pnl:.2f}")
            self.send_telegram(msg)

    def monitor_active_trades(self):
        """
        Ye function har second chalta hai aur check karta hai:
        1. Target Hit?
        2. SL Hit?
        3. Trail SL karna hai kya?
        """
        if not self.active_trades: return

        print(f"👀 Monitoring {len(self.active_trades)} Active Trades...")
        
        # Copy list to avoid error while removing items
        trades_copy = self.active_trades[:] 

        for trade in trades_copy:
            try:
                # Live Price lao
                ltp = session_manager.get_ltp(trade['symbol'])
                
                # Agar Broker API price nahi de raha, to Scanner se backup price lo
                if ltp == 0: 
                    data = scanner.analyze_stock(trade['symbol'])
                    if data: ltp = data['Price']
                    else: continue
                
                # --- TRAILING SL LOGIC (The Money Maker) ---
                if ltp > trade['highest_price']:
                    trade['highest_price'] = ltp
                
                # Agar price Entry se 1% upar gaya hai
                if ltp > (trade['entry_price'] * 1.01):
                    # Naya SL = Current Price se 0.5% neeche (Profit Lock)
                    new_sl = ltp * 0.995 
                    if new_sl > trade['sl']:
                        trade['sl'] = new_sl
                        print(f"🛡️ {trade['symbol']}: Trailing SL moved to {new_sl:.2f}")

                # --- EXIT CHECKS ---
                if ltp >= trade['target']:
                    self.close_trade(trade, ltp, "TARGET HIT 🎯")
                elif ltp <= trade['sl']:
                    self.close_trade(trade, ltp, "STOPLOSS HIT 🛑")
                    
            except Exception as e:
                print(f"Monitor Error {trade['symbol']}: {e}")

    def scan_and_trade(self):
        """
        Naye trades dhoondne ka logic
        """
        if len(self.active_trades) >= MAX_TRADES: return

        print("🔎 Scanning Market for Opportunities...")
        
        # 1. Scanner se poocho (Technical Analysis)
        opportunities = scanner.scan_market("15m")
        
        # Top 3 stocks hi check karo
        for opp in opportunities[:3]:
            symbol = opp['Symbol']
            price = opp['Price']
            score = opp['Score']
            
            # Check duplicates
            if any(t['symbol'] == symbol for t in self.active_trades): continue
            
            # 2. AI Brain se poocho (Deep Learning)
            print(f"🧠 Asking AI about {symbol}...")
            ai_res = brain.predict_signal(symbol)
            
            # Agar Scanner + AI dono Bullish hain
            # AI Probability > 60% honi chahiye
            if ai_res['signal'] == "BUY" and ai_res['prob'] > 60:
                
                # Dynamic SL & Target
                # SL thoda tight rakhenge (Scanner ke SL se verify kar sakte hain)
                sl = price * 0.985  # 1.5% SL
                target = price * 1.03 # 3% Target
                
                self.place_buy_order(symbol, price, sl, target, ai_res['prob'])
                
                if len(self.active_trades) >= MAX_TRADES: break

    def run(self):
        print("🤖 AUTO TRADER STARTED...")
        print(f"📝 MODE: {'PAPER TRADING (Safe)' if PAPER_MODE else 'REAL MONEY (Risky) ⚠️'}")
        
        # Login Check
        if not session_manager.get_session():
            print("❌ Login Failed! Check Credentials.")
            return
        
        while True:
            try:
                # 1. Jo trades open hain, unhe manage karo (Fast)
                self.monitor_active_trades()
                
                # 2. Naye trades dhoondo (Slow - Every 2 mins)
                now = datetime.now()
                if now.minute % 2 == 0 and now.second < 10:
                   self.scan_and_trade()
                   time.sleep(10) # Ek baar scan karke thoda ruko
                
                time.sleep(2) # CPU Cooling
                
            except KeyboardInterrupt:
                print("\n🛑 Stopping Bot...")
                break
            except Exception as e:
                print(f"❌ Main Loop Error: {e}")
                time.sleep(5)

# Entry Point
if __name__ == "__main__":
    bot = AutoTrader()
    bot.run()