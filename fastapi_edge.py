from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
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
from database import init_postgres, close_postgres
from redis_server import init_redis

mongo_client = None
robot_col = None
poi_col = None
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, robot_col, poi_col, background_tasks

    print("SERVER STARTUP..")
    
    try:
    
        # ============ Initialize MongoDB ============
        mongo_client = MongoClient("mongodb://localhost:27017/")

        db = mongo_client["robotDB"]

        robot_col = db['robots']
        poi_col = db['poi']
        print("MongoDB connected")

        # ============ Initialize PostgreSQL ============
        await init_postgres()
        print("PostgreSQL connected")

        # ============ Initialize Redis ============

        redis_task = asyncio.create_task(init_redis(app))
        background_tasks.append(redis_task)
        print("Redis initializing")


        print("SERVER INITIALIZED")

        yield
    
    finally:

        print("SERVER SHUTTING DOWN...")

        for task in background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

app = FastAPI(lifespan=lifespan)
app.include_router(robot.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/hello')
async def main_hello():
    return "hello from main server!"

if __name__ == "__main__":
    uvicorn.run("fastapi_edge:app", host='0.0.0.0', reload=True)
