from fastapi import FastAPI, WebSocket, APIRouter, Request
from pymongo import MongoClient
from contextlib import asynccontextmanager
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

async def init_redis(app: FastAPI):
    app.state.redis = Redis(host="localhost", port=6379, decode_responses=True)

    print("REDIS SERVER INITIALIZED")

    asyncio.create_task(pub_robot_pose(app.state.redis))

async def pub_robot_pose(redis: Redis):
    url = DIRECT_WS+"/ws/v2/topics"
    async with websockets.connect(url) as ws:
        try:
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/tracked_pose"]}))

            while True:
                msg = await ws.recv()
                #topic = msg["topic"]

                await redis.publish(
                    "robot:pose", msg
                )

                print(f"TOPIC PUBLISH: [{round(time.time(),1)}]", msg)
            
        except Exception as e:
            print("WebSocket closed:", e)
        finally:
            await ws.close()

async def sub_robot_pose(request: Request):
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
