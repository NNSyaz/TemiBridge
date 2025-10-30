from fastapi import FastAPI, WebSocket
from pymongo import MongoClient
from contextlib import asynccontextmanager
import asyncio
import time
import uvicorn
import websockets
import json
import httpx
import robot

@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = MongoClient("mongodb://localhost:27017/")

    db = mongo_client["robotDB"]

    global robot_col
    robot_col = db['robots']

app = FastAPI()
app.include_router(robot.router)

@app.get('/hello')
async def main_hello():
    return "hello from main server!"

if __name__ == "__main__":
    uvicorn.run("fastapi_edge:app", host='0.0.0.0', reload=True)