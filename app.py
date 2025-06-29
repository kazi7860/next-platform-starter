# app.py

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# উচ্চ precision এর জন্য Decimal কনফিগার করা
getcontext().prec = 8

# Flask অ্যাপ এবং CORS কনফিগারেশন
app = Flask(__name__)
CORS(app)

FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

def get_historical_candles(symbol, timeframe='1min', limit=5):
    """ FMP থেকে শেষ কয়েকটি ক্যান্ডেলের OHLC ডেটা আনে """
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?apikey={FMP_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        # ডেটা উল্টো করে সাজানো যাতে নতুন ক্যান্ডেল শেষে থাকে
        return list(reversed(data[:limit]))
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {e}")
        return None

def find_round_numbers(price):
    """ বর্তমান প্রাইসের কাছাকাছি রাউন্ড নাম্বার খুঁজে বের করে """
    price_decimal = Decimal(str(price))
    # উদাহরণ: 1.12345 এর জন্য 1.12000 এবং 1.12500 খুঁজবে
    # এই লজিকটি অ্যাসেট অনুযায়ী আরও উন্নত করা প্রয়োজন
    increment = Decimal('0.00500') # ফরেক্সের জন্য
    if price < 10: # ক্রিপ্টো বা স্টকের জন্য ভিন্ন হতে পারে
        increment = Decimal('50.0')

    lower_round = (price_decimal // increment) * increment
    upper_round = lower_round + increment
    return lower_round, upper_round

def check_round_number_strategy(candles):
    """ Round Number Breakout + Confirmation + Trap Identification স্ট্র্যাটেজি প্রয়োগ করে """
    if not candles or len(candles) < 3:
        return {"signal": "NEUTRAL", "reason": "Not enough candle data."}

    # শেষ তিনটি ক্যান্ডেল নেওয়া (older, breakout_candidate, confirmation_candidate)
    last_three_candles = candles[-3:]
    breakout_candle = last_three_candles[1]
    confirmation_candle = last_three_candles[2]
    
    close_price = breakout_candle['close']
    
    lower_round, upper_round = find_round_numbers(close_price)

    # --- সিগন্যাল লজিক ---

    # Bullish Breakout (CALL) চেক
    # ব্রেকআউট ক্যান্ডেলটি কি একটি আপার রাউন্ড নাম্বার ব্রেক করেছে?
    if breakout_candle['open'] < upper_round and breakout_candle['close'] > upper_round:
        # Trap Identification (ফাঁদ শনাক্তকরণ)
        # কনফার্মেশন ক্যান্ডেলটি কি আবার নিচে নেমে এসেছে?
        if confirmation_candle['close'] < breakout_candle['close'] and confirmation_candle['close'] < upper_round:
            return {"signal": "TRAP", "reason": f"Bullish breakout trap at {upper_round}. Price failed to hold."}
        
        # Confirmation Candle (কনফার্মেশন যাচাই)
        # কনফার্মেশন ক্যান্ডেলটিও কি বুলিশ?
        if confirmation_candle['close'] > confirmation_candle['open'] and confirmation_candle['close'] > upper_round:
             return {"signal": "CALL", "reason": f"Confirmed bullish breakout at {upper_round}."}

    # Bearish Breakout (PUT) চেক
    # ব্রেকআউট ক্যান্ডেলটি কি একটি লোয়ার রাউন্ড নাম্বার ব্রেক করেছে?
    if breakout_candle['open'] > lower_round and breakout_candle['close'] < lower_round:
        # Trap Identification
        if confirmation_candle['close'] > breakout_candle['close'] and confirmation_candle['close'] > lower_round:
            return {"signal": "TRAP", "reason": f"Bearish breakout trap at {lower_round}. Price failed to hold."}
            
        # Confirmation Candle
        if confirmation_candle['close'] < confirmation_candle['open'] and confirmation_candle['close'] < lower_round:
            return {"signal": "PUT", "reason": f"Confirmed bearish breakout at {lower_round}."}

    return {"signal": "NEUTRAL", "reason": "No clear breakout signal found."}


@app.route('/generate-signal', methods=['POST'])
def generate_signal_endpoint():
    req_data = request.get_json()
    symbol = req_data.get('asset')

    if not symbol:
        return jsonify({"error": "Asset symbol is required."}), 400

    # শেষ ৫টি ক্যান্ডেলের ডেটা আনা
    candles = get_historical_candles(symbol, timeframe='1min', limit=5)

    if not candles:
        return jsonify({"error": f"Could not fetch historical data for {symbol}."}), 500

    # স্ট্র্যাটেজি প্রয়োগ করে সিগন্যাল পাওয়া
    strategy_result = check_round_number_strategy(candles)
    signal_type = strategy_result['signal']
    reason = strategy_result['reason']

    # ডেমোর জন্য একটি র‍্যান্ডম win/loss
    is_win = random.random() < 0.75 if signal_type != "NEUTRAL" else False

    # ফ্রন্টএন্ডে পাঠানোর জন্য ডেটা প্রস্তুত করা
    latest_candle = candles[-1]
    result = {
        "asset": symbol,
        "signalType": signal_type,
        "isWin": is_win,
        "price": latest_candle['close'],
        "rsi": None, # এই স্ট্র্যাটেজিতে RSI ব্যবহার করা হয়নি
        "sma": None,  # এই স্ট্র্যাটেজিতে SMA ব্যবহার করা হয়নি
        "message": reason # ফ্রন্টএন্ডে দেখানোর জন্য কারণ
    }
    
    return jsonify(result)


@app.route('/')
def index():
    return "Trading Bot Backend with Round Number Strategy is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
