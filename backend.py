import websocket
import json
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from pydantic import BaseModel

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
QUOTEX_WS_URL = "wss://quotex-websocket-url"  # Replace with actual Quotex WebSocket URL
LSTM_MODEL_PATH = "lstm_model.h5"

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data storage
prices = {}
scaler = MinMaxScaler()

# LSTM model
def create_lstm_model():
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(50, return_sequences=True, input_shape=(20, 1)),
        tf.keras.layers.LSTM(50),
        tf.keras.layers.Dense(25),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    return model

def load_lstm_model():
    try:
        return tf.keras.models.load_model(LSTM_MODEL_PATH)
    except:
        logger.warning("No trained LSTM model found. Creating new model.")
        return create_lstm_model()

def train_lstm_model(data):
    try:
        scaled_data = scaler.fit_transform(np.array(data).reshape(-1, 1))
        X, y = [], []
        for i in range(20, len(scaled_data)):
            X.append(scaled_data[i-20:i, 0])
            y.append(scaled_data[i, 0])
        X, y = np.array(X), np.array(y)
        X = X.reshape(X.shape[0], X.shape[1], 1)
        model = create_lstm_model()
        model.fit(X, y, epochs=10, batch_size=32, verbose=1)
        model.save(LSTM_MODEL_PATH)
        logger.info("LSTM model trained and saved.")
        return model
    except Exception as e:
        logger.error(f"Error in LSTM training: {e}")
        return None

lstm_model = load_lstm_model()

# Selenium setup
def setup_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    return driver

# Calculate Support/Resistance
def calculate_support_resistance(prices):
    if len(prices) < 20:
        return None, None
    df = pd.DataFrame(prices, columns=['close'])
    support = df['close'].min()
    resistance = df['close'].max()
    return support, resistance

# WebSocket handler for Quotex
def on_message(ws, message, asset):
    try:
        data = json.loads(message)
        price = data.get('price', 0)
        if price:
            if asset not in prices:
                prices[asset] = []
            prices[asset].append(price)
            logger.info(f"New price for {asset}: {price}")

            if len(prices[asset]) >= 100:
                df = pd.DataFrame(prices[asset][-100:], columns=['close'])
                df['sma'] = SMAIndicator(df['close'], window=20).sma_indicator()
                df['rsi'] = RSIIndicator(df['close']).rsi()
                macd = MACD(df['close'])
                df['macd'] = macd.macd()
                df['macd_signal'] = macd.macd_signal()

                support, resistance = calculate_support_resistance(prices[asset][-100:])
                signal_data = generate_signal(df, asset, support, resistance)
                asyncio.run(emit_signal(signal_data))
    except Exception as e:
        logger.error(f"Error in on_message: {e}")

async def emit_signal(signal_data):
    async with app.state.websocket_manager.broadcast(signal_data):
        pass  # No Telegram integration

def generate_signal(df, asset, support, resistance:
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]
    latest_rsi = df['rsi'].iloc[-1]
    latest_macd = df['macd'].iloc[-1]
    latest_macd_signal = df['macd_signal'].iloc[-1]

    signal = None
    if latest_price > latest_sma && latest_rsi > 70 and latest_macd > latest_macd_signal:
        signal = "CALL"
    elif latest_price < latest_sma && latest_rsi < 30 and latest_macd < latest_macd_signal:
        signal = "PUT"

    scaled_data = scaler.fit_transform(df['close'].values).reshape(-1, 1))
    X = scaled_data[-20:].reshape(-1, 1, 1)
    lstm_pred = lstm_model.predict(X, verbose=0)[0][0]
    lstm_signal = "CALL" if lstm_pred > latest_price else "PUT"

    return {
        "asset": asset,
        "price": latest_price,
        "sma": latest_sma,
        "rsi": latest_rsi,
        "support": support,
        "resistance": resistance,
        "signal": signal,
        "lstm_signal": lstm_signal,
        "time": time.strftime('%H:%M:%S')
    }

# WebSocket manager
class WebSocketManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data):
        for connection in self.active_connections:
            await connection.send_json(data)

app.state.websocket_manager = WebSocketManager()

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await app.state.websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await app.state.websocket_manager.disconnect(websocket)

class AssetRequest(BaseModel):
    asset: str

@app.post("/start_signals")
async def start_signals(request: Request):
    import threading
    threading.Thread(target=start_quotex_websocket, args=(request.asset,), daemon=True).start()
    return {"status": "started", "asset": request.asset}

class TrainRequest(BaseModel):
    data: list

@app.post("/train_lstm")
async def train_lstm(request: Request):
    train_lstm_model(request.data)
    return {"status": "trained"}

def start_quotex_websocket(asset):
    ws = websocket.WebSocketApp(
        QUOTEX_WS_URL,
        on_message=lambda ws, msg: on_message(ws, msg, asset),
        on_error=lambda ws, error: logger.error(f"WebSocket error: {error}"),
        on_close=lambda ws, code, msg: logger.info(f"WebSocket closed: {code} - {msg}"),
        on_open=lambda ws: ws.send(json.dumps({"action": "subscribe", "asset": asset})))
    )
    ws.run_forever()

def scrape_quoted_data():
    driver = setup_selenium()
    try:
        driver.get("https://qxbroker.com")
        time.sleep(10)  # Adjust as needed
        # Add scraping logic here if needed
    finally:
        driver.quit()

if __name__ == "__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)