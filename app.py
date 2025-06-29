# app.py

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random

# Flask অ্যাপ ইনিশিয়ালাইজ করা
app = Flask(__name__)
# CORS সক্রিয় করা যাতে আপনার HTML পেজ এই সার্ভারে রিকোয়েস্ট পাঠাতে পারে
CORS(app)

# --- আপনার দেওয়া FMP API Key ---
FMP_API_KEY = "kSy6pLcFKTueuh4QZqOSU3BbLWTwR48N"

def get_market_data(symbol, timeframe='1min', rsi_period=14, sma_period=10):
    """
    FMP API ব্যবহার করে নির্দিষ্ট অ্যাসেটের জন্য ডেটা আনে।
    """
    # FMP সাধারণত হাইফেন (-) বা স্ল্যাশ (/) ছাড়া সিম্বল ব্যবহার করে
    fmp_symbol = symbol.replace('/', '').replace('-', '').replace('-OTC', '')

    base_url = "https://financialmodelingprep.com/api/v3"
    
    try:
        # FMP API থেকে রিয়েল-টাইম কোট (মূল্য) আনা
        # ফরেক্স পেয়ারের জন্য আলাদা এন্ডপয়েন্ট ব্যবহার করলে ভালো ফলাফল পাওয়া যায়
        if len(fmp_symbol) == 6 and fmp_symbol.isalpha(): # যেমন EURUSD, GBPJPY
             quote_url = f"{base_url}/forex/{fmp_symbol}?apikey={FMP_API_KEY}"
        else: # স্টক, ক্রিপ্টো ইত্যাদির জন্য
             quote_url = f"{base_url}/quote/{fmp_symbol}?apikey={FMP_API_KEY}"
        
        quote_response = requests.get(quote_url)
        quote_response.raise_for_status() # HTTP error থাকলে exception দেবে
        quote_data = quote_response.json()

        if not quote_data:
            return {"error": f"'{symbol}' এর জন্য কোনো Quote ডেটা পাওয়া যায়নি। সিম্বলটি সঠিক কিনা দেখুন।"}

        # কিছু ক্ষেত্রে ডেটা একটি লিস্টের মধ্যে আসে
        current_price = quote_data[0].get('price') or quote_data[0].get('bid')

        # FMP API থেকে টেকনিক্যাল ইন্ডিকেটর (RSI) আনা
        rsi_url = f"{base_url}/technical_indicator/{timeframe}/{fmp_symbol}?period={rsi_period}&type=rsi&apikey={FMP_API_KEY}"
        rsi_response = requests.get(rsi_url)
        rsi_response.raise_for_status()
        rsi_data = rsi_response.json()
        current_rsi = rsi_data[0].get('rsi') if rsi_data else None

        # FMP API থেকে সিম্পল মুভিং অ্যাভারেজ (SMA) আনা
        sma_url = f"{base_url}/technical_indicator/{timeframe}/{fmp_symbol}?period={sma_period}&type=sma&apikey={FMP_API_KEY}"
        sma_response = requests.get(sma_url)
        sma_response.raise_for_status()
        sma_data = sma_response.json()
        current_sma = sma_data[0].get('sma') if sma_data else None

        return {
            "price": current_price,
            "rsi": current_rsi,
            "sma": current_sma,
            "error": None
        }

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {http_err.response.text}")
        error_message = f"FMP API থেকে ডেটা আনতে সমস্যা হয়েছে। স্ট্যাটাস কোড: {http_err.response.status_code}. এটি একটি ভুল সিম্বল অথবা API কী-র সমস্যা হতে পারে।"
        return {"error": error_message}
    except Exception as e:
        print(f"API কল করার সময় একটি সাধারণ সমস্যা হয়েছে: {e}")
        return {"error": str(e)}

@app.route('/generate-signal', methods=['POST'])
def generate_signal():
    """
    ফ্রন্টএন্ড থেকে রিকোয়েস্ট পাওয়ার পর সিগন্যাল তৈরি করে পাঠায়।
    """
    req_data = request.get_json()
    symbol = req_data.get('asset')

    if not symbol:
        return jsonify({"error": "Asset symbol is required."}), 400

    # FMP থেকে অ্যাসেটের ডেটা আনা
    market_data = get_market_data(symbol)

    if market_data.get("error"):
        return jsonify({"error": market_data.get("error")}), 500

    price = market_data.get("price")
    rsi = market_data.get("rsi")
    sma = market_data.get("sma")

    # --- সিগন্যাল তৈরির লজিক ---
    signal_type = "NEUTRAL"
    confidence = 0.5

    if rsi is not None and sma is not None and price is not None:
        if rsi > 70 and price < sma:  # Overbought এবং প্রাইস SMA এর নিচে (শক্তিশালী PUT)
            signal_type = "PUT"
            confidence = 0.8
        elif rsi < 30 and price > sma:  # Oversold এবং প্রাইস SMA এর উপরে (শক্তিশালী CALL)
            signal_type = "CALL"
            confidence = 0.8
        elif rsi > 65:
            signal_type = "PUT"
            confidence = 0.6
        elif rsi < 35:
            signal_type = "CALL"
            confidence = 0.6

    # একটি র‍্যান্ডম win/loss ফলাফল তৈরি করা
    is_win = True if random.random() < confidence else False

    result = {
        "asset": symbol,
        "signalType": signal_type,
        "isWin": is_win,
        "price": price,
        "rsi": rsi,
        "sma": sma,
        "message": f"Signal for {symbol} generated."
    }
    
    return jsonify(result)

# একটি রুট এন্ডপয়েন্ট, যা ব্রাউজারে অ্যাপটি লাইভ আছে কিনা তা পরীক্ষা করতে সাহায্য করবে
@app.route('/')
def index():
    return "Backend server for Trading Bot is running!"

# সার্ভারটি চালানোর জন্য
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)