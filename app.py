# app.py (চূড়ান্ত সমাধান - কার্যকরী প্রেডিকশন লজিকসহ)

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from decimal import Decimal, getcontext

# --- কনফিগারেশন অপরিবর্তিত ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- ডেটা আনার এবং হেল্পার ফাংশন (আগের মতোই) ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50: return None, f"'{symbol}' এর জন্য যথেষ্ট ডেটা নেই।"
        
        all_candles = list(reversed(candles_data))
        rsi_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}", timeout=10).json()
        sma_short_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=9&type=ema&apikey={FMP_API_KEY}", timeout=10).json()
        sma_long_data = requests.get(f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=21&type=ema&apikey={FMP_API_KEY}", timeout=10).json()
        support, resistance = find_support_resistance(all_candles)
        
        return {
            "all_candles": all_candles, "latest_price": all_candles[-1]['close'], "support": support,
            "resistance": resistance, "latest_rsi": rsi_data[0].get('rsi'),
            "short_ma": sma_short_data[0].get('ema'), "latest_sma": sma_long_data[0].get('ema'),
        }, None
    except Exception as e: return None, f"API থেকে ডেটা আনতে সমস্যা: {e}"

def find_support_resistance(candles): recent = candles[-50:]; return min(c['low'] for c in recent), max(c['high'] for c in recent)

# --- নতুন এবং কার্যকরী প্রেডিকশন স্ট্র্যাটেজি ---
def get_next_candle_prediction(market_data):
    # ডেটা ভ্যালিডেশন
    required_keys = ['latest_price', 'latest_rsi', 'short_ma', 'latest_sma']
    if any(market_data.get(key) is None for key in required_keys):
        return {"decision": "WAIT", "reason": "ইন্ডিকেটর ডেটা লোড হচ্ছে..."}

    # ডেটা প্রস্তুত করা
    price = Decimal(str(market_data['latest_price']))
    short_ma = Decimal(str(market_data['short_ma']))
    long_ma = Decimal(str(market_data['latest_sma']))
    rsi = market_data['latest_rsi']

    # ১. মূল ট্রেন্ড নির্ধারণ (EMA ক্রসওভার এবং প্রাইসের অবস্থান)
    trend = "NEUTRAL"
    if short_ma > long_ma and price > long_ma:
        trend = "UP"
    elif short_ma < long_ma and price < long_ma:
        trend = "DOWN"

    # ২. মোমেন্টাম এবং এক্সট্রিম কন্ডিশন (RSI)
    is_oversold = rsi < 35
    is_overbought = rsi > 65

    # ৩. সিদ্ধান্ত নেওয়ার লজিক
    
    # শক্তিশালী CALL সিগন্যাল: আপট্রেন্ড + Oversold (দাম কমার পর ট্রেন্ডের দিকে আবার উঠবে)
    if trend == "UP" and is_oversold:
        return {"decision": "UP", "reason": " শক্তিশালী আপট্রেন্ডে প্রাইস এখন সাপোর্টের কাছে (Oversold)।"}

    # শক্তিশালী PUT সিগন্যাল: ডাউনট্রেন্ড + Overbought (দাম বাড়ার পর ট্রেন্ডের দিকে আবার নামবে)
    if trend == "DOWN" and is_overbought:
        return {"decision": "DOWN", "reason": " শক্তিশালী ডাউনট্রেন্ডে প্রাইস এখন রেসিস্ট্যান্সের কাছে (Overbought)।"}

    # ট্রেন্ডের দিকে সাধারণ সিগন্যাল
    if trend == "UP":
        return {"decision": "UP", "reason": "মার্কেট বর্তমানে আপট্রেন্ডে আছে।"}
    
    if trend == "DOWN":
        return {"decision": "DOWN", "reason": "মার্কেট বর্তমানে ডাউনট্রেন্ডে আছে।"}

    # যদি কোনো স্পষ্ট ট্রেন্ড না থাকে
    return {"decision": "WAIT", "reason": "মার্কেট সাইডওয়েজ অথবা অনিশ্চিত। স্পষ্ট ট্রেন্ডের জন্য অপেক্ষা করুন।"}


# --- মূল API এন্ডপয়েন্ট (অপরিবর্তিত) ---
@app.route('/get-prediction', methods=['POST'])
def get_prediction_endpoint():
    options = request.get_json()
    asset, timeframe = options.get('asset'), options.get('timeframe')
    if not asset: return jsonify({"error": "Asset is required."}), 400
    
    market_data, error_msg = get_market_data(asset, timeframe)
    if error_msg: return jsonify({"error": error_msg, "market_data": None}), 500

    prediction = get_next_candle_prediction(market_data)
    
    return jsonify({"prediction": prediction, "market_data": market_data})

@app.route('/get-market-update', methods=['POST'])
def get_market_update_endpoint():
    options = request.get_json()
    market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
    if error_msg: return jsonify({"error": error_msg}), 500
    return jsonify(market_data)

@app.route('/')
def index():
    return "AI Trading Bot Final Prediction Backend (Logic Fixed) - Operational!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
