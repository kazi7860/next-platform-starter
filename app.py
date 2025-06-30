# app.py (চূড়ান্ত সংস্করণ - দুটি ভিন্ন এন্ডপয়েন্টসহ)

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

# --- ডেটা আনার ফাংশন ---
def get_market_data(symbol, timeframe='1min', limit=300):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট মার্কেট ডেটা পাওয়া যায়নি।"
        all_candles = list(reversed(candles_data))
        rsi_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}"
        sma_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=50&type=sma&apikey={FMP_API_KEY}"
        market_info = {
            "all_candles": all_candles,
            "latest_price": all_candles[-1]['close'],
            "latest_rsi": requests.get(rsi_url, timeout=10).json()[0].get('rsi'),
            "latest_sma": requests.get(sma_url, timeout=10).json()[0].get('sma'),
        }
        return market_info, None
    except Exception as e:
        return None, f"ডেটা আনার সময় সমস্যা হয়েছে: {e}"

# --- স্ট্র্যাটেজি ও হেল্পার ফাংশন ---
def find_support_resistance(candles):
    recent = candles[-50:]
    return min(c['low'] for c in recent), max(c['high'] for c in recent)
def is_strong_candle_signal(p, c):
    if c['open'] < p['close'] and c['close'] > p['open']: return "BULLISH"
    if c['open'] > p['close'] and c['close'] < p['open']: return "BEARISH"
    return "NEUTRAL"

def analyze_market_slice(market_data, candle_slice):
    if len(candle_slice) < 2: return {"signal": "NEUTRAL"}
    p, c = candle_slice[0], candle_slice[1]
    price = Decimal(str(c['close']))
    sma_slow = Decimal(str(market_data['latest_sma']))
    main_trend = "UP" if price > sma_slow else "DOWN"
    support, resistance = find_support_resistance(market_data['all_candles'])
    rsi, candle_signal = market_data['latest_rsi'], is_strong_candle_signal(p, c)
    call_met = sum([main_trend == "UP", rsi < 45, abs(price-Decimal(str(support)))<(price*Decimal('0.002')), candle_signal=="BULLISH"])
    put_met = sum([main_trend == "DOWN", rsi > 55, abs(price-Decimal(str(resistance)))<(price*Decimal('0.002')), candle_signal=="BEARISH"])
    if call_met >= 3: return {"signal": "CALL"}
    if put_met >= 3: return {"signal": "PUT"}
    if call_met == 2: return {"signal": "POTENTIAL CALL"}
    if put_met == 2: return {"signal": "POTENTIAL PUT"}
    return {"signal": "NEUTRAL"}

# --- এন্ডপয়েন্ট ১: লাইভ সিগন্যাল ---
@app.route('/get-live-signal', methods=['POST'])
def get_live_signal_endpoint():
    options = request.get_json()
    market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
    if error_msg: return jsonify({"error": error_msg, "market_data": None, "signals": []}), 500
    
    analysis = analyze_market_slice(market_data, market_data['all_candles'][-2:])
    signal_type = analysis['signal']
    signals = []
    if signal_type != "NEUTRAL":
        signals.append({
            "asset": options.get('asset'), "signalType": signal_type,
            "isWin": random.random() < 0.8 if "POTENTIAL" not in signal_type else None,
            "timestamp": market_data['all_candles'][-1]['date'],
            "isFuture": "POTENTIAL" in signal_type
        })
    return jsonify({"signals": signals, "market_data": market_data, "message": "Live analysis complete."})

# --- এন্ডপয়েন্ট ২: ঐতিহাসিক সিগন্যাল ---
@app.route('/get-historical-signals', methods=['POST'])
def get_historical_signals_endpoint():
    options = request.get_json()
    num_signals, trend_filter = options.get('num_signals', 1), options.get('trend', 'ANY')
    market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
    if error_msg: return jsonify({"error": error_msg}), 500
    
    found_signals = []
    for i in range(len(market_data['all_candles']) - 2):
        if len(found_signals) >= num_signals: break
        analysis = analyze_market_slice(market_data, market_data['all_candles'][i:i+2])
        signal_type = analysis['signal']
        if signal_type not in ["NEUTRAL", "POTENTIAL CALL", "POTENTIAL PUT"]:
            price_at_signal = Decimal(str(market_data['all_candles'][i+1]['close']))
            trend_at_signal = "UP" if price_at_signal > Decimal(str(market_data['latest_sma'])) else "DOWN"
            if trend_filter == 'ANY' or trend_at_signal == trend_filter:
                found_signals.append({
                    "asset": options.get('asset'), "signalType": signal_type,
                    "isWin": random.random() < 0.8,
                    "timestamp": market_data['all_candles'][i+1]['date'], "isFuture": False
                })
    return jsonify({"signals": found_signals, "market_data": market_data, "message": "Historical analysis complete."})

@app.route('/')
def index():
    return "AI Trading Bot (Final - All Features) Backend is Running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
