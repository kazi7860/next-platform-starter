# app.py (লাইভ সিগন্যাল দেওয়ার জন্য আপডেট করা)

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# --- কনফিগারেশন অপরিবর্তিত ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- ডেটা আনার এবং হেল্পার ফাংশন অপরিবর্তিত ---
def get_market_data(symbol, timeframe='1min', limit=100):
    # ... এই ফাংশনটি আগের মতোই থাকবে ...
    # (আগের উত্তর থেকে কপি করে নিন)
    pass

def find_support_resistance(candles):
    # ... এই ফাংশনটি আগের মতোই থাকবে ...
    pass

def is_bullish_engulfing(prev_candle, curr_candle):
    # ... এই ফাংশনটি আগের মতোই থাকবে ...
    pass

def is_bearish_engulfing(prev_candle, curr_candle):
    # ... এই ফাংশনটি আগের মতোই থাকবে ...
    pass

def check_confluence_strategy(market_data, candle_slice):
    # ... এই ফাংশনটি আগের মতোই থাকবে ...
    pass

# --- মূল API এন্ডপয়েন্ট (পরিবর্তিত) ---

@app.route('/get-signals-with-all-filters', methods=['POST'])
def get_live_signal_endpoint():
    options = request.get_json()
    symbol = options.get('asset')
    timeframe = options.get('timeframe', '1min')
    signal_filter = options.get('signal_filter', 'ALL')
    
    if not symbol: return jsonify({"error": "Asset is required."}), 400

    # ডেটা আনা হচ্ছে
    market_data, error_msg = get_market_data(symbol, timeframe)
    if error_msg: return jsonify({"error": error_msg}), 500

    all_candles = market_data['all_candles']
    
    # --- নতুন লজিক: শুধুমাত্র সর্বশেষ ক্যান্ডেলটি পরীক্ষা করা ---
    # আমরা শেষ দুটি ক্যান্ডেল নেব (একটি আগের, একটি বর্তমান)
    latest_candle_slice = all_candles[-2:]
    
    # স্ট্র্যাটেজি প্রয়োগ করে লাইভ সিগন্যাল খোঁজা
    signal_type = check_confluence_strategy(market_data, latest_candle_slice)
    
    found_signals = []

    # যদি একটি বৈধ সিগন্যাল পাওয়া যায় এবং তা ফিল্টারের সাথে মেলে
    if signal_type != "NEUTRAL":
        if signal_filter == 'ALL' or signal_filter == signal_type:
            found_signals.append({
                "asset": symbol,
                "signalType": signal_type,
                "isWin": random.random() < 0.8, # ডেমো win rate
                "timestamp": latest_candle_slice[1]['date']
            })
    
    return jsonify({
        "signals": found_signals, 
        "market_data": {
            'latest_price': market_data['latest_price'],
            'latest_rsi': market_data['latest_rsi'],
            'latest_sma': market_data['latest_sma_50']
        },
        "message": "Live signal analysis complete."
    })


@app.route('/')
def index():
    return "Live Signal AI Bot Backend is Running!"

# --- বাকি কোড এবং ফাংশনগুলো আগের উত্তর থেকে কপি করে এখানে বসিয়ে দিন ---
# (যেমন: __main__ অংশ এবং অন্যান্য হেল্পার ফাংশন)
# নিচে একটি উদাহরণ দেওয়া হলো
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট মার্কেট ডেটা পাওয়া যায়নি।"
        all_candles = list(reversed(candles_data))
        rsi_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}"
        rsi_data = requests.get(rsi_url, timeout=10).json()
        sma_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}"
        sma_data = requests.get(sma_url, timeout=10).json()
        market_info = {
            "all_candles": all_candles,
            "latest_price": all_candles[-1]['close'],
            "latest_rsi": rsi_data[0]['rsi'] if rsi_data else None,
            "latest_sma_50": sma_data[0]['sma'] if sma_data else None,
        }
        return market_info, None
    except requests.exceptions.RequestException as e:
        return None, "ডেটা প্রোভাইডারের সাথে সংযোগ স্থাপন করা যায়নি।"
    except Exception as e:
        return None, f"ডেটা প্রসেস করার সময় সমস্যা হয়েছে: {e}"

def check_confluence_strategy(market_data, candle_slice):
    if len(candle_slice) < 2: return "NEUTRAL"
    prev_candle, current_candle = candle_slice
    price = Decimal(str(current_candle['close']))
    rsi = market_data.get('latest_rsi')
    sma_50 = market_data.get('latest_sma_50')
    if rsi is None or sma_50 is None: return "NEUTRAL"
    sma_50 = Decimal(str(sma_50))
    main_trend = "UP" if price > sma_50 else "DOWN"
    support, resistance = find_support_resistance(market_data['all_candles'])
    call_conditions_met = (1 if main_trend == "UP" else 0) + (1 if rsi < 40 else 0) + (1 if abs(price - Decimal(str(support))) < (price * Decimal('0.001')) else 0) + (1 if is_bullish_engulfing(prev_candle, current_candle) else 0)
    put_conditions_met = (1 if main_trend == "DOWN" else 0) + (1 if rsi > 60 else 0) + (1 if abs(price - Decimal(str(resistance))) < (price * Decimal('0.001')) else 0) + (1 if is_bearish_engulfing(prev_candle, current_candle) else 0)
    if call_conditions_met >= 3: return "CALL"
    if put_conditions_met >= 3: return "PUT"
    return "NEUTRAL"

def find_support_resistance(candles):
    recent_candles = candles[-50:]
    return min(c['low'] for c in recent_candles), max(c['high'] for c in recent_candles)
def is_bullish_engulfing(prev_candle, curr_candle):
    return curr_candle['open'] < prev_candle['close'] and curr_candle['close'] > prev_candle['open']
def is_bearish_engulfing(prev_candle, curr_candle):
    return curr_candle['open'] > prev_candle['close'] and curr_candle['close'] < prev_candle['open']

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
