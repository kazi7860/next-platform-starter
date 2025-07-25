from fastapi import FastAPI, WebSocket
import pyquotex
import asyncio
import json

app = FastAPI()

# Quotex সংযোগ (তোমার ইমেইল ও পাসওয়ার্ড এখানে যোগ করা হয়েছে)
quotex = pyquotex.Quotex()
email = "kazimahedihasantushar@gmail.com"  # তোমার Quotex/Gmail ইমেইল
password = "LOVE78690"                     # তোমার পাসওয়ার্ড
quotex.connect()
quotex.login(email, password)

async def get_live_signal():
    while True:
        asset = "USD_BRL-OTC"  # উদাহরণ, তুমি পরিবর্তন করতে পারো
        data = quotex.get_candles(asset, 60, 10)  # 60 সেকেন্ডের 10 ক্যান্ডল
        if data:
            last_candle = data[-1]
            close_price = last_candle[4]  # Closing price
            signal = "Buy" if close_price > data[-2][4] else "Sell"  # সরল সিগনাল
            yield json.dumps({"asset": asset, "signal": signal, "price": close_price})
        await asyncio.sleep(5)  # 5 সেকেন্ড অন্তর আপডেট

@app.get("/")
async def root():
    return {"message": "Quotex Signal Server"}

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async for signal in get_live_signal():
        await websocket.send_text(signal)
    await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
