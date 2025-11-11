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
from redis.asyncio import Redis
from redis_server import init_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("SERVER STARTUP..")
    mongo_client = MongoClient("mongodb://localhost:27017/")

    db = mongo_client["robotDB"]

    global robot_col
    robot_col = db['robots']

    #app.state.redis = Redis(host="localhost", port=6379, decode_responses=True)

    asyncio.create_task(init_redis(app))

    #asyncio.create_task(robot.stream_robot_pose())

    print("SERVER INITIALIZED")

    yield

    print("SERVER SHUTTING DOWN...")

app = FastAPI(lifespan=lifespan)
app.include_router(robot.router)

@app.get('/hello')
async def main_hello():
    return "hello from main server!"

if __name__ == "__main__":
    uvicorn.run("fastapi_edge:app", host='0.0.0.0', reload=True)

