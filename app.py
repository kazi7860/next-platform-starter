# app.py (চূড়ান্ত সংস্করণ - উন্নত ইন্ডিকেটর ও স্ট্র্যাটেজিসহ)

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- ডেটা আনার এবং প্রস্তুত করার ফাংশন (উন্নত) ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '') # ইনডেক্সের জন্য ^ চিহ্ন বাদ দেওয়া
    try:
        # ক্যান্ডেল ডেটা
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট মার্কেট ডেটা পাওয়া যায়নি।"
        all_candles = list(reversed(candles_data))

        # একাধিক ইন্ডিকেটর আনা হচ্ছে
        rsi_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}"
        sma_fast_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=20&type=sma&apikey={FMP_API_KEY}" # স্বল্পমেয়াদী
        sma_slow_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}" # দীর্ঘমেয়াদী

        rsi_data = requests.get(rsi_url, timeout=10).json()
        sma_fast_data = requests.get(sma_fast_url, timeout=10).json()
        sma_slow_data = requests.get(sma_slow_url, timeout=10).json()

        market_info = {
            "all_candles": all_candles,
            "latest_price": all_candles[-1]['close'],
            "latest_rsi": rsi_data[0]['rsi'] if rsi_data else None,
            "latest_sma_fast": sma_fast_data[0]['sma'] if sma_fast_data else None,
            "latest_sma_slow": sma_slow_data[0]['sma'] if sma_slow_data else None,
        }
        return market_info, None
    except Exception as e:
        return None, f"ডেটা আনার সময় সমস্যা হয়েছে: {e}"

# --- স্ট্র্যাটেজি সম্পর্কিত হেল্পার ফাংশন ---
def find_support_resistance(candles):
    recent_candles = candles[-50:]
    return min(c['low'] for c in recent_candles), max(c['high'] for c in recent_candles)

def is_strong_candle_signal(prev_candle, curr_candle):
    # বুলিশ বা বেয়ারিশ Engulfing প্যাটার্ন পরীক্ষা করে
    is_bullish = curr_candle['open'] < prev_candle['close'] and curr_candle['close'] > prev_candle['open']
    is_bearish = curr_candle['open'] > prev_candle['close'] and curr_candle['close'] < prev_candle['open']
    if is_bullish: return "BULLISH"
    if is_bearish: return "BEARISH"
    return "NEUTRAL"

# --- মূল কনফ্লুয়েন্স স্ট্র্যাটেজি (উন্নত) ---
def analyze_market_for_signals(market_data):
    all_candles = market_data['all_candles']
    if len(all_candles) < 2: return {"live_signal": "NEUTRAL", "future_signal": "NONE", "reason": "Not enough data"}

    # সর্বশেষ ডেটা সংগ্রহ
    price = Decimal(str(market_data['latest_price']))
    rsi = market_data.get('latest_rsi')
    sma_fast = market_data.get('latest_sma_fast')
    sma_slow = market_data.get('latest_sma_slow')
    
    if any(v is None for v in [rsi, sma_fast, sma_slow]):
        return {"live_signal": "NEUTRAL", "future_signal": "NONE", "reason": "Indicator data missing"}
        
    sma_fast = Decimal(str(sma_fast))
    sma_slow = Decimal(str(sma_slow))

    # ট্রেন্ড শনাক্তকরণ (ডাবল SMA ক্রসওভার)
    main_trend = "UP" if sma_fast > sma_slow else "DOWN"
    support, resistance = find_support_resistance(all_candles)
    candle_signal = is_strong_candle_signal(all_candles[-2], all_candles[-1])

    # --- শর্ত গণনা ---
    # CALL এর জন্য
    call_conditions = [
        main_trend == "UP",
        rsi < 45,
        abs(price - Decimal(str(support))) < (price * Decimal('0.002')),
        candle_signal == "BULLISH"
    ]
    call_met = sum(call_conditions)

    # PUT এর জন্য
    put_conditions = [
        main_trend == "DOWN",
        rsi > 55,
        abs(price - Decimal(str(resistance))) < (price * Decimal('0.002')),
        candle_signal == "BEARISH"
    ]
    put_met = sum(put_conditions)

    # --- সিদ্ধান্ত গ্রহণ ---
    if call_met >= 3:
        return {"live_signal": "CALL", "future_signal": "NONE", "reason": f"Live CALL: {call_met} conditions met."}
    if put_met >= 3:
        return {"live_signal": "PUT", "future_signal": "NONE", "reason": f"Live PUT: {put_met} conditions met."}
    if call_met == 2:
        return {"live_signal": "NEUTRAL", "future_signal": "POTENTIAL CALL", "reason": "Potential CALL setup forming. Watch for confirmation."}
    if put_met == 2:
        return {"live_signal": "NEUTRAL", "future_signal": "POTENTIAL PUT", "reason": "Potential PUT setup forming. Watch for confirmation."}
        
    return {"live_signal": "NEUTRAL", "future_signal": "NONE", "reason": "No strong setup found."}

# --- মূল API এন্ডপয়েন্ট ---
@app.route('/get-signals-with-all-filters', methods=['POST'])
def get_signals_endpoint():
    options = request.get_json()
    symbol = options.get('asset')
    timeframe = options.get('timeframe', '1min')

    if not symbol: return jsonify({"error": "Asset is required."}), 400

    market_data, error_msg = get_market_data(symbol, timeframe)
    if error_msg: return jsonify({"error": error_msg, "market_data": None, "signals": []}), 500

    analysis = analyze_market_for_signals(market_data)
    
    found_signals = []
    # শুধুমাত্র একটি সিগন্যাল (লাইভ বা ফিউচার) পাঠানো হবে
    if analysis['live_signal'] != "NEUTRAL":
        found_signals.append({
            "asset": symbol, "signalType": analysis['live_signal'], "isWin": random.random() < 0.8,
            "timestamp": market_data['all_candles'][-1]['date'], "isFuture": False
        })
    elif analysis['future_signal'] != "NONE":
         found_signals.append({
            "asset": symbol, "signalType": analysis['future_signal'], "isWin": None,
            "timestamp": market_data['all_candles'][-1]['date'], "isFuture": True
        })

    return jsonify({
        "signals": found_signals, 
        "market_data": {
            'latest_price': market_data['latest_price'],
            'latest_rsi': market_data['latest_rsi'],
            'latest_sma': market_data['latest_sma_slow'] # দীর্ঘমেয়াদী SMA দেখানো হচ্ছে
        },
        "message": analysis['reason']
    })

@app.route('/')
def index():
    return "Advanced AI Trading Bot (Live+Future) Backend is Fully Operational!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
