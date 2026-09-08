import math
import config 

class RiskManager:
    def __init__(self, capital=None, risk_per_trade_percent=2.0):
        self.capital = capital if capital else config.CAPITAL
        self.risk_pct = risk_per_trade_percent
        
        # ✅ UPDATED: Added MCX Commodities Lot Sizes
        self.LOT_SIZES = {
            "NIFTY": 25,       
            "BANKNIFTY": 15,   
            "FINNIFTY": 25,    
            "MIDCPNIFTY": 50,
            "SENSEX": 10,
            "CRUDEOIL": 100,      # 1 Lot = 100 Barrels
            "CRUDEOILM": 10,      # Mini
            "NATURALGAS": 1250,   # 1 Lot = 1250 mmBtu
            "GOLD": 100,          # 1 Kg
            "GOLDM": 10,          # Mini
            "SILVER": 30,         # 30 Kg
            "SILVERM": 5          # Mini
        }

    def calculate_quantity(self, symbol, entry_price, sl_price, ai_score=0):
        try:
            if entry_price <= 0 or sl_price <= 0: return 0

            # 1. Base Risk Calculation
            base_risk_amount = self.capital * (self.risk_pct / 100)
            
            # 2. AI Scaling
            multiplier = 1.0
            if ai_score >= 80: multiplier = 1.25   
            elif ai_score >= 90: multiplier = 1.5  
            elif ai_score < 50: multiplier = 0.5   
            
            max_risk_amount = base_risk_amount * multiplier
            sl_gap = abs(entry_price - sl_price)
            
            if sl_gap == 0: return 0
            
            clean_sym = symbol.upper().replace(".NS", "").replace("-EQ", "")
            
            # ✅ OPTION DELTA FIX
            if "CE" in clean_sym or "PE" in clean_sym:
                real_sl_gap = sl_gap * 0.5 
            else:
                real_sl_gap = sl_gap

            # 3. Raw Quantity
            raw_qty = max_risk_amount / real_sl_gap
            
            # 4. Lot Size Handling (Indices & Commodities)
            final_qty = 0
            lot_size = 1
            is_lot_based = False
            margin_req = 1.0  # Default 100% margin for cash/options

            if any(idx in clean_sym for idx in ["NIFTY", "SENSEX", "BANK"]):
                is_lot_based = True
                if "BANKNIFTY" in clean_sym: lot_size = self.LOT_SIZES["BANKNIFTY"]
                elif "FINNIFTY" in clean_sym: lot_size = self.LOT_SIZES["FINNIFTY"]
                elif "MIDCP" in clean_sym: lot_size = self.LOT_SIZES["MIDCPNIFTY"]
                elif "SENSEX" in clean_sym: lot_size = self.LOT_SIZES["SENSEX"]
                else: lot_size = self.LOT_SIZES["NIFTY"]
                
            elif any(comm in clean_sym for comm in ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"]):
                is_lot_based = True
                margin_req = 0.10  # ✅ 10% Margin requirement for MCX Futures
                
                if "CRUDEOILM" in clean_sym: lot_size = self.LOT_SIZES["CRUDEOILM"]
                elif "CRUDEOIL" in clean_sym: lot_size = self.LOT_SIZES["CRUDEOIL"]
                elif "NATURALGAS" in clean_sym: lot_size = self.LOT_SIZES["NATURALGAS"]
                elif "GOLDM" in clean_sym: lot_size = self.LOT_SIZES["GOLDM"]
                elif "GOLD" in clean_sym: lot_size = self.LOT_SIZES["GOLD"]
                elif "SILVERM" in clean_sym: lot_size = self.LOT_SIZES["SILVERM"]
                elif "SILVER" in clean_sym: lot_size = self.LOT_SIZES["SILVER"]

            if is_lot_based:
                num_lots = math.floor(raw_qty / lot_size)
                final_qty = num_lots * lot_size
                if num_lots < 1: return 0
            else:
                final_qty = math.floor(raw_qty)
            
            # 5. Capital Safety Check (Max 25% of capital per trade)
            max_capital_allowed = self.capital * 0.25 
            required_capital = final_qty * entry_price * margin_req
            
            if required_capital > max_capital_allowed:
                max_affordable_qty = max_capital_allowed / (entry_price * margin_req)
                if is_lot_based:
                    final_qty = int(max_affordable_qty // lot_size) * lot_size
                else:
                    final_qty = int(max_affordable_qty)

            if (final_qty * entry_price * margin_req) > self.capital:
                 max_affordable_qty = self.capital / (entry_price * margin_req)
                 if is_lot_based:
                     final_qty = int(max_affordable_qty // lot_size) * lot_size
                 else:
                     final_qty = int(max_affordable_qty)

            return int(final_qty)

        except Exception as e:
            return 0

risk_manager = RiskManager()