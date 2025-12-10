from fastapi import APIRouter, WebSocket, Request, Body, WebSocketDisconnect
from typing import Dict, Optional
import asyncio
import json
import time
import websockets
import requests
from redis.asyncio import Redis
from database import (
    create_task, 
    update_task_status, 
    get_robot_id_by_sn,
    insert_robot as pg_insert_robot
)
from pymongo import MongoClient

# MongoDB setup
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["robotDB"]
robot_col = db['robots']
poi_col = db['poi']

router = APIRouter(
    prefix='/api/v1/robot/temi'
)

# Store active Temi robot connections
# Key: robot_sn, Value: {"ip": "...", "ws_port": 8080, "last_seen": timestamp}
active_temi_robots: Dict[str, dict] = {}

# ============ STATUS UPDATES FROM ANDROID APP ============

@router.post("/status/update")
async def receive_temi_status(request: Request, payload: dict = Body(...)):
    """
    Android app sends status updates here periodically
    
    Payload example:
    {
        "sn": "R2D2123456",
        "status": {
            "status": "idle",
            "battery": 85,
            "charging": false,
            "location": "kitchen",
            "ready": true
        },
        "type": "temi"
    }
    """
    redis = request.app.state.redis
    
    sn = payload.get("sn")
    status = payload.get("status", {})
    
    if not sn:
        return {"status": 400, "msg": "Missing serial number"}
    
    # Update last seen timestamp
    active_temi_robots[sn] = {
        "last_seen": time.time(),
        "status": status
    }
    
    # Store in Redis for real-time access
    await redis.set(f"temi:{sn}:status", json.dumps(status))
    await redis.set(f"temi:{sn}:battery", status.get("battery", 0))
    await redis.set(f"temi:{sn}:location", status.get("location", "unknown"))
    await redis.set(f"temi:{sn}:last_seen", time.time())
    
    # Publish to WebSocket subscribers
    await redis.publish(f"temi:{sn}:status", json.dumps(status))
    
    print(f"[TEMI] Status update from {sn}: battery={status.get('battery')}%, location={status.get('location')}")
    
    return {"status": 200, "msg": "Status received"}

@router.post("/navigation/update")
async def receive_navigation_status(request: Request, payload: dict = Body(...)):
    """
    Android app sends navigation status updates
    
    Payload:
    {
        "sn": "R2D2123456",
        "location": "kitchen",
        "status": "complete",  # start, going, complete, abort
        "description": "Navigation completed successfully"
    }
    """
    redis = request.app.state.redis
    
    sn = payload.get("sn")
    location = payload.get("location")
    nav_status = payload.get("status")
    description = payload.get("description", "")
    
    print(f"[TEMI] Navigation update {sn}: {location} -> {nav_status}")
    
    # Get current task ID
    task_id_str = await redis.get(f"temi:{sn}:current_task_id")
    
    if task_id_str and nav_status in ["complete", "abort"]:
        task_id = int(task_id_str)
        
        # Update task status in PostgreSQL
        if nav_status == "complete":
            await update_task_status(task_id, "completed")
            await redis.set(f"temi:{sn}:location", location)
            await redis.delete(f"temi:{sn}:current_task_id")
        elif nav_status == "abort":
            await update_task_status(task_id, "failed")
            await redis.delete(f"temi:{sn}:current_task_id")
        
        print(f"[TEMI] Task {task_id} marked as {nav_status}")
    
    # Publish navigation event
    await redis.publish(f"temi:{sn}:navigation", json.dumps(payload))
    
    return {"status": 200, "msg": "Navigation status received"}

# ============ ROBOT CONTROL (WebSocket to Android App) ============

async def send_command_to_temi(robot_ip: str, command: dict, timeout: int = 5) -> dict:
    """
    Send command to Temi Android app via WebSocket
    
    HONEST NOTE: This assumes you know the robot's IP
    You need to maintain IP mapping when robots connect
    """
    ws_url = f"ws://{robot_ip}:8080"
    
    try:
        async with websockets.connect(ws_url, timeout=timeout) as ws:
            # Send command
            await ws.send(json.dumps(command))
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            return json.loads(response)
            
    except asyncio.TimeoutError:
        return {"error": "Temi robot did not respond in time"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/command/goto")
async def temi_goto_location(request: Request, payload: dict = Body(...)):
    """
    Send goto command to Temi robot
    
    Payload:
    {
        "sn": "R2D2123456",
        "location": "kitchen"
    }
    """
    redis = request.app.state.redis
    
    sn = payload.get("sn")
    location = payload.get("location")
    
    if not sn or not location:
        return {"status": 400, "msg": "Missing sn or location"}
    
    # Get robot ID from database
    robot_id = await get_robot_id_by_sn(sn)
    if not robot_id:
        return {"status": 404, "msg": "Robot not registered"}
    
    # Check if robot is online
    if sn not in active_temi_robots:
        return {"status": 503, "msg": "Robot not connected"}
    
    # Get current location from Redis
    current_location = await redis.get(f"temi:{sn}:location") or "unknown"
    
    # Create task in PostgreSQL
    # Note: Temi doesn't have coordinates, so we use 0,0 as placeholders
    task_id = await create_task(
        robot_id=robot_id,
        last_poi=current_location,
        target_poi=location,
        start_x=0.0,
        start_y=0.0,
        target_x=0.0,
        target_y=0.0
    )
    
    # Store task ID in Redis
    await redis.set(f"temi:{sn}:current_task_id", task_id)
    
    # Get robot IP (you need to implement this)
    robot_data = robot_col.find_one({"data.sn": sn})
    if not robot_data:
        return {"status": 404, "msg": "Robot IP not found"}
    
    robot_ip = robot_data["data"]["ip"]
    
    # Send command to Android app
    command = {
        "command": "goto",
        "location": location
    }
    
    result = await send_command_to_temi(robot_ip, command)
    
    if "error" in result:
        await update_task_status(task_id, "failed")
        return {"status": 500, "msg": result["error"]}
    
    return {
        "status": 200,
        "msg": f"Moving to {location}",
        "task_id": task_id,
        "result": result
    }

@router.post("/command/stop")
async def temi_stop_movement(payload: dict = Body(...)):
    """
    Stop Temi robot movement
    """
    sn = payload.get("sn")
    
    if not sn:
        return {"status": 400, "msg": "Missing sn"}
    
    # Get robot IP
    robot_data = robot_col.find_one({"data.sn": sn})
    if not robot_data:
        return {"status": 404, "msg": "Robot not found"}
    
    robot_ip = robot_data["data"]["ip"]
    
    # Send stop command
    command = {"command": "stop"}
    result = await send_command_to_temi(robot_ip, command)
    
    return {"status": 200, "result": result}

@router.post("/command/speak")
async def temi_speak(payload: dict = Body(...)):
    """
    Make Temi robot speak
    """
    sn = payload.get("sn")
    text = payload.get("text")
    
    if not sn or not text:
        return {"status": 400, "msg": "Missing sn or text"}
    
    robot_data = robot_col.find_one({"data.sn": sn})
    if not robot_data:
        return {"status": 404, "msg": "Robot not found"}
    
    robot_ip = robot_data["data"]["ip"]
    
    command = {
        "command": "speak",
        "text": text
    }
    
    result = await send_command_to_temi(robot_ip, command)
    return {"status": 200, "result": result}

# ============ LOCATION MANAGEMENT ============

@router.post("/location/save")
async def temi_save_location(payload: dict = Body(...)):
    """
    Tell Temi to save current location
    """
    sn = payload.get("sn")
    name = payload.get("name")
    
    if not sn or not name:
        return {"status": 400, "msg": "Missing sn or name"}
    
    robot_data = robot_col.find_one({"data.sn": sn})
    if not robot_data:
        return {"status": 404, "msg": "Robot not found"}
    
    robot_ip = robot_data["data"]["ip"]
    
    command = {
        "command": "save_location",
        "name": name
    }
    
    result = await send_command_to_temi(robot_ip, command)
    
    if result.get("success"):
        # Save to MongoDB as well
        poi = {
            "name": name,
            "type": "temi_location",
            "robot_sn": sn,
            "time_created": time.time()
        }
        poi_col.insert_one(poi)
    
    return {"status": 200, "result": result}

@router.get("/location/list")
async def temi_list_locations(sn: str):
    """
    Get list of saved locations from Temi
    """
    robot_data = robot_col.find_one({"data.sn": sn})
    if not robot_data:
        return {"status": 404, "msg": "Robot not found"}
    
    robot_ip = robot_data["data"]["ip"]
    
    command = {"command": "get_locations"}
    result = await send_command_to_temi(robot_ip, command)
    
    return {"status": 200, "locations": result.get("locations", [])}

# ============ WEBSOCKET FOR REAL-TIME STATUS ============

@router.websocket("/ws/status/{sn}")
async def temi_websocket_status(websocket: WebSocket, sn: str):
    """
    WebSocket endpoint for real-time Temi status updates
    """
    await websocket.accept()
    redis = websocket.app.state.redis
    
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"temi:{sn}:status")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        print(f"[TEMI] WebSocket disconnected for {sn}")
    finally:
        await pubsub.close()
        await websocket.close()

# ============ ROBOT REGISTRATION ============

@router.post("/register")
async def temi_register(payload: dict = Body(...)):
    """
    Register a new Temi robot
    
    Payload:
    {
        "name": "Temi-1",
        "nickname": "Reception Robot",
        "sn": "R2D2123456",
        "ip": "192.168.1.100"
    }
    """
    name = payload.get("name")
    nickname = payload.get("nickname")
    sn = payload.get("sn")
    ip = payload.get("ip")
    
    if not all([name, nickname, sn, ip]):
        return {"status": 400, "msg": "Missing required fields"}
    
    # Check if already registered
    if robot_col.find_one({"data.sn": sn}):
        return {"status": 400, "msg": "Robot already registered"}
    
    try:
        # Insert into PostgreSQL
        robot_id = await pg_insert_robot(name, nickname, sn, ip, model="TEMI")
        
        # Insert into MongoDB
        mongo_data = {
            "nickname": nickname,
            "name": name,
            "status": "idle",
            "type": "temi",
            "last_poi": "",
            "data": {
                "sn": sn,
                "ip": ip,
                "time_created": time.time()
            }
        }
        mongo_result = robot_col.insert_one(mongo_data)
        
        return {
            "status": 200,
            "msg": "Temi robot registered successfully",
            "robot_id": robot_id,
            "mongo_id": str(mongo_result.inserted_id)
        }
    
    except Exception as e:
        return {"status": 500, "msg": f"Registration failed: {str(e)}"}

# ============ HEALTH CHECK ============

@router.get("/active")
async def get_active_temi_robots():
    """
    Get list of currently active Temi robots
    """
    now = time.time()
    active = []
    
    for sn, data in active_temi_robots.items():
        # Consider robot active if seen in last 30 seconds
        if now - data["last_seen"] < 30:
            active.append({
                "sn": sn,
                "status": data["status"],
                "last_seen": data["last_seen"]
            })
    
    return {"active_robots": active, "count": len(active)}