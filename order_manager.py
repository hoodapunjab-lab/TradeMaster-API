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

    def place_buy_order(self, symbol, price, sl, target, ai_conf):
        with self.lock:
            for t in self.active_trades:
                if t['symbol'] == symbol: return

            qty = rm.calculate_quantity(symbol, price, sl, ai_score=ai_conf)
            if qty == 0: return

            print(f"🚀 EXECUTING BUY: {symbol} | Qty: {qty} | Price: {price}")
            
            order_id = "PAPER_ID_123"
            if not PAPER_MODE:
                # ✅ LIMIT ORDER FIX (Slippage Safety: Max 0.2% upar tak hi lega)
                limit_price = round(price * 1.002, 2)
                order_id = session_manager.place_order(symbol, "BUY", qty, order_type="LIMIT", price=limit_price)
                if not order_id: 
                    print("❌ Broker Error: Order failed")
                    return

            trade = {
                "symbol": symbol, "type": "BUY", "entry_price": price, 
                "qty": qty, "sl": sl, "target": target, "order_id": order_id, 
                "status": "OPEN", "highest_price": price, "ai_conf": ai_conf, 
                "timestamp": str(datetime.now())
            }
            self.active_trades.append(trade)
            self.save_trades()
            
            mode_txt = "📝 PAPER TRADE" if PAPER_MODE else "💸 REAL MONEY"
            msg = (f"🔵 **BUY INITIATED ({mode_txt})**\n"
                   f"Symbol: {symbol}\nQty: {qty}\nPrice: {price}\n"
                   f"SL: {sl:.2f} | TGT: {target:.2f}\nAI Confidence: {ai_conf}%")
            self.send_telegram(msg)

    def close_trade(self, trade, exit_price, reason):
        with self.lock:
            print(f"🔴 CLOSING TRADE: {trade['symbol']} | Reason: {reason} | Price: {exit_price}")
            if not PAPER_MODE:
                session_manager.place_order(trade['symbol'], "SELL", trade['qty'], order_type="MARKET")
            
            pnl = (exit_price - trade['entry_price']) * trade['qty']
            self.active_trades.remove(trade)
            self.save_trades()
            
            emoji = "✅" if pnl > 0 else "❌"
            msg = (f"{emoji} **TRADE CLOSED**\nSymbol: {trade['symbol']}\n"
                   f"Reason: {reason}\nExit Price: {exit_price}\nPnL: ₹{pnl:.2f}")
            self.send_telegram(msg)

    def monitor_active_trades(self):
        if not self.active_trades: return
        print(f"👀 Monitoring {len(self.active_trades)} Active Trades...")
        
        trades_copy = self.active_trades[:] 
        for trade in trades_copy:
            try:
                ltp = session_manager.get_ltp(trade['symbol'])
                if ltp == 0: 
                    data = scanner.analyze_stock(trade['symbol'])
                    if data: ltp = data['Price']
                    else: continue
                
                if ltp > trade['highest_price']:
                    trade['highest_price'] = ltp
                
                # ✅ TRAILING SL UPGRADE: Risk lock karo agar 1.5% upar gaya
                if ltp > (trade['entry_price'] * 1.015):
                    # Lock thoda aur tight (0.8% below highest)
                    new_sl = trade['highest_price'] * 0.992 
                    if new_sl > trade['sl']:
                        trade['sl'] = new_sl
                        self.save_trades()

                if ltp >= trade['target']: self.close_trade(trade, ltp, "TARGET HIT 🎯")
                elif ltp <= trade['sl']: self.close_trade(trade, ltp, "STOPLOSS HIT 🛑")
                    
            except Exception as e:
                pass

    def scan_and_trade(self):
        if len(self.active_trades) >= MAX_TRADES: return
        print("🔎 Scanning Market for Opportunities...")
        
        opportunities = scanner.scan_market("15m")
        
        for opp in opportunities[:3]:
            symbol = opp['Symbol']
            price = opp['Price']
            
            if any(t['symbol'] == symbol for t in self.active_trades): continue
            
            # ✅ DOUBLE SECTOR VERIFICATION (Before Execution)
            if REGIME_AVAILABLE:
                stock_sector = symbols.get_sector(symbol)
                from data_engine import db_engine
                sector_df = db_engine.fetch_data(stock_sector, "15m", limit=50)
                if not sector_df.empty:
                    sector_trend = regime_detector.get_regime(sector_df)
                    if "DOWN" in sector_trend:
                        print(f"⚠️ Rejecting {symbol}: Sector {stock_sector} is Bearish.")
                        continue # Abort Trade!

            ai_res = brain.predict_signal(symbol)
            
            if ai_res['signal'] == "BUY" and ai_res['prob'] >= config.AI_CONFIDENCE_THRESHOLD:
                sl = price * 0.985  
                target = price * 1.03 
                self.place_buy_order(symbol, price, sl, target, ai_res['prob'])
                if len(self.active_trades) >= MAX_TRADES: break

    def run(self):
        print("🤖 AUTO TRADER STARTED...")
        if not session_manager.get_session():
            print("❌ Login Failed! Check Credentials.")
            return
        
        while True:
            try:
                self.monitor_active_trades()
                now = datetime.now()
                if now.minute % 2 == 0 and now.second < 10:
                   self.scan_and_trade()
                   time.sleep(10) 
                time.sleep(2) 
            except KeyboardInterrupt:
                break
            except Exception as e:
                time.sleep(5)

if __name__ == "__main__":
    bot = AutoTrader()
    bot.run()