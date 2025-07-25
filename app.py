# app.py (চূড়ান্ত এবং সম্পূর্ণ সঠিক সংস্করণ - সিনট্যাক্স এরর সমাধানসহ)

import websocket
import json
import datetime
import threading
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock 
import requests
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app)
sock = Sock(app)
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

clients = []

# --- পার্ট ১: Quotex WebSocket থেকে ডেটা গ্রহণ ---
def on_quotex_message(ws, message):
    try:
        data = json.loads(message)
        if isinstance(data, list) and data[0] == "quotes":
            asset = data[1]["symbol"]
            price = data[1]["value"]
            for client in clients:
                try: client.send(json.dumps({"asset": asset, "price": price}))
                except Exception: clients.remove(client)
    except Exception as e:
        print(f"Error parsing Quotex message: {e}")

def on_quotex_open(ws):
    print("✅ Connected to Quotex WebSocket")
    otc_assets = ["EURUSD-OTC", "GBPUSD-OTC", "AUDCAD-OTC"]
    for asset in otc_assets: ws.send(json.dumps(["subscribe", {"quotes": asset}]))

def run_quotex_ws():
    ws_url = "wss://quote-ws.quotex.io"
    ws = websocket.WebSocketApp(ws_url, on_open=on_quotex_open, on_message=on_quotex_message, on_error=lambda ws,e: print(e), on_close=lambda ws,cs,cm: print("closed"))
    while True:
        try:
            ws.run_forever()
            time.sleep(5)
        except Exception as e:
            print(f"Quotex WS connection error: {e}")

threading.Thread(target=run_quotex_ws, daemon=True).start()

# --- পার্ট ২: আমাদের নিজস্ব WebSocket সার্ভার ---
@sock.route('/live-price')
def live_price_socket(ws):
    clients.append(ws)
    try:
        while True: ws.receive(timeout=60) # ক্লায়েন্টকে কানেক্টেড রাখার জন্য
    except Exception: pass
    finally:
        if ws in clients: clients.remove(ws)

# --- পার্ট ৩: FMP API দিয়ে সিগন্যাল জেনারেশন ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট মার্কেট ডেটা পাওয়া যায়নি।"
        all_candles = list(reversed(candles_data))
        
        rsi_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}", timeout=10).json()
        sma_short_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=20&type=sma&apikey={FMP_API_KEY}", timeout=10).json()
        sma_long_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}", timeout=10).json()
        support, resistance = find_support_resistance(all_candles)
        
        return {
            "all_candles": all_candles, "latest_price": all_candles[-1]['close'], "support": support,
            "resistance": resistance, "latest_rsi": rsi_data[0].get('rsi') if rsi_data else None,
            "short_ma": sma_short_data[0].get('sma') if sma_short_data else None,
            "latest_sma": sma_long_data[0].get('sma') if sma_long_data else None,
        }, None
    except Exception as e:
        return None, f"ডেটা আনার সময় সমস্যা হয়েছে: {e}"

def find_support_resistance(candles):
    recent = candles[-50:]
    return min(c['low'] for c in recent), max(c['high'] for c in recent)

def is_strong_candle_signal(p, c):
    if c.get('open') < p.get('close') and c.get('close') > p.get('open'): return "BULLISH"
    if c.get('open') > p.get('close') and c.get('close') < p.get('open'): return "BEARISH"
    return "NEUTRAL"

def analyze_live_market(market_data, trend_filter, signal_filter):
    all_candles = market_data['all_candles']
    if len(all_candles) < 2: return {"signal": "NONE", "reason": "Not enough data"}

    price = Decimal(str(market_data['latest_price'])); sma_slow = Decimal(str(market_data['latest_sma']))
    main_trend = "UP" if price > sma_slow else "DOWN"

    if trend_filter != 'ANY' and main_trend != trend_filter:
        return {"signal": "NONE", "reason": f"বর্তমান ট্রেন্ড ({main_trend}) আপনার '{trend_filter}' ফিল্টারের সাথে মেলেনি।"}

    rsi, support, resistance = market_data.get('latest_rsi'), market_data.get('support'), market_data.get('resistance')
    candle_signal = is_strong_candle_signal(all_candles[-2], all_candles[-1])

    call_conditions = [(main_trend == "UP", "ট্রেন্ড UP"), (rsi < 45, "RSI কম"), (abs(price-Decimal(str(support)))<(price*Decimal('0.002')), "সাপোর্টের কাছে"), (candle_signal=="BULLISH", "বুলিশ ক্যান্ডেল")]
    put_conditions = [(main_trend == "DOWN", "ট্রেন্ড DOWN"), (rsi > 55, "RSI বেশি"), (abs(price-Decimal(str(resistance)))<(price*Decimal('0.002')), "রেসিস্ট্যান্সের কাছে"), (candle_signal=="BEARISH", "বেয়ারিশ ক্যান্ডেল")]
    
    call_met, put_met = sum(c[0] for c in call_conditions), sum(c[0] for c in put_conditions)

    if call_met >= 3 and signal_filter in ["ALL", "CALL"]: return {"signal": "CALL", "is_future": False, "reason": "লাইভ সিগন্যাল: একাধিক শর্ত মিলেছে।"}
    if put_met >= 3 and signal_filter in ["ALL", "PUT"]: return {"signal": "PUT", "is_future": False, "reason": "লাইভ সিগন্যাল: একাধিক শর্ত মিলেছে।"}
    if call_met == 2 and signal_filter in ["ALL", "CALL"]:
        reasons = [r for met, r in call_conditions if met]; return {"signal": "POTENTIAL CALL", "is_future": True, "reason": " এবং ".join(reasons) + "। কনফার্মেশনের জন্য অপেক্ষা করুন।"}
    if put_met == 2 and signal_filter in ["ALL", "PUT"]:
        reasons = [r for met, r in put_conditions if met]; return {"signal": "POTENTIAL PUT", "is_future": True, "reason": " এবং ".join(reasons) + "। কনফার্মেশনের জন্য অপেক্ষা করুন।"}
        
    return {"signal": "NONE", "reason": "এই মুহূর্তে কোনো ভালো সুযোগ তৈরি হচ্ছে না।"}

@app.route('/get-signal', methods=['POST'])
def get_signal_endpoint():
    options = request.get_json()
    asset, timeframe, trend_filter, signal_filter = options.get('asset'), options.get('timeframe'), options.get('trend_filter'), options.get('signal_filter')
    if not asset: return jsonify({"error": "Asset is required."}), 400
    
    market_data, error_msg = get_market_data(asset, timeframe)
    if error_msg: return jsonify({"error": error_msg, "market_data": None, "analysis": None}), 400

    analysis = analyze_live_market(market_data, trend_filter, signal_filter)
    return jsonify({ "analysis": analysis, "market_data": market_data })

@app.route('/get-market-update', methods=['POST'])
def get_market_update_endpoint():
    options = request.get_json()
    market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
    if error_msg: return jsonify({"error": error_msg}), 400
    return jsonify(market_data)

@app.route('/')
def index():
    return "Hybrid AI Trading Bot Backend is Running Correctly!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
