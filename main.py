import os
import json
import time
import asyncio
import threading
import warnings
import concurrent.futures
from datetime import datetime, time as dt_time
import yfinance as yf
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import symbols

warnings.filterwarnings('ignore')

app = FastAPI(title="TradeMaster Pro API")

# --- GLOBAL OBJECTS ---
brain = None 

market_status_cache = {
    "data": [],
    "last_updated": 0
}

# ✅ ANTI-SPAM FLAG: Server ko multiple same requests execute karne se rokega
is_updating_status = False 

executor = concurrent.futures.ThreadPoolExecutor(max_workers=15)

# ✅ UPDATED CORS POLICY (For HTTPS Live Website)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://trademaster-web.web.app", 
        "https://trademaster-web.firebaseapp.com",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "*" # Fallback
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*", "Authorization", "Content-Type", "ngrok-skip-browser-warning", "Access-Control-Allow-Origin"],
)

if not os.path.exists("static"): os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")


def update_market_status_bg():
    global market_status_cache, is_updating_status

    # ✅ FIX: Agar already update chal raha hai, ya 5 sec nahi huye, toh reject kar do
    if is_updating_status or (time.time() - market_status_cache['last_updated'] < 5):
        return

    is_updating_status = True

    try:
        try:
            from smart_session import session_manager
        except:
            session_manager = None

        status = []

        indices = [
            {"name": "NIFTY 50", "symbol": "NIFTY", "y": "^NSEI"},
            {"name": "BANK NIFTY", "symbol": "BANKNIFTY", "y": "^NSEBANK"},
            {"name": "SENSEX", "symbol": "SENSEX", "y": "^BSESN"},
            {"name": "NIFTY IT", "symbol": "NIFTY IT", "y": "^CNXIT"},
            {"name": "NIFTY AUTO", "symbol": "NIFTY AUTO", "y": "^CNXAUTO"},
            {"name": "NIFTY METAL", "symbol": "NIFTY METAL", "y": "^CNXMETAL"},
            {"name": "NIFTY PHARMA", "symbol": "NIFTY PHARMA", "y": "^CNXPHARMA"},
            {"name": "CRUDEOIL", "symbol": "CRUDEOIL", "y": "CL=F"},
            {"name": "GOLD", "symbol": "GOLD", "y": "GC=F"},
            {"name": "SILVER", "symbol": "SILVER", "y": "SI=F"},
            {"name": "NATURALGAS", "symbol": "NATURALGAS", "y": "NG=F"}
        ]

        current_time = datetime.now().time()
        # ✅ FIX: Weekend Logic Added taaki Saturday/Sunday ko faltu API calls na hon
        is_weekend = datetime.now().weekday() > 4
        mcx_symbols = ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"]

        old_prices = {item["name"]: item["price"] for item in market_status_cache["data"]} if market_status_cache["data"] else {}

        for idx in indices:
            price = old_prices.get(idx["name"], 0)
            is_mcx = idx["symbol"] in mcx_symbols

            if is_weekend and not is_mcx: 
                market_open = False
            else:
                if is_mcx:
                    market_open = dt_time(9, 0) <= current_time <= dt_time(23, 30)
                else:
                    market_open = dt_time(9, 15) <= current_time <= dt_time(15, 30)

            if market_open or price == 0:
                temp_price = 0
                try:
                    if session_manager:
                        temp_price = session_manager.get_ltp(idx["symbol"])
                except: pass

                # ✅ FIX: yfinance timeout lagaya hai taaki server hang na ho
                if not temp_price or temp_price == 0:
                    try:
                        ticker = yf.Ticker(idx["y"])
                        temp_price = ticker.fast_info.last_price
                    except Exception: 
                        pass

                if temp_price and temp_price > 0:
                    price = temp_price

            if price and price > 0: 
                if market_open:
                    trend = "LIVE"
                    color = "#00ff88"
                else:
                    trend = "CLOSED"  
                    color = "#ff4d4d"
            else: 
                trend = "OFFLINE"
                color = "#ff4d4d"
                price = 0

            status.append({"name": idx["name"], "price": round(price, 2), "trend": trend, "color": color})

        market_status_cache = {
            "data": status,
            "last_updated": time.time()
        }

    finally:
        # ✅ Lock ko release karna zaroori hai
        is_updating_status = False


# --- ROUTES ---

@app.get("/api")
def read_root():
    return {"message": "TradeMaster Pro API is Running! 🚀"}

@app.get("/active_trades")
def get_auto_trades():
    file_path = "current_trades.json"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except: return []
    return []

@app.get("/market_status")
async def get_status(background_tasks: BackgroundTasks):
    if time.time() - market_status_cache['last_updated'] > 5:
        background_tasks.add_task(update_market_status_bg)
    if not market_status_cache["data"]:
        # Agar cache bilkul khali hai toh ek baar run kar lo
        update_market_status_bg()
    return market_status_cache["data"]

@app.get("/option_chain")
async def get_options():
    loop = asyncio.get_event_loop()
    try:
        import option_data
        symbols_to_track = symbols.INDICES + symbols.COMMODITIES

        tasks = [loop.run_in_executor(executor, option_data.analyze_option_chain, sym) for sym in symbols_to_track]
        results = await asyncio.gather(*tasks)

        # ✅ API LEVEL SCORE CAPPING (Indices & Commodities)
        final_data = {}
        for sym, res in zip(symbols_to_track, results):
            if res and 'pcr' in res and str(res['pcr']).replace('%', '').replace('.', '').isdigit():
                raw_val = float(str(res['pcr']).replace('%', ''))
                res['pcr'] = f"{int(min(abs(raw_val), 100))}%"
            final_data[sym] = res

        return final_data
    except Exception as e:
        return {}

# ✅ FRONTEND REMINDER: Yahan par frontend se API call aate waqt '/scan/5m' aana chahiye
@app.get("/scan/{interval}")
async def scan(interval: str):
    loop = asyncio.get_event_loop()
    try:
        import scanner
        results = await loop.run_in_executor(executor, scanner.scan_market, interval)

        # ✅ API LEVEL SCORE CAPPING (Scanner Table)
        if isinstance(results, list):
            for res in results:
                if 'Score' in res:
                    res['Score'] = int(min(abs(res['Score']), 100))
                if 'Accuracy' in res:
                    res['Accuracy'] = float(min(abs(res['Accuracy']), 100.0))

        return results
    except Exception as e:
        return {"error": str(e)}

@app.get("/ask_ai/{symbol}")
async def ask_ai(symbol: str):
    if brain is None or not brain.is_ready:
        return {"error": "AI Model is still warming up in background. Please wait 1 minute.", "trend": "WAIT", "prob": 0}

    clean_sym = symbol.upper().replace(".NS", "").replace("-EQ", "")
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(executor, brain.predict_signal, clean_sym)

    # ✅ API LEVEL SCORE CAPPING (Direct AI Queries)
    if isinstance(res, dict) and 'prob' in res:
        res['prob'] = float(min(abs(res['prob']), 100.0))

    return res

@app.get("/all_symbols")
def get_all_symbols():
    return symbols.ALL_STOCKS

@app.post("/train_brain")
async def train_brain_endpoint(background_tasks: BackgroundTasks):
    if brain is None:
        return {"message": "AI is warming up. Please wait."}
    background_tasks.add_task(brain.train_brain)
    return {"message": "🧠 Training started in background."}


def load_heavy_libraries_in_bg():
    global brain
    print("🧠 Loading TensorFlow & AI Model in background (Takes 60s+)...")
    try:
        from ai_brain import TradeBrain
        brain = TradeBrain()
        print("✅ AI Model Loaded Successfully and Ready for Trading!")
    except Exception as e:
        print("❌ AI Load Error:", e)

@app.on_event("startup")
async def startup_event():
    print("🚀 API Started instantly! Port is Open.")
    threading.Thread(target=load_heavy_libraries_in_bg, daemon=True).start()
