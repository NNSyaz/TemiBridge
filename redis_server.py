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
from database import record_position, get_robot_id_by_sn, update_task_status

#Robot IP
IP = "192.168.0.250"

#REST URL
BASE_URL = "https://apiglobal.autoxing.com"

#WEBSOCKET URL
WS_URL = "wss://serviceglobal.autoxing.com"

#DIRECT ROBOT URL
DIRECT_URL = f"http://{IP}:8090"

#DIRECT ROBOT WEBSOCKET URL
DIRECT_WS = f"ws://{IP}:8090"

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
    r = Redis(host="localhost", port=6379, decode_responses=True)
    app.state.redis = r
    #ts = app.state.redis.ts()

    print("REDIS SERVER INITIALIZED")

    #await start_redis_status(app.state.redis)
    asyncio.create_task(pub_robot_status(app.state.redis))
    asyncio.create_task(pub_lidar_points(app.state.redis))
    asyncio.create_task(monitor_planning_state(app.state.redis))

async def pub_robot_status(redis: Redis):
    compile_list = {}
    prev_pose = None
    robot_id = None

    await redis.publish("robot:status", json.dumps({
    "status": "online",
    "battery": 100,
    "last_poi": "center"
}))

    robot_id = await get_robot_id_by_sn("2682406203417T7")

    url = DIRECT_WS+"/ws/v2/topics"
    async with websockets.connect(url) as ws:
        try:
            await start_redis_status(redis, True)
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/battery_state"]}))

            print("REDIS STATE PUBLISH STARTED")

            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                topic = data.get("topic")
                if topic == "/battery_state":
                    compile_list.update({"battery":msg})
                    data_json = json.dumps(compile_list)

                    await redis.set("robot:battery", data_json)
                
                    await redis.publish("robot:status", data_json)

                elif topic == "/tracked_pose" and robot_id:
                    pose_data = data.get("pos", [])
                    ori_data = data.get("ori", 0)

                    if len(pose_data) >= 2:
                        x, y = float(pose_data[0]), float(pose_data[1])

                        await record_position(
                            robot_id=robot_id,
                            x=x,
                            y=y,
                            ori=float(ori_data),
                            prev_x=prev_pose[0] if prev_pose else None,
                            prev_y=prev_pose[1] if prev_pose else None
                        )

                        prev_pose = (x, y)
                        compile_list.update({"pose": msg})
                        await redis.publish("robot:pose", json.dumps(compile_list))

                    
        except Exception as e:
            print("WebSocket closed:", e)
            compile_list.update({"status": 'offline'})
            data_json = json.dumps(compile_list)

            await redis.publish("robot:status", data_json)
            await start_redis_status(redis, False)
        finally:
            await ws.close()

async def monitor_planning_state(redis: Redis):

    url = DIRECT_WS + "ws/v2/topics"

    async with websockets.connect(url) as ws:
        try:
            await ws.send(json.dumps({"enable_topic":["/planning_state"]}))
            print("Subcribed to /planning_state")

            while True:
                msg = ws.recv()
                data = json.loads(msg)

                if data.get("topic") == "/planning_state":
                    await handle_planning_state(redis, data)

        except Exception as e:
            print(f"Planning state monitor error: {e}")
        finally:
            await ws.close

async def handle_planning_state(redis: Redis, data: dict):
    """
    Process planning state updates and update task status
    
    move_state values:
    - "moving": Task in progress
    - "succeeded": Task completed successfully
    - "failed": Task failed
    - "cancelled": Task was cancelled
    """

    move_state = data.get("move_state")
    action_id = data.get("action_id")
    fail_reason = data.get("fail_reason_str", "none")
    remaining_distance = data.get("remaining_distance", 0.0)

    print(f" Planning_state {move_state} | Action: {action_id} | Distance:{remaining_distance}m")

    #Store current planning state in Redis
    await redis.set("robot:planning_state", json.dumps(data))

    # Get current task ID from Redis
    current_task_id = redis.get("robot:current_task_id")

    if not current_task_id:
        print("No active task ID found")
        return

    current_task_id = int(current_task_id)

    #Update robot status based on move_state
    if move_state == "moving":
        await redis.set("robot:status", "active")
        await redis.set("robot:state", "moving")
        print(f"Task {current_task_id} in progress ({remaining_distance:.2f})m remaining")
        
    elif move_state == "succeeded":
        await redis.set("robot:status", "idle")
        await redis.set("robot:state", "idle")

        #Update task status in PostgreSQL
        await update_task_status(current_task_id, "completed")

        print(f"Task {current_task_id} complete successfully")

        # Publish completion event
        await redis.publish("robot:task_completed", json.dumps({
            "task_id": current_task_id,
            "status": "completed",
            "timestamp": time.time()
        }))

    elif move_state == "failed":
        await redis.set("robot:status", "error")
        await redis.set("robot:state", "failed")

        #Update fail task status progress in postgresql
        await update_task_status(current_task_id, "failed", fail_reason)

        await redis.delete("robot:current_task_id")

        print(f"Task {current_task_id} failed: {fail_reason}")

        await redis.publish("robot:task_failed", json.dumps({
            "task_id": current_task_id,
            "status": "failed",
            "reason": fail_reason,
            "timestamp": time.time()
        }))

    elif move_state == "cancelled":
        await redis.set("robot:status", "idle"),
        await redis.set("robot:state", "cancelled")

        #Update task status in the postgresql
        await update_task_status(current_task_id, "cancelled")

        #Clear current task
        await redis.delete("robot:current_task_id")

        print(f"Task {current_task_id} cancelled")

        await redis.publish("robot:task_cancelled", json.dumps({
            "task_id": current_task_id,
            "status": "cancelled",
            "timestamp": time.time()
        })) 

async def pub_lidar_points(redis: Redis):
    """Publishes lidar point cloud data"""
    url = DIRECT_WS + "/ws/v2/topics"

    async with websockets.connect(url) as ws:
        try:
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable":["/scan_matched_points2"]}))

            while True:
                msg = await ws.recv()
                await redis.publish("robot:lidar", msg)

        except Exception as e:
            print(e)

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
        await websockets.close()
        await pubsub.close()
        print("Subscriber closed")
 

async def start_redis_status(redis: Redis, stat: bool):
    print("ROBOT REDIS BOOL STATUS: ",stat)
    if stat:
        status = {
            "status": "online",
            "poi": "origin"
        }
    else:
        status = {
            "status": "offline",
            "poi": "origin"
        }

    await redis.set("robot:status", status["status"])
    await redis.set("robot:last_poi", status["poi"])