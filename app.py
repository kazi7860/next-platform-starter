# app.py (চূড়ান্ত হাইব্রিড সংস্করণ: Quotex WebSocket + FMP API)

import websocket
import json
import datetime
import threading
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock # WebSocket সার্ভারের জন্য নতুন লাইব্রেরি
import requests
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app)
sock = Sock(app) # Flask অ্যাপের সাথে WebSocket যুক্ত করা
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- গ্লোবাল ভেরিয়েবল: লাইভ প্রাইস সংরক্ষণের জন্য ---
live_otc_prices = {}
clients = [] # সংযুক্ত সব ফ্রন্টএন্ড ক্লায়েন্টদের তালিকা

# --- পার্ট ১: Quotex WebSocket থেকে ডেটা গ্রহণ ---

def on_quotex_message(ws, message):
    global live_otc_prices
    try:
        data = json.loads(message)
        if isinstance(data, list) and data[0] == "quotes":
            asset = data[1]["symbol"]
            price = data[1]["value"]
            live_otc_prices[asset] = price
            # নতুন প্রাইস পেলে সব সংযুক্ত ক্লায়েন্টকে পাঠানো হবে
            for client in clients:
                try:
                    client.send(json.dumps({"asset": asset, "price": price}))
                except Exception:
                    clients.remove(client)
    except Exception as e:
        print(f"Error parsing Quotex message: {e}")

def on_quotex_error(ws, error): print(f"Quotex WebSocket error: {error}")
def on_quotex_close(ws, close_status_code, close_msg): print("Quotex WebSocket closed. Reconnecting...")
def on_quotex_open(ws):
    print("✅ Connected to Quotex WebSocket")
    otc_assets = ["EURUSD-OTC", "GBPUSD-OTC", "AUDCAD-OTC", "EURJPY-OTC"] # উদাহরণ
    for asset in otc_assets:
        ws.send(json.dumps(["subscribe", {"quotes": asset}]))

def run_quotex_ws():
    ws_url = "wss://quote-ws.quotex.io"
    ws = websocket.WebSocketApp(ws_url, on_open=on_quotex_open, on_message=on_quotex_message, on_error=on_quotex_error, on_close=on_quotex_close)
    while True:
        ws.run_forever()
        time.sleep(5) # সংযোগ বিচ্ছিন্ন হলে ৫ সেকেন্ড পর আবার চেষ্টা করবে

# একটি আলাদা থ্রেডে Quotex WebSocket চালানো হচ্ছে যাতে মূল অ্যাপ ব্লক না হয়
quotex_thread = threading.Thread(target=run_quotex_ws)
quotex_thread.daemon = True
quotex_thread.start()

# --- পার্ট ২: আমাদের নিজস্ব WebSocket সার্ভার (ফ্রন্টএন্ডের জন্য) ---

@sock.route('/live-price')
def live_price_socket(ws):
    global clients
    clients.append(ws)
    print(f"New client connected. Total clients: {len(clients)}")
    try:
        while True:
            # ক্লায়েন্টকে কানেক্টেড রাখার জন্য এখানে বার্তা গ্রহণ করা যায়
            message = ws.receive()
    except Exception as e:
        print(f"Client disconnected: {e}")
    finally:
        clients.remove(ws)
        print(f"Client removed. Total clients: {len(clients)}")


# --- পার্ট ৩: FMP API দিয়ে সিগন্যাল জেনারেশন (আগের মতোই) ---

# (get_market_data, find_support_resistance, analyze_live_market ইত্যাদি ফাংশন অপরিবর্তিত)
# ... আগের চূড়ান্ত উত্তর থেকে এই ফাংশনগুলো কপি করে নিন ...

@app.route('/get-signal', methods=['POST'])
def get_signal_endpoint():
    # ... এই এন্ডপয়েন্টটি আগের চূড়ান্ত উত্তর থেকে কপি করুন, কোনো পরিবর্তন নেই ...
    pass
    
@app.route('/')
def index():
    return "Hybrid AI Trading Bot Backend is Running!"

# --- helper functions from previous answers for completeness ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50: return None, f"'{symbol}' এর জন্য যথেষ্ট ডেটা নেই।"
        all_candles = list(reversed(candles_data))
        rsi_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}", timeout=10).json()
        sma_short_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=20&type=sma&apikey={FMP_API_KEY}", timeout=10).json()
        sma_long_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}", timeout=10).json()
        support, resistance = find_support_resistance(all_candles)
        return {"all_candles": all_candles, "latest_price": all_candles[-1]['close'], "support": support, "resistance": resistance, "latest_rsi": rsi_data[0].get('rsi'), "short_ma": sma_short_data[0].get('sma'), "latest_sma": sma_long_data[0].get('sma'),}, None
    except Exception as e: return None, f"API থেকে ডেটা আনতে সমস্যা: {e}"
def find_support_resistance(candles): recent = candles[-50:]; return min(c['low'] for c in recent), max(c['high'] for c in recent)
def analyze_live_market(market_data, trend_filter, signal_filter):
    # This is a placeholder for your complex strategy
    return {"signal": "CALL", "is_future": False, "reason": "Analysis complete."}
if __name__ == '__main__':
    # This part is for local testing, Render will use its own server (like Gunicorn)
    app.run(host='0.0.0.0', port=5000)
