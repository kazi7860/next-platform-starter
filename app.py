# app.py

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
from decimal import Decimal, getcontext

# ... Decimal, Flask, CORS কনফিগারেশন আগের মতোই ...
app = Flask(__name__)
CORS(app)

FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"
BASE_URL = "https://financialmodelingprep.com/api/v3"

def get_historical_candles(symbol, timeframe='1min', limit=200): # এখন বেশি ডেটা আনব
    fmp_symbol = symbol.replace('/', '').replace('-', '')
    url = f"{BASE_URL}/historical-chart/{timeframe}/{fmp_symbol}?apikey={FMP_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return list(reversed(data[:limit]))
    except Exception as e:
        print(f"Error fetching historical data: {e}")
        return None

def find_round_numbers(price):
    # ... এই ফাংশনটি অপরিবর্তিত ...
    price_decimal = Decimal(str(price))
    increment = Decimal('0.00500')
    if price > 100: # JPY পেয়ার বা স্টকের জন্য
        increment = Decimal('0.500')
    elif price > 10: # ক্রিপ্টোর জন্য
        increment = Decimal('50.0')
    lower_round = (price_decimal // increment) * increment
    upper_round = lower_round + increment
    return lower_round, upper_round

def check_round_number_strategy(candles, trend_filter):
    if not candles or len(candles) < 3:
        return {"signal": "NEUTRAL", "reason": "Not enough data."}
    
    breakout_candle = candles[1]
    confirmation_candle = candles[2]
    close_price = breakout_candle['close']
    lower_round, upper_round = find_round_numbers(close_price)

    # Bullish Breakout (CALL)
    if breakout_candle['open'] < upper_round and breakout_candle['close'] > upper_round:
        if trend_filter != "DOWN": # যদি DOWN ট্রেন্ড ফিল্টার না থাকে
            if confirmation_candle['close'] < upper_round:
                return {"signal": "TRAP", "reason": f"Bullish trap at {upper_round}."}
            if confirmation_candle['close'] > confirmation_candle['open']:
                return {"signal": "CALL", "reason": f"Confirmed bullish breakout at {upper_round}."}

    # Bearish Breakout (PUT)
    if breakout_candle['open'] > lower_round and breakout_candle['close'] < lower_round:
        if trend_filter != "UP": # যদি UP ট্রেন্ড ফিল্টার না থাকে
            if confirmation_candle['close'] > lower_round:
                return {"signal": "TRAP", "reason": f"Bearish trap at {lower_round}."}
            if confirmation_candle['close'] < confirmation_candle['open']:
                return {"signal": "PUT", "reason": f"Confirmed bearish breakout at {lower_round}."}

    return {"signal": "NEUTRAL", "reason": "No clear breakout."}

# নতুন এন্ডপয়েন্ট
@app.route('/generate-signals-strategy', methods=['POST'])
def generate_signals_endpoint():
    req_data = request.get_json()
    symbol = req_data.get('asset')
    num_signals = req_data.get('num_signals', 1)
    trend = req_data.get('trend', 'ANY') # ডিফল্ট 'ANY'

    if not symbol:
        return jsonify({"error": "Asset symbol is required."}), 400

    # আমরা যথেষ্ট পরিমাণ ক্যান্ডেল আনব যাতে সিগন্যাল খোঁজা যায়
    candles = get_historical_candles(symbol, timeframe='1min', limit=200)

    if not candles:
        return jsonify({"error": f"Could not fetch data for {symbol}."}), 500

    found_signals = []
    
    # আমরা পেছনের দিক থেকে ক্যান্ডেলগুলো পরীক্ষা করব
    for i in range(len(candles) - 3):
        # প্রতিবার ৩টি ক্যান্ডেলের একটি স্লাইস নিয়ে পরীক্ষা করব
        candle_slice = candles[i:i+3]
        
        strategy_result = check_round_number_strategy(candle_slice, trend)
        signal_type = strategy_result['signal']
        
        if signal_type != "NEUTRAL" and signal_type != "TRAP":
            is_win = random.random() < 0.75 # ডেমো win/loss
            
            found_signals.append({
                "asset": symbol,
                "signalType": signal_type,
                "isWin": is_win,
                "reason": strategy_result['reason'],
                "timestamp": candle_slice[2]['date'] # সিগন্যালের সময়
            })
            
            # যদি কাঙ্ক্ষিত সংখ্যক সিগন্যাল পাওয়া যায়, লুপ বন্ধ হবে
            if len(found_signals) >= num_signals:
                break

    # সর্বশেষ মার্কেট ডেটা পাঠানোর জন্য
    latest_candle = candles[-1]
    market_data = {
        "price": latest_candle['close'],
        "rsi": None, "sma": None # এই স্ট্র্যাটেজিতে প্রয়োজন নেই
    }
    
    return jsonify({"signals": found_signals, "market_data": market_data})

# ... রুট এন্ডপয়েন্ট এবং main ফাংশন অপরিবর্তিত ...
@app.route('/')
def index():
    return "Trading Bot Backend with Filters is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
