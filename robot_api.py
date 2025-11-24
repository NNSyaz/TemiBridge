from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, Body
from contextlib import asynccontextmanager
import httpx
import websockets
import uvicorn
import hashlib
import time
import asyncio
import json

router = APIRouter(
    prefix='/edge/v1/robot'
)

#REST URL
BASE_URL = "https://apiglobal.autoxing.com"

#WEBSOCKET URL
WS_URL = "wss://serviceglobal.autoxing.com"

#DIRECT ROBOT URL
DIRECT_URL = "http://192.168.0.250:8090"

#DIRECT ROBOT WEBSOCKET URL
DIRECT_WS = "ws://192.168.0.250:8090"

pose_data = {
    "data" : ""
}

@router.get('/hello')
async def hello():
    return "Hello from edge server"

@router.websocket('/ws/hello')
async def websocket_hello(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Hello from edge server websocket")
    await websocket.close()

@router.get("/get_site")

#---------DIRECT ROBOT ENDPOINTS------------

@router.get("/info")
async def get_robot_info():
    async with httpx.AsyncClient() as client:
        url = DIRECT_URL+"/device/info"
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        print("ROBOT INFO", data)
        return data

@router.get("/set/wifi")
async def setup_wifi(mode: str):
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "mode" : mode,
        "ssid" : "RoboRapid_2.4GHz@unifi",
        "psk" : "1sampai8"
    }
    print("WIFI MODE DATA: ", mode)

    async with httpx.AsyncClient() as client:
        url = DIRECT_URL+"/services/setup_wifi"
        r = await client.post(url, headers=header, json=payload)
        r.raise_for_status()
        data = r.json()

        return data

@router.get("/set_control_mode")
async def set_control_mode(mode: str):
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "control_mode" : mode
    }
    print("CONTROL MODE STRING: ", mode)

    async with httpx.AsyncClient() as client:
            url = DIRECT_URL+"/services/wheel_control/set_control_mode"
            print(url)
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()
            print("SET CONTROL MODE: ", data)

            return data

@router.post('/set/emergency_stop')
async def set_emergency_stop(payload: dict = Body(...)):
    header = {
        "Content-Type": "application/json" 
    }

    print("PAYLOAD DATA: ", payload)

    try:
        async with httpx.AsyncClient() as client:
            url = DIRECT_URL+"/services/wheel_control/set_emergency_stop"
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()

            return data
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
        print(error_msg)
        return error_msg
    except Exception as e:
        return f"Error: {e}"

@router.get('/position')
async def get_pose():
     async with httpx.AsyncClient() as client:
        return pose_data["data"]

@router.post("/move/poi")
async def go_to_poi(payload: dict = Body(...)):
    header = {
        "Content-Type": "application/json" 
    }
    async with httpx.AsyncClient() as client:
            try:
                url = DIRECT_URL+"/chassis/moves"
                print(url)
                r = await client.post(url, headers=header, json=payload)
                r.raise_for_status()
                data = r.json()
                print("MOVE ", data)

                return data
            except Exception as e:
                print(f"Error: {e}")
                return f"Error: {e}"

@router.get("/move")
async def move_robot():
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "target_x" : -1,
        "target_y" : 3,
        "target_ori" : 0,
    }

    async with httpx.AsyncClient() as client:
            url = DIRECT_URL+"/chassis/moves"
            print(url)
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()
            print("MOVE ", data)

            return data

@router.get("/move/charge")
async def move_robot():
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "type" : "charge",
        "charge_retry_count" : 3
    }

    async with httpx.AsyncClient() as client:
            url = DIRECT_URL+"/chassis/moves"
            print(url)
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()
            print("MOVE ", data)

            return data

@router.websocket("/ws/track_pose")
async def track_position(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Connecting to Fielder..")
    try:
        while True:
            await websocket.send_json(pose_data['data'])
            await asyncio.sleep(0.1)
            print(f"mock data: {pose_data['data']['topic']}")
    except Exception as e:
        print("Connection closed: ", str(e))

    #asyncio.create_task(stream_topics())

async def stream_robot_topics():
    ws_url = DIRECT_WS+"/ws/v2/topics"
    print("Websocket URL: ", ws_url)

    async with websockets.connect(ws_url) as ws:
        try:
            #enable important data topics
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/tracked_pose"]}))

            while True:
                msg = await ws.recv()
                pose_data['data'] = json.loads(msg)
                #print("Websocket Message: ", msg)
                #return msg
        except websockets.exceptions.ConnectionClosed:
            print("Websocket Connection Closed")

async def mock_websocket():
    while True:
        pose_data['data'] = round(time.time(),2)
        await asyncio.sleep(0.1)
        #print("Test data",pose_data)

#------------CLOUD ENDPOINTS----------------

async def get_robot_list(token):
    headers = {
        "Content-Type": "application/json",
        "X-Token": f"{token}",
    }

    payload = {
        "pageSize": 0,
        "timestamp": 0,
    }

    async with httpx.AsyncClient() as client:
            url = BASE_URL+"/robot/v1.1/list"
            r = await client.post(url, headers=headers, json= payload)
            r.raise_for_status()
            data = r.json()
            print("LIST OF DATA")
            print(data)

            return data

async def get_robot_status(id, token):
    headers = {
        "Content-Type": "application/json",
        "X-Token": f"{token}",
    }

    async with httpx.AsyncClient() as client:
        url = BASE_URL+f"/robot/v1.1/{id}/state"
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        print("LIST OF ROBOT DATA")
        print(data)

@router.websocket("/ws/connect")
async def websocket_endpoint(websocket: WebSocket, robot_id: str):
    await websocket.accept()
    await websocket.send_text(f"Connecting to robot {robot_id}..")
    asyncio.create_task(connect_fielder())
    await websocket.send_text("Connected to Fielder")
    await websocket.close()

async def connect_fielder():
    auth_data = main_fastapi.get_token()
    robot_id = auth_data['robot_id']
    token = auth_data['token']
    ws_url = WS_URL+f"/robot-control/oversee/{robot_id}"

    async with websockets.connect(ws_url, subprotocols=[token]) as ws:
        print("Connect to Fielder Websocket")

        async def heartbeat():
            while True:
                await ws.send(json.dumps({"reqType": "onHeartBeat"}))
                await asyncio.sleep(5)

        asyncio.create_task(heartbeat())

        try:
            while True:
                msg = await ws.recv()
                print("Websocket Message: ", msg)
        except websockets.exceptions.ConnectionClosed:
            print("Websocket Connection Closed")

@router.get("/get/robot_status")
async def get_robot_status_rest(sn: str, request: Request):
    """
    REST endpoint to get robot status by serial number
    Returns the current status, battery, and location from Redis
    """
    redis = request.app.state.redis
    
    try:
        # Get data from Redis
        battery_raw = await redis.get("robot:battery")
        status = await redis.get("robot:status")
        poi = await redis.get("robot:last_poi")
        
        # Parse battery data if it exists
        battery_percent = 0
        if battery_raw:
            try:
                battery_data = json.loads(battery_raw)
                battery_json = json.loads(battery_data["battery"])
                battery_percent = battery_json.get("percentage", 0) * 100
            except Exception as e:
                print(f"Error parsing battery data: {e}")
                battery_percent = 0
        
        # Default values if Redis data is missing
        if not status:
            status = "offline"
        if not poi:
            poi = "unknown"
        
        # Return in a format compatible with your frontend
        response = {
            "robotStatus": {
                "state": 2 if status in ["active", "online"] else 0,  # 2 = online, 0 = offline
                "power": int(battery_percent),
                "areaName": poi,
                "status": status
            },
            "sn": sn,
            "battery": int(battery_percent),
            "last_poi": poi
        }
        
        print(f"REST Status Response for {sn}: {response}")
        return response
        
    except Exception as e:
        print(f"Error getting robot status for {sn}: {e}")
        # Return offline status on error
        return {
            "robotStatus": {
                "state": 0,
                "power": 0,
                "areaName": "unknown",
                "status": "offline"
            },
            "sn": sn,
            "battery": 0,
            "last_poi": "unknown"
        }

if __name__ == "__main__":
    #generate_sign(APP_ID, APP_SECRET)
    asyncio.run(set_control_mode())
    #pass