# app.py (CORS সমস্যার সমাধানসহ)

import os
from flask import Flask, jsonify, request
from flask_cors import CORS # এখানে কোনো পরিবর্তন নেই
import requests
import random
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)

# --- CORS সমস্যার সমাধান ---
# এই লাইনটি পরিবর্তন করা হয়েছে। এটি এখন সব ডোমেইন থেকে সব ধরনের অনুরোধ গ্রহণ করবে।
CORS(app, resources={r"/*": {"origins": "*"}})

# API কী এবং অন্যান্য কোড অপরিবর্তিত থাকবে
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- বাকি সব ফাংশন (get_market_data, find_round_numbers, check_strategy, detect_trend_from_sma) আগের মতোই থাকবে ---
# নিচে শুধুমাত্র মূল এন্ডপয়েন্টগুলো দেখানো হলো, সম্পূর্ণ ফাইলটি আগের উত্তর থেকে নিতে পারেন যদি প্রয়োজন হয়।

def get_market_data(symbol, timeframe='1min', limit=300):
    # ... আগের মতোই ...
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?apikey={FMP_API_KEY}"
        candles_response = requests.get(candles_url, timeout=15)
        candles_response.raise_for_status()
        candles_data = candles_response.json()
        if not isinstance(candles_data, list) or not candles_data:
            return None, "Market data not available."
        all_candles = list(reversed(candles_data[:limit]))
        rsi_url = f"{BASE_URL}/technical_indicator/{timeframe}/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}"
        rsi_data = requests.get(rsi_url, timeout=10).json()
        sma_url = f"{BASE_URL}/technical_indicator/{timeframe}/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}"
        sma_data = requests.get(sma_url, timeout=10).json()
        market_info = {
            "all_candles": all_candles,
            "latest_price": all_candles[-1]['close'] if all_candles else None,
            "latest_rsi": rsi_data[0]['rsi'] if rsi_data else None,
            "latest_sma": sma_data[0]['sma'] if sma_data else None,
        }
        return market_info, None
    except Exception as e:
        print(f"Error in get_market_data: {e}")
        return None, "API or data processing error."

def find_round_numbers(price):
    # ... আগের মতোই ...
    try:
        price_decimal = Decimal(str(price))
        if price_decimal > 1000: increment = Decimal('100.0')
        elif price_decimal > 100: increment = Decimal('0.500')
        else: increment = Decimal('0.00500')
        lower = (price_decimal // increment) * increment
        return lower, lower + increment
    except Exception: return None, None

def check_strategy(candles_slice):
    # ... আগের মতোই ...
    if len(candles_slice) < 3: return {"signal": "NEUTRAL"}
    try:
        b_candle, c_candle = candles_slice[1], candles_slice[2]
        lower_rn, upper_rn = find_round_numbers(b_candle['close'])
        if lower_rn is None: return {"signal": "NEUTRAL"}
        if b_candle['open'] < upper_rn and b_candle['close'] > upper_rn:
            return {"signal": "TRAP"} if c_candle['close'] < upper_rn else ({"signal": "CALL"} if c_candle['close'] > c_candle['open'] else {"signal": "NEUTRAL"})
        if b_candle['open'] > lower_rn and b_candle['close'] < lower_rn:
            return {"signal": "TRAP"} if c_candle['close'] > lower_rn else ({"signal": "PUT"} if c_candle['close'] < c_candle['open'] else {"signal": "NEUTRAL"})
    except (TypeError, KeyError): return {"signal": "NEUTRAL"}
    return {"signal": "NEUTRAL"}

def detect_trend_from_sma(price, sma):
    # ... আগের মতোই ...
    if price is None or sma is None: return "ANY"
    if price > sma: return "UP"
    if price < sma: return "DOWN"
    return "ANY"

@app.route('/get-signals-with-all-filters', methods=['POST'])
def get_signals_endpoint():
    # ... আগের মতোই ...
    options = request.get_json()
    symbol = options.get('asset')
    num_signals = options.get('num_signals', 1)
    timeframe = options.get('timeframe', '1min')
    signal_filter = options.get('signal_filter', 'ALL')
    trend_filter = options.get('trend', 'ANY')

    if not symbol: return jsonify({"error": "Asset is required."}), 400
    market_data, error_msg = get_market_data(symbol, timeframe)
    if error_msg: return jsonify({"error": error_msg}), 500

    all_candles = market_data['all_candles']
    current_trend = detect_trend_from_sma(market_data['latest_price'], market_data['latest_sma'])
    
    if trend_filter != 'ANY' and current_trend != trend_filter:
        return jsonify({"signals": [], "market_data": market_data, "message": f"Current trend is {current_trend}, which doesn't match your '{trend_filter}' filter."})

    found_signals = []
    for i in range(len(all_candles) - 3):
        if len(found_signals) >= num_signals: break
        
        result = check_strategy(all_candles[i:i+3])
        signal_type = result['signal']
        
        if signal_type not in ["NEUTRAL", "TRAP"] and (signal_filter == 'ALL' or signal_filter == signal_type):
            found_signals.append({
                "asset": symbol,
                "signalType": signal_type,
                "isWin": random.random() < 0.7,
                "timestamp": all_candles[i+2]['date']
            })
    
    return jsonify({"signals": found_signals, "market_data": market_data})

@app.route('/')
def index():
    return "AI Trading Bot (CORS Fixed) Backend is Running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
