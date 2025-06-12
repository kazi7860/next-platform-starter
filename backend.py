from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World from Vercel"}

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "Test signal from Vercel"})
    await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
