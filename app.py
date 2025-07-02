# app.py (চূড়ান্ত সমাধান - উন্নত এরর হ্যান্ডলিংসহ)

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

# --- ডেটা আনার এবং হেল্পার ফাংশন (উন্নত এরর হ্যান্ডলিং) ---
def get_market_data(symbol, timeframe='1min', limit=100):
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('^', '')
    try:
        # সব API এন্ডপয়েন্ট
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        
        # API কল এবং স্ট্যাটাস কোড চেক
        candles_response = requests.get(candles_url, timeout=20)
        if candles_response.status_code != 200:
            # API লিমিট শেষ হলে বা অন্য কোনো সমস্যা হলে
            try:
                error_content = candles_response.json()
                api_error_message = error_content.get("error", "API থেকে ডেটা আনতে সমস্যা হয়েছে।")
                if "limit" in api_error_message.lower():
                    return None, "আপনার দৈনিক API ব্যবহারের সীমা শেষ হয়ে গেছে।"
                return None, f"API Error: {api_error_message}"
            except:
                return None, f"API Error (Status {candles_response.status_code}): {candles_response.text}"

        candles_data = candles_response.json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট ক্যান্ডেল ডেটা পাওয়া যায়নি।"
        
        all_candles = list(reversed(candles_data))
        
        # অন্যান্য ইন্ডিকেটর
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
    except requests.exceptions.RequestException as e:
        return None, f"নেটওয়ার্ক সমস্যা: {e}"
    except Exception as e:
        return None, f"ডেটা প্রসেসিং এ সমস্যা: {e}"

# --- আপনার অন্যান্য ফাংশন (analyze_live_market, find_support_resistance, ইত্যাদি) অপরিবর্তিত থাকবে ---
def find_support_resistance(candles): recent = candles[-50:]; return min(c['low'] for c in recent), max(c['high'] for c in recent)
def is_strong_candle_signal(p, c):
    try:
        if c.get('open') < p.get('close') and c.get('close') > p.get('open'): return "BULLISH"
        if c.get('open') > p.get('close') and c.get('close') < p.get('open'): return "BEARISH"
    except (TypeError, KeyError): pass
    return "NEUTRAL"
def analyze_live_market(market_data, trend_filter, signal_filter):
    # ... আগের উত্তর থেকে এই ফাংশনটি কপি করুন ...
    pass

# --- মূল API এন্ডপয়েন্ট (অপরিবর্তিত) ---
@app.route('/get-signal', methods=['POST'])
def get_signal_endpoint():
    try:
        # ... আগের উত্তর থেকে এই ফাংশনটি কপি করুন ...
        pass
    except Exception as e:
        return jsonify({"error": f"সার্ভারে একটি অপ্রত্যাশিত সমস্যা হয়েছে: {e}"}), 500
@app.route('/get-market-update', methods=['POST'])
def get_market_update_endpoint():
    try:
        # ... আগের উত্তর থেকে এই ফাংশনটি কপি করুন ...
        pass
    except Exception as e:
        return jsonify({"error": f"মার্কেট আপডেট এ সমস্যা: {e}"}), 500

@app.route('/')
def index():
    return "AI Trading Bot (Error Handling v3) Backend is Running!"

# --- সম্পূর্ণ কার্যকরী কোড নিচে দেওয়া হলো ---
def analyze_live_market(market_data, trend_filter, signal_filter):
    try:
        all_candles = market_data['all_candles']
        if len(all_candles) < 2: return {"signal": "NONE", "reason": "Not enough data"}
        price = Decimal(str(market_data['latest_price'])); sma_slow = Decimal(str(market_data['latest_sma']))
        main_trend = "UP" if price > sma_slow else "DOWN"
        if trend_filter != 'ANY' and main_trend != trend_filter: return {"signal": "NONE", "reason": f"বর্তমান ট্রেন্ড ({main_trend}) আপনার '{trend_filter}' ফিল্টারের সাথে মেলেনি।"}
        rsi, support, resistance = market_data.get('latest_rsi'), market_data.get('support'), market_data.get('resistance')
        candle_signal = is_strong_candle_signal(all_candles[-2], all_candles[-1])
        call_conditions = [(main_trend == "UP", "ট্রেন্ড UP"), (rsi < 45, "RSI কম"), (abs(price-Decimal(str(support)))<(price*Decimal('0.002')), "সাপোর্টের কাছে"), (candle_signal=="BULLISH", "বুলিশ ক্যান্ডেল")]
        put_conditions = [(main_trend == "DOWN", "ট্রেন্ড DOWN"), (rsi > 55, "RSI বেশি"), (abs(price-Decimal(str(resistance)))<(price*Decimal('0.002')), "রেসিস্ট্যান্সের কাছে"), (candle_signal=="BEARISH", "বেয়ারিশ ক্যান্ডেল")]
        call_met, put_met = sum(c[0] for c in call_conditions), sum(c[0] for c in put_conditions)
        if call_met >= 3 and signal_filter in ["ALL", "CALL"]: return {"signal": "CALL", "is_future": False, "reason": "লাইভ সিগন্যাল: শর্ত মিলেছে।"}
        if put_met >= 3 and signal_filter in ["ALL", "PUT"]: return {"signal": "PUT", "is_future": False, "reason": "লাইভ সিগন্যাল: শর্ত মিলেছে।"}
        if call_met == 2 and signal_filter in ["ALL", "CALL"]: reasons = [r for met, r in call_conditions if met]; return {"signal": "POTENTIAL CALL", "is_future": True, "reason": " এবং ".join(reasons) + "।"}
        if put_met == 2 and signal_filter in ["ALL", "PUT"]: reasons = [r for met, r in put_conditions if met]; return {"signal": "POTENTIAL PUT", "is_future": True, "reason": " এবং ".join(reasons) + "।"}
        return {"signal": "NONE", "reason": "এই মুহূর্তে কোনো ভালো সুযোগ তৈরি হচ্ছে না।"}
    except Exception as e: return {"signal": "NONE", "reason": f"স্ট্র্যাটেজি অ্যানালাইসিস এ সমস্যা: {e}"}

@app.route('/get-signal', methods=['POST'])
def get_signal_endpoint_full():
    try:
        options = request.get_json()
        asset, timeframe, trend_filter, signal_filter = options.get('asset'), options.get('timeframe'), options.get('trend_filter'), options.get('signal_filter')
        if not asset: return jsonify({"error": "Asset is required."}), 400
        market_data, error_msg = get_market_data(asset, timeframe)
        if error_msg: return jsonify({"error": error_msg, "market_data": None, "analysis": None}), 400
        analysis = analyze_live_market(market_data, trend_filter, signal_filter)
        return jsonify({ "analysis": analysis, "market_data": market_data })
    except Exception as e: return jsonify({"error": f"সার্ভারে একটি অপ্রত্যাশিত সমস্যা হয়েছে: {e}"}), 500

@app.route('/get-market-update', methods=['POST'])
def get_market_update_endpoint_full():
    try:
        options = request.get_json()
        market_data, error_msg = get_market_data(options.get('asset'), options.get('timeframe'))
        if error_msg: return jsonify({"error": error_msg}), 400
        return jsonify(market_data)
    except Exception as e: return jsonify({"error": f"মার্কেট আপডেট এ সমস্যা: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
