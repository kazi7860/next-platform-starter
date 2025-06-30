# app.py (উন্নত কনফ্লুয়েন্স স্ট্র্যাটেজিসহ)

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# --- কনফিগারেশন ---
getcontext().prec = 10
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) # CORS সমস্যার চূড়ান্ত সমাধান
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- ডেটা আনার এবং প্রস্তুত করার ফাংশন ---

def get_market_data(symbol, timeframe='1min', limit=100):
    """ FMP API থেকে ক্যান্ডেল, RSI এবং SMA ডেটা একবারে আনে """
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    try:
        # ক্যান্ডেল ডেটা
        candles_url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?limit={limit}&apikey={FMP_API_KEY}"
        candles_data = requests.get(candles_url, timeout=15).json()
        if not isinstance(candles_data, list) or len(candles_data) < 50:
            return None, f"'{symbol}' এর জন্য যথেষ্ট মার্কেট ডেটা পাওয়া যায়নি।"
        all_candles = list(reversed(candles_data))

        # RSI ডেটা
        rsi_url = f"{BASE_URL}/technical_indicator/daily/{fmp_symbol}?period=14&type=rsi&apikey={FMP_API_KEY}"
        rsi_data = requests.get(rsi_url, timeout=10).json()
        
        # SMA ডেটা (ট্রেন্ড বোঝার জন্য)
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

# --- স্ট্র্যাটেজি সম্পর্কিত হেল্পার ফাংশন ---

def find_support_resistance(candles):
    """ শেষ ৫০টি ক্যান্ডেল থেকে সাধারণ S&R লেভেল খুঁজে বের করে """
    recent_candles = candles[-50:]
    highest_high = max(c['high'] for c in recent_candles)
    lowest_low = min(c['low'] for c in recent_candles)
    return lowest_low, highest_high

def is_bullish_engulfing(prev_candle, curr_candle):
    """ বুলিশ Engulfing প্যাটার্ন পরীক্ষা করে """
    # বর্তমান ক্যান্ডেলটি কি আগের ক্যান্ডেলকে পুরোপুরি ঢেকে ফেলেছে?
    return curr_candle['open'] < prev_candle['close'] and curr_candle['close'] > prev_candle['open']

def is_bearish_engulfing(prev_candle, curr_candle):
    """ বেয়ারিশ Engulfing প্যাটার্ন পরীক্ষা করে """
    return curr_candle['open'] > prev_candle['close'] and curr_candle['close'] < prev_candle['open']

# --- মূল কনফ্লুয়েন্স স্ট্র্যাটেজি ফাংশন ---

def check_confluence_strategy(market_data, candle_slice):
    """ একাধিক শর্ত মিলিয়ে একটি শক্তিশালী সিগন্যাল খুঁজে বের করে """
    if len(candle_slice) < 2:
        return "NEUTRAL"

    # প্রয়োজনীয় ডেটা সংগ্রহ
    prev_candle, current_candle = candle_slice
    price = Decimal(str(current_candle['close']))
    rsi = market_data.get('latest_rsi')
    sma_50 = market_data.get('latest_sma_50')
    
    if rsi is None or sma_50 is None:
        return "NEUTRAL"
        
    sma_50 = Decimal(str(sma_50))

    # ট্রেন্ড শনাক্তকরণ
    main_trend = "UP" if price > sma_50 else "DOWN"

    # সাপোর্ট এবং রেসিস্ট্যান্স লেভেল
    support, resistance = find_support_resistance(market_data['all_candles'])

    # --- CALL সিগন্যালের জন্য শর্তাবলী (কনফ্লুয়েন্স) ---
    call_conditions_met = 0
    # শর্ত ১: মূল ট্রেন্ড কি UP?
    if main_trend == "UP": call_conditions_met += 1
    # শর্ত ২: RSI কি Oversold (৪০ এর নিচে)? (৩০ এর চেয়ে ৪০ বেশি সুযোগ দেয়)
    if rsi < 40: call_conditions_met += 1
    # শর্ত ৩: প্রাইস কি সাপোর্ট লেভেলের কাছাকাছি?
    if abs(price - Decimal(str(support))) < (price * Decimal('0.001')): call_conditions_met += 1
    # শর্ত ৪: একটি Bullish Engulfing প্যাটার্ন কি তৈরি হয়েছে?
    if is_bullish_engulfing(prev_candle, current_candle): call_conditions_met += 1

    # --- PUT সিগন্যালের জন্য শর্তাবলী (কনফ্লুয়েন্স) ---
    put_conditions_met = 0
    # শর্ত ১: মূল ট্রেন্ড কি DOWN?
    if main_trend == "DOWN": put_conditions_met += 1
    # শর্ত ২: RSI কি Overbought (৬০ এর উপরে)?
    if rsi > 60: put_conditions_met += 1
    # শর্ত ৩: প্রাইস কি রেসিস্ট্যান্স লেভেলের কাছাকাছি?
    if abs(price - Decimal(str(resistance))) < (price * Decimal('0.001')): put_conditions_met += 1
    # শর্ত ৪: একটি Bearish Engulfing প্যাটার্ন কি তৈরি হয়েছে?
    if is_bearish_engulfing(prev_candle, current_candle): put_conditions_met += 1

    # সিদ্ধান্ত গ্রহণ: যদি অন্তত ৩টি শর্ত মেলে, তবেই সিগন্যাল দেওয়া হবে
    if call_conditions_met >= 3:
        return "CALL"
    if put_conditions_met >= 3:
        return "PUT"
        
    return "NEUTRAL"

# --- মূল API এন্ডপয়েন্ট ---

@app.route('/get-signals-with-all-filters', methods=['POST'])
def get_signals_endpoint():
    options = request.get_json()
    symbol = options.get('asset')
    num_signals = options.get('num_signals', 1)
    timeframe = options.get('timeframe', '1min')
    signal_filter = options.get('signal_filter', 'ALL')
    # ট্রেন্ড ফিল্টারটি এখন আর সরাসরি প্রয়োজন নেই, কারণ স্ট্র্যাটেজি নিজেই ট্রেন্ড ব্যবহার করছে

    if not symbol: return jsonify({"error": "Asset is required."}), 400

    market_data, error_msg = get_market_data(symbol, timeframe)
    if error_msg: return jsonify({"error": error_msg}), 500

    all_candles = market_data['all_candles']
    found_signals = []

    # পেছনের দিক থেকে ক্যান্ডেল পরীক্ষা করা
    for i in range(len(all_candles) - 2):
        if len(found_signals) >= num_signals: break
        
        candle_slice = all_candles[i:i+2]
        signal_type = check_confluence_strategy(market_data, candle_slice)
        
        if signal_type != "NEUTRAL":
            if signal_filter == 'ALL' or signal_filter == signal_type:
                found_signals.append({
                    "asset": symbol,
                    "signalType": signal_type,
                    "isWin": random.random() < 0.8, # ডেমো win rate
                    "timestamp": candle_slice[1]['date']
                })
    
    return jsonify({
        "signals": found_signals, 
        "market_data": {
            'latest_price': market_data['latest_price'],
            'latest_rsi': market_data['latest_rsi'],
            'latest_sma': market_data['latest_sma_50']
        }
    })

@app.route('/')
def index():
    return "Advanced Confluence Strategy Bot Backend is Running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
