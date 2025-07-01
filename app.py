# app.py (চূড়ান্ত সংস্করণ - নেক্সট ক্যান্ডেল প্রেডিকশন)

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

# --- ডেটা আনার এবং হেল্পার ফাংশন ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        # সব API এন্ডপয়েন্ট
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

# --- চূড়ান্ত এবং শক্তিশালী প্রেডিকশন স্ট্র্যাটেজি ---
def get_next_candle_prediction(market_data):
    all_candles, price_str = market_data['all_candles'], market_data['latest_price']
    rsi, short_ma, long_ma = market_data['latest_rsi'], market_data['short_ma'], market_data['latest_sma']
    support, resistance = market_data['support'], market_data['resistance']
    
    if any(v is None for v in [price_str, rsi, short_ma, long_ma, support, resistance]):
        return {"decision": "WAIT", "reason": "ইন্ডিকেটর ডেটা অসম্পূর্ণ।"}

    price, short_ma, long_ma = Decimal(str(price_str)), Decimal(str(short_ma)), Decimal(str(long_ma))
    support, resistance = Decimal(str(support)), Decimal(str(resistance))

    # পয়েন্ট সিস্টেম: প্রতিটি শর্তের জন্য পয়েন্ট যোগ বা বিয়োগ করা হবে
    up_points = 0
    down_points = 0

    # ১. মূল ট্রেন্ড (EMA Crossover)
    if short_ma > long_ma: up_points += 2 # Golden Cross
    else: down_points += 2 # Death Cross

    # ২. RSI মোমেন্টাম
    if rsi < 35: up_points += 2 # Oversold
    elif rsi > 65: down_points += 2 # Overbought
    elif rsi < 50: down_points += 1
    else: up_points += 1

    # ৩. সাপোর্ট ও রেসিস্ট্যান্স
    price_range = resistance - support
    if price_range == 0: price_range = Decimal('0.001') # ০ দিয়ে ভাগ এড়ানোর জন্য
    
    # প্রাইস সাপোর্টের কতটা কাছে?
    dist_from_support = (price - support) / price_range
    if dist_from_support < 0.2: up_points += 2 # সাপোর্টের খুব কাছে
    
    # প্রাইস রেসিস্ট্যান্সের কতটা কাছে?
    dist_from_resistance = (resistance - price) / price_range
    if dist_from_resistance < 0.2: down_points += 2 # রেসিস্ট্যান্সের খুব কাছে

    # ৪. ক্যান্ডেলস্টিক প্যাটার্ন (শেষ দুটি ক্যান্ডেল)
    p_candle, c_candle = all_candles[-2:]
    if c_candle['open'] < p_candle['close'] and c_candle['close'] > p_candle['open']: up_points += 1.5 # Bullish Engulfing
    if c_candle['open'] > p_candle['close'] and c_candle['close'] < p_candle['open']: down_points += 1.5 # Bearish Engulfing

    # চূড়ান্ত সিদ্ধান্ত
    if up_points > down_points + 2:
        return {"decision": "UP", "reason": f"শক্তিশালী আপট্রেন্ড সিগন্যাল (Score: {up_points:.1f} vs {down_points:.1f})"}
    if down_points > up_points + 2:
        return {"decision": "DOWN", "reason": f"শক্তিশালী ডাউনট্রেন্ড সিগন্যাল (Score: {down_points:.1f} vs {up_points:.1f})"}
    
    return {"decision": "WAIT", "reason": "মার্কেট অনিশ্চিত। কোনো স্পষ্ট সিগন্যাল নেই।"}

# --- মূল API এন্ডপয়েন্ট ---
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
    return "AI Trading Bot Final Prediction Backend - Operational!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
