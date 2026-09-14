# --- MARKET KINGS (Index Movers) ---
WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS",
    "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS",
    "ADANIENT.NS", "ADANIPORTS.NS",
    "TATAMOTORS.NS", "MARUTI.NS", "M&M.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", 
    "SUNPHARMA.NS", "ULTRACEMCO.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "TITAN.NS", "ASIANPAINT.NS"
]

# ✅ UPDATED: ALL INDICES (Sensex Added)
INDICES = ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTY IT", "NIFTY AUTO", "NIFTY METAL", "NIFTY PHARMA"]

# ✅ UPDATED: COMMODITY SECTION (MCX - Base Names for Auto-Expiry Logic)
COMMODITIES = [
    "CRUDEOIL", 
    "GOLD",
    "SILVER",
    "NATURALGAS"
]

# Baki backend files iska use karengi
ALL_STOCKS = WATCHLIST + INDICES + COMMODITIES

# ✅ THE MASTER SECTOR MAP 
SECTOR_MAP = {
    # IT Sector
    "INFY.NS": "NIFTY IT", 
    "TCS.NS": "NIFTY IT",
    
    # Auto Sector
    "TATAMOTORS.NS": "NIFTY AUTO", 
    "MARUTI.NS": "NIFTY AUTO", 
    "M&M.NS": "NIFTY AUTO", 
    "EICHERMOT.NS": "NIFTY AUTO", 
    "HEROMOTOCO.NS": "NIFTY AUTO",
    
    # Bank Sector
    "HDFCBANK.NS": "BANKNIFTY", 
    "ICICIBANK.NS": "BANKNIFTY", 
    "AXISBANK.NS": "BANKNIFTY", 
    "KOTAKBANK.NS": "BANKNIFTY", 
    "INDUSINDBK.NS": "BANKNIFTY", 
    "SBIN.NS": "BANKNIFTY",
    
    # Metal Sector
    "TATASTEEL.NS": "NIFTY METAL", 
    "JSWSTEEL.NS": "NIFTY METAL", 
    "HINDALCO.NS": "NIFTY METAL",
    
    # Pharma Sector
    "SUNPHARMA.NS": "NIFTY PHARMA"
}

def get_sector(symbol):
    """
    Stock ka naam dene par uska Sector wapas karega. 
    """
    # Agar symbol commodity ka hissa hai (Ex: CRUDEOIL24SEPFUT)
    if any(comm in symbol for comm in COMMODITIES):
        return "COMMODITY"
        
    # Agar symbol Sensex hai
    if "SENSEX" in symbol:
        return "SENSEX"
        
    return SECTOR_MAP.get(symbol, "NIFTY")