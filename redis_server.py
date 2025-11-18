from fastapi import FastAPI, WebSocket, APIRouter, Request
from pymongo import MongoClient
from contextlib import asynccontextmanager
from typing import List
import asyncio
import time
import uvicorn
import websockets
import json
import httpx
from redis.asyncio import Redis

#REST URL
BASE_URL = "https://apiglobal.autoxing.com"

#WEBSOCKET URL
WS_URL = "wss://serviceglobal.autoxing.com"

#DIRECT ROBOT URL
DIRECT_URL = "http://192.168.0.250:8090"

#DIRECT ROBOT WEBSOCKET URL
DIRECT_WS = "ws://192.168.0.250:8090"

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected: {len(self.active_connections)} total")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Client disconnected: {len(self.active_connections)} remaining")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

ws_manager = ConnectionManager()

async def init_redis(app: FastAPI):
    app.state.redis = Redis(host="localhost", port=6379, decode_responses=True)

    print("REDIS SERVER INITIALIZED")

    asyncio.create_task(pub_robot_status(app.state.redis))
    asyncio.create_task(pub_lidar_points(app.state.redis))

async def pub_robot_status(redis: Redis):
    compile_list = {}

    url = DIRECT_WS+"/ws/v2/topics"
    async with websockets.connect(url) as ws:
        try:
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/battery_state"]}))

            print("REDIS STATE PUBLISH STARTED")

            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                topic = data.get("topic")

                if topic == "/battery_state":
                    compile_list.update({"battery":msg})
                if topic == "/tracked_pose":
                    compile_list.update({"pose":msg})
                    data_json = json.dumps(compile_list)

                    await redis.publish("robot:state", data_json)

                    #print(f"TOPIC PUBLISH: [{round(time.time(),1)}]", data_json)
            
        except Exception as e:
            print("WebSocket closed:", e)
        finally:
            await ws.close()

async def sub_robot_status(request: Request):
    pubsub = request.app.state.redis.pubsub()
    await pubsub.subscribe("robot:pose")
    print("Subscribed to robot:pose")

    try:
        async for message in pubsub.listen():
            print("REDIS SUB DATA: ",message)
            if message["type"] == "message":
                data = message["data"]
                print("Received robot pose:", data)
                return message
    except Exception as e:
        print("Subscriber error:", e)
    finally:
        await websocket.close()
        await pubsub.close()
        print("Subscriber closed")

async def pub_lidar_points(redis: Redis):
    url = DIRECT_WS+"/ws/v2/topics"

    async with websockets.connect(url) as ws:
        try:
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/scan_matched_points2"]}))

            while True:
                msg = await ws.recv()

                await redis.publish(
                    "robot:lidar", msg
                )

                #print(f"TOPIC PUBLISH: [{round(time.time(),1)}]", msg)

        except Exception as e:
            print(e)   