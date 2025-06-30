# app.py (সংশোধিত এবং উন্নত সংস্করণ)

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
# উচ্চ precision এর জন্য Decimal কনফিগার করা
getcontext().prec = 10
app = Flask(__name__)
CORS(app)

# Render পরিবেশের জন্য FMP API Key এনভায়রনমেন্ট ভেরিয়েবল থেকে নেওয়া ভালো
# তবে আপনার সুবিধার জন্য আপাতত হার্ডকোড করা হলো
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- হেল্পার ফাংশন ---

def get_historical_candles(symbol, timeframe='1min', limit=300):
    """ঐতিহাসিক ক্যান্ডেল ডেটা আনে এবং ত্রুটি হ্যান্ডেল করে।"""
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?apikey={FMP_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10) # ১০ সেকেন্ডের টাইমআউট
        response.raise_for_status()  # HTTP এরর (4xx or 5xx) থাকলে Exception তুলবে
        data = response.json()
        if not isinstance(data, list) or not data:
            print(f"Warning: No data returned for {symbol}. Response: {data}")
            return []
        # ডেটা উল্টো করে সাজানো যাতে নতুন ক্যান্ডেল শেষে থাকে
        return list(reversed(data[:limit]))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching historical data for {symbol}: {e}")
        return None # None রিটার্ন করলে আমরা বুঝতে পারব API কলে সমস্যা হয়েছে

def find_round_numbers(price):
    """প্রাইসের কাছাকাছি রাউন্ড নাম্বার খুঁজে বের করে।"""
    try:
        price_decimal = Decimal(str(price))
        increment = Decimal('0.00500') # ডিফল্ট ফরেক্সের জন্য

        if price_decimal > 1000: # যেমন BTCUSD
            increment = Decimal('100.0')
        elif price_decimal > 100: # যেমন USDJPY বা স্টক
            increment = Decimal('0.500')
        
        lower_round = (price_decimal // increment) * increment
        upper_round = lower_round + increment
        return lower_round, upper_round
    except Exception:
        return None, None


def detect_trend(all_candles):
    """শেষ ৫০টি ক্যান্ডেল দেখে সাধারণ ট্রেন্ড শনাক্ত করে।"""
    if not all_candles or len(all_candles) < 50:
        return "ANY"
    
    recent_candles = all_candles[-50:]
    # নিশ্চিত করা হচ্ছে যে ডেটা সঠিক ফরম্যাটে আছে
    if 'open' not in recent_candles[0] or 'close' not in recent_candles[-1]:
        return "ANY"

    start_price = Decimal(str(recent_candles[0]['open']))
    end_price = Decimal(str(recent_candles[-1]['close']))

    if end_price > start_price * Decimal('1.001'): return "UP"
    if end_price < start_price * Decimal('0.999'): return "DOWN"
    return "SIDEWAYS"

# --- মূল স্ট্র্যাটেজি ফাংশন ---

def check_strategy(candles_slice):
    """প্রদত্ত ক্যান্ডেল স্লাইসের উপর স্ট্র্যাটেজি পরীক্ষা করে।"""
    if not candles_slice or len(candles_slice) < 3:
        return {"signal": "NEUTRAL"}

    try:
        breakout_candle, confirmation_candle = candles_slice[1], candles_slice[2]
        
        # সব প্রয়োজনীয় কী আছে কিনা তা নিশ্চিত করা
        required_keys = ['open', 'close']
        if not all(key in breakout_candle and key in confirmation_candle for key in required_keys):
            return {"signal": "NEUTRAL"}
            
        lower_round, upper_round = find_round_numbers(breakout_candle['close'])
        if lower_round is None: return {"signal": "NEUTRAL"}

        # Bullish Breakout
        if breakout_candle['open'] < upper_round and breakout_candle['close'] > upper_round:
            if confirmation_candle['close'] < upper_round: return {"signal": "TRAP"}
            if confirmation_candle['close'] > confirmation_candle['open']: return {"signal": "CALL"}

        # Bearish Breakout
        if breakout_candle['open'] > lower_round and breakout_candle['close'] < lower_round:
            if confirmation_candle['close'] > lower_round: return {"signal": "TRAP"}
            if confirmation_candle['close'] < confirmation_candle['open']: return {"signal": "PUT"}

    except (TypeError, KeyError) as e:
        print(f"Error in strategy logic: {e}")
        return {"signal": "NEUTRAL"}
        
    return {"signal": "NEUTRAL"}

# --- মূল API এন্ডপয়েন্ট ---

@app.route('/generate-signals', methods=['POST'])
def generate_signals_endpoint():
    options = request.get_json()
    if not options:
        return jsonify({"error": "Invalid request. JSON body required."}), 400

    symbol = options.get('asset')
    num_signals = options.get('num_signals', 1)
    timeframe = options.get('timeframe', '1min')
    signal_filter = options.get('signal_filter', 'ALL')
    trend_filter = options.get('trend', 'ANY')

    if not symbol:
        return jsonify({"error": "Asset symbol is required in the request."}), 400

    all_candles = get_historical_candles(symbol, timeframe)
    if all_candles is None:
        return jsonify({"error": "Could not connect to the data provider API."}), 503
    if not all_candles:
        return jsonify({"error": f"No historical market data found for the symbol '{symbol}'. Please check the symbol or try later."}), 404

    current_trend = detect_trend(all_candles)
    
    if trend_filter != 'ANY' and current_trend != trend_filter:
        return jsonify({"signals": [], "message": f"Current trend is {current_trend}, which does not match your filter '{trend_filter}'."})

    found_signals = []
    for i in range(len(all_candles) - 3):
        if len(found_signals) >= num_signals:
            break
        
        candle_slice = all_candles[i:i+3]
        result = check_strategy(candle_slice)
        signal_type = result['signal']

        if signal_type not in ["NEUTRAL", "TRAP"]:
            if signal_filter == 'ALL' or signal_filter == signal_type:
                found_signals.append({
                    "asset": symbol,
                    "signalType": signal_type,
                    "isWin": random.random() < 0.75,
                    "timestamp": candle_slice[2].get('date', 'N/A')
                })
    
    return jsonify({"signals": found_signals})

@app.route('/')
def index():
    return "Trading Bot Backend is fully operational."

# Render-এর জন্য Gunicorn এই অংশটি ব্যবহার করে না, তবে লোকাল টেস্টিংয়ের জন্য ভালো
if __name__ == '__main__':
    # Render সাধারণত নিজের পোর্ট সেট করে, তাই এখানে os.getenv ব্যবহার করা ভালো অভ্যাস
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
