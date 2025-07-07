from flask import Flask, request, jsonify
from flask_cors import CORS
from quotexapi.ws import Quotex
import threading
import time

app = Flask(__name__)
CORS(app)

# সর্বশেষ ক্যান্ডেল ডেটা রাখার জন্য
latest_candles = {}

# আপনার কনফিগারেশন দিন (সিক্রেট রাখতে চাইলে Render variable ব্যবহার করুন)
EMAIL = "your_quotex_email"
PASSWORD = "your_quotex_password"

q = Quotex(EMAIL, PASSWORD)

def on_candle(data):
    # data['symbol'] = e.g. 'EURUSD_OTC'
    asset = data.get('symbol')
    if asset:
        latest_candles[asset] = data

def on_connect():
    print("Connected to Quotex!")
    # যতগুলো অ্যাসেট লাগবে, এখানে সাবস্ক্রাইব করুন
    for asset in [
        "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC"  # চাইলে আরও অ্যাসেট
    ]:
        q.select_asset(asset)
        q.subscribe_candles(asset, 60)  # 1 মিনিট টাইমফ্রেম

q.on_candle = on_candle
q.on_connect = on_connect

# Quotex connect রাখতে background thread
def run_quotex():
    q.connect()
    while True:
        time.sleep(1)

threading.Thread(target=run_quotex, daemon=True).start()

@app.route('/api/otcdata')
def get_otc_data():
    asset = request.args.get('asset', '').replace('/', '').replace('-', '').upper() + "_OTC"
    candle = latest_candles.get(asset)
    if not candle:
        return jsonify({"error": "No data yet"}), 404
    # মার্কেট ডেটা return করুন
    return jsonify({
        "asset": asset,
        "price": candle.get('close'),
        "open": candle.get('open'),
        "high": candle.get('max'),
        "low": candle.get('min'),
        "start": candle.get('from'),
        "end": candle.get('to'),
        # চাইলে RSI, MA নিজে ক্যালকুলেট করে এখানে দিন
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0')