from SmartApi import SmartConnect 
import pyotp 
import config
import symbols 
import time
import json
import os
import requests
from datetime import datetime

class SmartSessionManager:
    def __init__(self):
        self.api = None
        self.token_map = {} 
        self.last_login_time = 0
        self.session_expiry = 80000 
        self.load_token_map()

    def load_token_map(self):
        json_file = "angel_tokens.json"
        need_download = True

        if os.path.exists(json_file):
            file_time = os.path.getmtime(json_file)
            if (time.time() - file_time) < 43200: 
                with open(json_file, 'r') as f:
                    self.token_map = json.load(f)
                if len(self.token_map) > 10: 
                    need_download = False

        if need_download:
            print("⬇️ Downloading & Filtering Symbol Tokens (Auto-Expiry Mode for Oil & MCX)...")
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            
            try:
                response = requests.get(url, timeout=30)
                data = response.json()
                new_map = {}
                
                # Dictionary to hold all future contracts for commodities to sort by date
                mcx_contracts = {comm: [] for comm in symbols.COMMODITIES}
                watchlist_clean = set(s.replace('.NS', '').replace('-EQ', '') for s in symbols.WATCHLIST)
                today = datetime.today()
                
                for item in data:
                    sym = item.get('symbol', '')
                    exch = item.get('exch_seg', '')
                    token = item.get('token', '')
                    name = item.get('name', '')
                    expiry_str = item.get('expiry', '')
                    
                    # 1. NSE Equity
                    if exch == 'NSE' and sym.replace('-EQ', '') in watchlist_clean:
                        new_map[sym.replace('-EQ', '') + ".NS"] = token
                    
                    # 2. NSE Indices
                    if exch == 'NSE':
                        if sym == "Nifty 50": new_map["NIFTY"] = token
                        elif sym == "Nifty Bank": new_map["BANKNIFTY"] = token
                        elif sym == "Nifty IT": new_map["NIFTY IT"] = token
                        elif sym == "Nifty Auto": new_map["NIFTY AUTO"] = token
                        elif sym == "Nifty Metal": new_map["NIFTY METAL"] = token
                        elif sym == "Nifty Pharma": new_map["NIFTY PHARMA"] = token

                    # 3. BSE Index (SENSEX)
                    if exch == 'BSE' and sym == 'SENSEX':
                        new_map["SENSEX"] = token
                        
                    # 4. MCX Auto-Expiry Logic (Commodities including CRUDEOIL / OIL variations)
                    if exch == 'MCX' and name in symbols.COMMODITIES and 'FUT' in sym:
                        try:
                            exp_date = datetime.strptime(expiry_str, "%d%b%Y")
                            if exp_date >= today:
                                mcx_contracts[name].append({'symbol': sym, 'token': token, 'date': exp_date})
                        except: pass

                # Get the nearest expiry for MCX
                for comm, contracts in mcx_contracts.items():
                    if contracts:
                        contracts.sort(key=lambda x: x['date']) # Sort by nearest date
                        nearest = contracts[0]
                        new_map[comm] = nearest['token']
                        new_map[comm + "_ACTUAL_SYMBOL"] = nearest['symbol'] # Save the real symbol for Broker API
                
                # ✅ OIL ALIAS / MAPPING FIX: Ensure CRUDEOIL handles generic "OIL" queries seamlessly
                if "CRUDEOIL" in new_map:
                    new_map["OIL"] = new_map["CRUDEOIL"]
                    new_map["OIL_ACTUAL_SYMBOL"] = new_map["CRUDEOIL_ACTUAL_SYMBOL"]

                self.token_map = new_map
                with open(json_file, 'w') as f:
                    json.dump(self.token_map, f)
                
            except Exception as e:
                print(f"❌ Token Download Failed: {e}")

    def get_token(self, symbol):
        # ✅ Handle 'OIL' mapping alias directly
        if symbol == "OIL": symbol = "CRUDEOIL"
        if symbol in self.token_map: return self.token_map[symbol]
        if symbol + ".NS" in self.token_map: return self.token_map[symbol + ".NS"]
        clean = symbol.replace(".NS", "")
        if clean in self.token_map: return self.token_map[clean]
        return None

    def get_session(self):
        current_time = time.time()
        if self.api and (current_time - self.last_login_time) < self.session_expiry:
            return self.api

        for i in range(1, 4): 
            try:
                temp_api = SmartConnect(api_key=config.API_KEY)
                totp = pyotp.TOTP(config.TOTP_KEY).now()
                data = temp_api.generateSession(config.CLIENT_ID, config.MPIN, totp)
                
                if data['status']:
                    self.api = temp_api
                    self.last_login_time = current_time
                    if not self.token_map: self.load_token_map()
                    return self.api
                else: time.sleep(1)
            except Exception as e: time.sleep(1)
        return None

    # ✅ DYNAMIC EXCHANGE ROUTING LOGIC WITH OIL SUPPORT
    def get_exchange_and_symbol(self, symbol):
        if symbol == "OIL": symbol = "CRUDEOIL"
        exch = "NSE"
        trade_sym = symbol.replace(".NS", "")
        
        if symbol == "SENSEX":
            exch = "BSE"
        elif any(comm in symbol for comm in symbols.COMMODITIES) or symbol == "CRUDEOIL":
            exch = "MCX"
            # MCX me order lagane ke liye real symbol (e.g., CRUDEOIL19OCT23FUT) chahiye
            if symbol + "_ACTUAL_SYMBOL" in self.token_map:
                trade_sym = self.token_map[symbol + "_ACTUAL_SYMBOL"]
        elif "CE" in symbol or "PE" in symbol:
            exch = "BFO" if "SENSEX" in symbol else "NFO"
            
        return exch, trade_sym

    def place_order(self, symbol, transaction_type, qty, order_type="MARKET", price=0, product_type="INTRADAY", variety="NORMAL"):
        api = self.get_session()
        if not api: return None

        try:
            token = self.get_token(symbol)
            if not token: return None

            exch, trade_sym = self.get_exchange_and_symbol(symbol)

            orderparams = {
                "variety": variety,
                "tradingsymbol": trade_sym, 
                "symboltoken": token,
                "transactiontype": transaction_type, 
                "exchange": exch,
                "ordertype": order_type, 
                "producttype": product_type,
                "duration": "DAY",
                "price": price, 
                "quantity": qty
            }
            
            order_id = api.placeOrder(orderparams)
            return order_id

        except Exception as e:
            print(f"❌ Order Execution Failed: {e}")
            return None

    def get_ltp(self, symbol):
        api = self.get_session()
        if not api: return 0
        token = self.get_token(symbol)
        if not token: return 0
        
        exch, trade_sym = self.get_exchange_and_symbol(symbol)
        try:
            data = api.ltpData(exch, trade_sym, token)
            if data['status']:
                return data['data']['ltp']
        except: pass
        return 0

session_manager = SmartSessionManager()