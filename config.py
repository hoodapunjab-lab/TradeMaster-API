import os

# --- 1. BROKER CREDENTIALS (ANGEL ONE) ---
API_KEY = "ATM2q52x"
CLIENT_ID = "V90362"
MPIN = "2727" 
TOTP_KEY = "4NLG2ZCHP5NS5N2XYRUUKBQ4VA"

# --- 2. TELEGRAM ALERTS ---
TELEGRAM_TOKEN = "8516180035:AAFghjx4H1jc6ADFtkegWELX42ZQG99HBuY"
TELEGRAM_CHAT_ID = "6911195221"

# --- 3. SYSTEM SETTINGS ---
DB_NAME = "trademaster_pro.db"
TIME_ZONE = "Asia/Kolkata"

# --- 4. TRADING LOGIC SETTINGS ---
CAPITAL = 100000  # Aapka total trading capital (₹)

# ✅ LAG FIX: 15m se hata kar 5m kar diya hai fast signals ke liye
SCAN_INTERVAL = "5m"    

# ✅ ACCURACY FIX: 80-90% accuracy ke liye filters strict kiye hain
MIN_SCORE_TO_BUY = 65   # Pehle 50 tha, ab sirf strong uptrend mein buy karega
MIN_SCORE_TO_SELL = 35  # NAYA: Agar score 35 se neeche ho toh Short Sell karega
MIN_SCORE_TO_GOD_MODE = 80

# Risk Management
MAX_TRADES_PER_DAY = 5
RISK_PER_TRADE = 2000   # Maximum loss per trade
MAX_LOSS_DAY = 5000     # System stop loss
TARGET_DAY = 10000      # Target profit for the day

# ✅ AI Settings (Accuracy Boost)
AI_CONFIDENCE_THRESHOLD = 65 # Pehle 60 tha, ab AI zyada sure hone par hi trade lega
ENABLE_ML_TRAP_DETECTION = True

# Sectors to Track
SECTORS_TO_TRACK = ["NIFTY IT", "NIFTY AUTO", "NIFTY METAL", "NIFTY PHARMA", "BANKNIFTY", "NIFTY 50", "SENSEX"]

# Commodity / Market Timings
MCX_MARKET_CLOSE_HOUR = 23
MCX_MARKET_CLOSE_MINUTE = 55
NSE_MARKET_CLOSE_HOUR = 15
NSE_MARKET_CLOSE_MINUTE = 15 # 3:15 PM par intraday square-off ke liye (Important!)

# --- 5. PATHS ---
MODELS_DIR = "models/"
LOGS_DIR = "logs/"

# Directory creation check
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)