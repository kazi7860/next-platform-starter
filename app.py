# app.py (চূড়ান্ত সংস্করণ - সব ফিল্টার কার্যকরী)

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- ডেটা আনার এবং হেল্পার ফাংশন ---
def get_market_data(symbol, timeframe='1min', limit=300):
    fmp_symbol = symbol.replace('/', '').replace('-', '')
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
            "all_candles": all_candles, "latest_price": all_candles[-1]['close'],
            "support": support, "resistance": resistance,
            "latest_rsi": rsi_data[0].get('rsi') if rsi_data else None,
            "short_ma": sma_short_data[0].get('sma') if sma_short_data else None,
            "latest_sma": sma_long_data[0].get('sma') if sma_long_data else None,
        }, None
    except Exception as e:
        return None, f"ডেটা আনার সময় সমস্যা হয়েছে: {e}"

def find_support_resistance(candles):
    recent = candles[-50:]
    return min(c['low'] for c in recent), max(c['high'] for c in recent)

def analyze_market_slice(candle_slice, trend_filter):
    if len(candle_slice) < 2: return {"signal": "NEUTRAL"}
    p_candle, c_candle = candle_slice
    if 'close' not in c_candle or 'open' not in p_candle: return {"signal": "NEUTRAL"}

    trend_of_slice = "UP" if c_candle['close'] > p_candle['open'] else "DOWN"
    if trend_filter != 'ANY' and trend_of_slice != trend_filter:
        return {"signal": "NEUTRAL"}
    
    # আপনার কনফ্লুয়েন্স স্ট্র্যাটেজি এখানে যোগ করতে পারেন
    if c_candle['open'] < p_candle['close'] and c_candle['close'] > p_candle['open']: return {"signal": "CALL"}
    if c_candle['open'] > p_candle['close'] and c_candle['close'] < p_candle['open']: return {"signal": "PUT"}
    return {"signal": "NEUTRAL"}

# --- মূল API এন্ডপয়েন্ট ---
@app.route('/get-historical-signals', methods=['POST'])
def get_historical_signals_endpoint():
    options = request.get_json()
    asset, timeframe = options.get('asset'), options.get('timeframe')
    num_signals, signal_filter, trend_filter = options.get('num_signals'), options.get('signal_filter'), options.get('trend_filter')

    if not asset: return jsonify({"error": "Asset is required."}), 400
    
    market_data, error_msg = get_market_data(asset, timeframe)
    if error_msg: return jsonify({"error": error_msg, "market_data": None}), 500

    found_signals, all_candles = [], market_data['all_candles']
    for i in range(len(all_candles) - 2, 0, -1):
        if len(found_signals) >= num_signals: break
        
        analysis = analyze_market_slice(all_candles[i:i+2], trend_filter)
        signal_type = analysis['signal']
        
        if signal_type != "NEUTRAL" and (signal_filter == 'ALL' or signal_filter == signal_type):
            is_win = all_candles[i+2]['close'] > all_candles[i+1]['close'] if signal_type == "CALL" else all_candles[i+2]['close'] < all_candles[i+1]['close']
            found_signals.append({
                "asset": asset, "signalType": signal_type,
                "isWin": is_win, "timestamp": all_candles[i+1]['date']
            })
    
    return jsonify({"signals": found_signals, "market_data": market_data})

@app.route('/get-market-update', methods=['POST'])
def get_market_update_endpoint():
    options = request.get_json()
    market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
    if error_msg: return jsonify({"error": error_msg}), 500
    return jsonify(market_data)

@app.route('/')
def index():
    return "AI Bot Final Corrected Version - All Filters Active!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
