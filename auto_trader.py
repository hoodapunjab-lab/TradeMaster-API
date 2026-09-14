import time
import json
import os
import threading
import requests
import pandas as pd
from datetime import datetime

import scanner          
import symbols
import config
from smart_session import session_manager
from ai_brain import TradeBrain
from risk_manager import risk_manager as rm

# Import Market Regime for Sector Checks
try:
    from market_regime import regime_detector
    REGIME_AVAILABLE = True
except:
    REGIME_AVAILABLE = False

PAPER_MODE = True  

MAX_TRADES = config.MAX_TRADES_PER_DAY
TRADES_FILE = "current_trades.json"
brain = TradeBrain()

class AutoTrader:
    def __init__(self):
        self.active_trades = self.load_trades()
        self.lock = threading.Lock() 
        
    def load_trades(self):
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, "r") as f: return json.load(f)
            except: return []
        return []

    def save_trades(self):
        try:
            with open(TRADES_FILE, "w") as f: json.dump(self.active_trades, f, indent=4)
        except: pass

    def send_telegram(self, msg):
        if not config.TELEGRAM_TOKEN: return
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
            requests.get(url, params={'chat_id': config.TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=5)
        except: pass

    # ✅ FIXED: Now properly handles BOTH Buy and Sell via unified place_order method
    def place_order(self, symbol, trade_type, price, sl, target, ai_conf):
        with self.lock:
            for t in self.active_trades:
                if t['symbol'] == symbol: return

            qty = rm.calculate_quantity(symbol, price, sl, ai_score=ai_conf)
            if qty == 0: return

            print(f"🚀 EXECUTING {trade_type}: {symbol} | Qty: {qty} | Price: {price}")
            
            order_id = "PAPER_ID_123"
            if not PAPER_MODE:
                # ✅ Pass trade_type dynamically (BUY or SELL)
                order_id = session_manager.place_order(symbol, trade_type, qty)
                if not order_id: return

            trade = {
                "symbol": symbol,
                "type": trade_type, # BUY ya SELL
                "entry_price": price,
                "qty": qty,
                "sl": sl,
                "target": target,
                "order_id": order_id,
                "status": "OPEN",
                "highest_price": price, # Long trailing ke liye
                "lowest_price": price,  # Short trailing ke liye
                "ai_conf": ai_conf,
                "timestamp": str(datetime.now())
            }
            self.active_trades.append(trade)
            self.save_trades()
            
            mode_txt = "📝 PAPER" if PAPER_MODE else "💸 REAL"
            color = "🟢" if trade_type == "BUY" else "🔴"
            msg = (f"{color} **{trade_type} INITIATED ({mode_txt})**\n"
                   f"Symbol: {symbol} | Qty: {qty}\nPrice: {price}\n"
                   f"SL: {sl:.2f} | TGT: {target:.2f}\nAI Conf: {ai_conf}%")
            self.send_telegram(msg)

    def close_trade(self, trade, exit_price, reason):
        with self.lock:
            print(f"🔴 CLOSING TRADE: {trade['symbol']} | Reason: {reason} | Price: {exit_price}")
            
            # Agar BUY tha toh SELL order dalo close karne ke liye, aur vice-versa
            exit_order_type = "SELL" if trade.get('type', 'BUY') == "BUY" else "BUY"
            
            if not PAPER_MODE:
                session_manager.place_order(trade['symbol'], exit_order_type, trade['qty'])
            
            # ✅ PNL Logic for both Buy and Sell
            if trade.get('type', 'BUY') == "BUY":
                pnl = (exit_price - trade['entry_price']) * trade['qty']
            else:
                pnl = (trade['entry_price'] - exit_price) * trade['qty']
            
            self.active_trades.remove(trade)
            self.save_trades()
            
            emoji = "✅" if pnl > 0 else "❌"
            msg = (f"{emoji} **TRADE CLOSED ({trade.get('type', 'BUY')})**\n"
                   f"Symbol: {trade['symbol']}\nReason: {reason}\n"
                   f"Exit Price: {exit_price}\nPnL: ₹{pnl:.2f}")
            self.send_telegram(msg)

    def monitor_active_trades(self):
        if not self.active_trades: return
        
        trades_copy = self.active_trades[:] 

        for trade in trades_copy:
            try:
                ltp = session_manager.get_ltp(trade['symbol'])
                if ltp == 0: 
                    data = scanner.analyze_stock(trade['symbol'])
                    if data: ltp = data['Price']
                    else: continue
                
                trade_type = trade.get('type', 'BUY')

                # ✅ DYNAMIC TRAILING SL (BUY & SELL Both)
                if trade_type == "BUY":
                    if ltp > trade['highest_price']: trade['highest_price'] = ltp
                    
                    if ltp > (trade['entry_price'] * 1.01): # 1% profit mein aane par
                        new_sl = ltp * 0.995 
                        if new_sl > trade['sl']:
                            trade['sl'] = new_sl
                            print(f"🛡️ {trade['symbol']} (BUY): Trailing SL moved up to {new_sl:.2f}")
                            
                    # Exit Check BUY
                    if ltp >= trade['target']: self.close_trade(trade, ltp, "TARGET HIT 🎯")
                    elif ltp <= trade['sl']: self.close_trade(trade, ltp, "STOPLOSS HIT 🛑")

                elif trade_type == "SELL":
                    # Initialize lowest_price if old trade doesn't have it
                    if 'lowest_price' not in trade: trade['lowest_price'] = trade['entry_price']
                    
                    if ltp < trade['lowest_price']: trade['lowest_price'] = ltp
                    
                    if ltp < (trade['entry_price'] * 0.99): # 1% profit mein aane par (price gira)
                        new_sl = ltp * 1.005 
                        if new_sl < trade['sl']:
                            trade['sl'] = new_sl
                            print(f"🛡️ {trade['symbol']} (SELL): Trailing SL moved down to {new_sl:.2f}")

                    # Exit Check SELL
                    if ltp <= trade['target']: self.close_trade(trade, ltp, "TARGET HIT 🎯")
                    elif ltp >= trade['sl']: self.close_trade(trade, ltp, "STOPLOSS HIT 🛑")
                    
            except Exception as e:
                print(f"Monitor Error {trade['symbol']}: {e}")

    def scan_and_trade(self):
        """
        Naye trades dhoondne ka logic (Upgraded for BUY & SELL)
        """
        if len(self.active_trades) >= MAX_TRADES: return

        print("🔎 Scanning Market for Opportunities...")
        
        # ✅ TIME FRAME CHANGED TO 5M FOR FAST SIGNALS
        opportunities = scanner.scan_market("5m")
        
        for opp in opportunities[:3]:
            symbol = opp['Symbol']
            price = opp['Price']
            
            if any(t['symbol'] == symbol for t in self.active_trades): continue
            
            print(f"🧠 Asking AI about {symbol}...")
            ai_res = brain.predict_signal(symbol)
            
            # ✅ BUY LOGIC (Long)
            if ai_res['signal'] == "BUY" and ai_res['prob'] > 60:
                sl = price * 0.985  # 1.5% SL Below
                target = price * 1.03 # 3% Target Above
                self.place_order(symbol, "BUY", price, sl, target, ai_res['prob'])
                if len(self.active_trades) >= MAX_TRADES: break
                
            # ✅ SELL LOGIC (Shorting for falling market)
            elif ai_res['signal'] == "SELL" and ai_res['prob'] > 60:
                sl = price * 1.015  # 1.5% SL Above price
                target = price * 0.97 # 3% Target Below price
                self.place_order(symbol, "SELL", price, sl, target, ai_res['prob'])
                if len(self.active_trades) >= MAX_TRADES: break

    def run(self):
        print("🤖 AUTO TRADER STARTED...")
        print(f"📝 MODE: {'PAPER TRADING (Safe)' if PAPER_MODE else 'REAL MONEY (Risky) ⚠️'}")
        
        if not session_manager.get_session():
            print("❌ Login Failed! Check Credentials.")
            return
        
        last_scan_time = 0
        
        while True:
            try:
                # 1. Manage Active Trades (Runs every iteration)
                self.monitor_active_trades()
                
                # 2. Naye trades dhoondo (Har 60 second mein ek baar, bina time block kiye)
                current_time = time.time()
                if current_time - last_scan_time > 60:  # Har 1 minute baad scan
                    self.scan_and_trade()
                    last_scan_time = time.time()
                
                time.sleep(2) # CPU Cooling (2 sec theek hai API ban bachane ke liye)
                
            except KeyboardInterrupt:
                print("\n🛑 Stopping Bot...")
                break
            except Exception as e:
                print(f"❌ Main Loop Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    bot = AutoTrader()
    bot.run()