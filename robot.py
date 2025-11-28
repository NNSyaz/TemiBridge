from fastapi import FastAPI, WebSocket, APIRouter, Request, WebSocketDisconnect, Body
from pymongo import MongoClient
from contextlib import asynccontextmanager
import asyncio
import time
import uvicorn
import websockets
import json
import httpx
from redis.asyncio import Redis
import minimap_test as map
import  keyboard_input

mongo_client = MongoClient("mongodb://localhost:27017/")

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

db = mongo_client["robotDB"]

robot_col = db['robots']
poi_col = db['poi']
pose_data = {
    "data" : ""
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = MongoClient("mongodb://localhost:27017/")
    print("PRINT REDIS: ", app.state)

    db = mongo_client["robotDB"]

    global robot_col
    robot_col = db['robots']

    #await stream_robot_pose()

router = APIRouter(
    prefix='/api/v1/robot'
)

#Edge server http url
EDGE_URL = "http://192.168.0.138:8000"

#Edge server websocket url
EDGE_WS = "ws://192.168.0.138:8000"

@router.get('/hello')
async def main_hello():
    return "hello"

@router.websocket('/ws/hello')
async def websocket_hello(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Hello from edge server websocket")
    await websocket.close()

@router.get("/get/poi_details")
async def get_poi_list(poi: str):
    poi_list = []

    poi_data = poi_col.find_one({"name" : poi})
    print("POI DATA DETAILS: ", poi_data)

    if poi_data:
        poi_data["_id"] = str(poi_data["_id"])

    return poi_data

@router.get("/get/poi_list")
async def get_poi_list():
    poi_list = []
    print("LIST POI")

    poi_data = poi_col.find()
    print("LIST POI ", poi_data)

    for poi in poi_data:
            poi["_id"] = str(poi["_id"])
            poi_list.append(poi)
            print(poi)

            print("POI DATA: ",poi)
            print("POI LIST: ", poi_list)

    return poi_list

@router.get("/set/poi")
async def set_poi_location(name: str, request: Request):
    #url = EDGE_URL+"/edge/v1/robot/position"
    recv_data = await get_pose(request)
    topic_data = json.loads(recv_data)
    print("TOPIC DATA: ", topic_data["pos"])

    coord = topic_data['pos']
    ori = topic_data['ori']


    poi = {"name" : name, "data" : {"target_x" : coord[0], "target_y" : coord[1], "target_ori" : ori}, "time_created" : round(time.time(),1)}
    poi_col.insert_one(poi)

    msg = f"POI named {name} successfully saved! : {poi['data']}"

    return msg

@router.websocket("/ws/current_pose")
async def websocket_robot_pose(websocket: WebSocket):
    await websocket.accept()

    redis = websocket.app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe("robot:pose")
    print("Subscribed to robot:pose")

    try:
        async for message in pubsub.listen():
            print("REDIS SUB DATA: ",message)
            if message["type"] == "message":
                data = message["data"]
                print("Received robot pose:", data)
                await websocket.send_text(data)
    except WebSocketDisconnect:
        await websocket.close()
        await pubsub.close()
        print("Websocket Disconnected")
    except Exception as e:
        print("Subscriber error:", e)
    finally:
        await websocket.close()
        await pubsub.close()
        print("Subscriber closed")

@router.websocket("/ws/get/robot_status")
async def get_robot_status(websocket: WebSocket):
    redis = websocket.app.state.redis
    compile_status = {}

    await websocket.accept()

    try:
        while True:
            battery_raw = json.loads(await redis.get("robot:battery"))
            status = await redis.get("robot:status")
            poi = await redis.get("robot:last_poi")
            print("BATTERY RAW DATA", battery_raw)
            print("STATUS DATA", status)
            print("poi DATA", poi)

            battery_data = battery_raw["battery"]
            battery_percent = json.loads(battery_data)
            print("BATTERY PERCENT", battery_percent)

            compile_status.update({"status": status, "battery": battery_percent["percentage"]*100, "last_poi": poi})
            await websocket.send_json(compile_status)
            await asyncio.sleep(1)

    except Exception as e:
        print(e)
    finally:
        await websocket.close()

@router.get("/move/poi")
async def go_to_poi(name: str, request: Request):
    redis = request.app.state.redis

    header = {
        "Content-Type" : "application/json"
    }

    data = poi_col.find_one({"name" : name})
    print("DATA: ", data)
    payload = data["data"]

    async with httpx.AsyncClient() as client:
        try:
            url = DIRECT_URL+"/chassis/moves"
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()

            status = "active"
            await redis.set("robot:status", status)
            await redis.set("robot:last_poi", name)

            test = await redis.get("robot:status")
            print("REDIS GET DATA", test)

            return data
        except httpx.ReadTimeout as e:
            print("Error: ",e)
            return e

@router.get("/move/charge")
async def move_charge(request: Request):
    redis = request.app.state.redis
    print("Charging Received")
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "type" : "charge",
        "charge_retry_count" : 3
    }

    async with httpx.AsyncClient() as client:
        try:
            url = DIRECT_URL+"/chassis/moves"
            print("URL: ",url)
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()
            print("MOVE ", data)
            await redis.set("robot:status", "charging")

            return data
        except httpx.ConnectTimeout as e:
            print("Error: ",e)
            return e

@router.get("/move")
async def move_robot():
    print("ROBOT TEST MOVE")
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

@router.get("/test/pose")
async def get_pose(request: Request):
    pubsub = request.app.state.redis.pubsub()
    await pubsub.subscribe("robot:state")
    print("Subscribed to robot:pose")

    try:
        async for message in pubsub.listen():
            print("REDIS SUB DATA: ",message)
            if message["type"] == "message":
                data = message["data"]
                print("Received robot pose:", data)
                return data
    except Exception as e:
        print("Subscriber error:", e)
    finally:
        await pubsub.close()
        print("Subscriber closed")

@router.websocket("/ws/test/pose")
async def sub_robot_pose(websocket: WebSocket):
    await websocket.accept()
    pubsub = websocket.app.state.redis.pubsub()
    await pubsub.subscribe("robot:state")
    print("Subscribed to robot:state")

    try:
        async for message in pubsub.listen():
            print("REDIS SUB DATA: ",message)
            if message["type"] == "message":
                data = message["data"]
                data_json = json.loads(data)
                print("Received robot pose:", data_json)
                await websocket.send_json(data_json)

    except Exception as e:
        print("Subscriber error:", e)
    finally:
        await websocket.close()
        await pubsub.close()
        print("Subscriber closed")

@router.get("/set/control_mode")
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

@router.get("/set/velocity")
async def set_velocity(vel: str):
    header = {
        "Content-Type": "application/json" 
    }
    payload = {
        "/wheel_control/max_forward_velocity": float(vel)
    }
    print("MAX VELOCITY ", vel)

    async with httpx.AsyncClient() as client:
            url = DIRECT_URL+"/robot-params"
            print(url)
            r = await client.post(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()
            print("SET CONTROL MODE: ", data)

            return data

@router.get("/move/cancel")
async def go_to_poi():
    header = {
        "Content-Type" : "application/json"
    }

    payload = {
        "state": "cancelled"
    }

    async with httpx.AsyncClient() as client:
        try:
            url = DIRECT_URL+"/chassis/moves/current"
            r = await client.patch(url, headers=header, json=payload)
            r.raise_for_status()
            data = r.json()

            return data
        except httpx.ReadTimeout as e:
            print("Error: ",e)
            return e

#For Autoxing with jack
@router.get("/jack/up")
async def jack_up():
    header = {
        "Content-Type" : "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            url = DIRECT_URL+"/services/jack_up"
            r = await client.post(url, headers=header)
            r.raise_for_status()
            data = r.json()

            return data
        except httpx.ReadTimeout as e:
            print("Error: ",e)
            return e

 #For Autoxing with jack       

@router.get("/jack/down")
async def jack_down():
    header = {
        "Content-Type" : "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            url = DIRECT_URL+"/services/jack_down"
            r = await client.post(url, headers=header)
            r.raise_for_status()
            data = r.json()

            return data
        except httpx.ReadTimeout as e:
            print("Error: ",e)
            return e

#------- ROBOT REGISTRATION ----------

@router.post("/register")
async def robot_register(payload: dict = Body(...)):
    name = payload["name"]
    nickname = payload["nickname"]
    sn = payload["sn"]
    ip = payload["ip"]
    status = "idle"
    last_poi = ""
    on_time = round(time.time(),1)
    last_offline = round(time.time(),1)
    time_created = round(time.time(),1)

    info = {"nickname":nickname, "name":name, "status": status, "last_poi": last_poi, "data" : {"sn": sn, "ip": ip, "time_created": time_created}}

    if not robot_col.find_one({"nickname" : nickname}):
        robot_col.insert_one(info)

        return({"status": 200, "msg" : "Successfully Registered!"})
    else:
        return({"status": 400, "msg" : "Robot with the same nickname already exist!"})
    
@router.get("/get/robot_list")
async def robot_register():
    robot_list = []
    print("LIST ROBOT")

    robot_data = robot_col.find()
    print("LIST ROBOT ", robot_data)

    for robot in robot_data:
        robot["_id"] = str(robot["_id"])
        robot_list.append(robot)
        print(robot)

        print("ROBOT DATA: ",robot)
    print("ROBOT LIST: ", robot_list)

    return robot_list

@router.get("/delete/robot_name")
async def delete_robot(name: str):
    print("delete selected")
    if robot_col.find_one({"nickname" : name}):
        robot_col.delete_one({"nickname": name})
        return({"status": 200, "msg" : "Successfully Delete"})
    else:
        return({"status": 404, "msg" : "Robot Don't Exist"})

#------------- DIRECT CONTROL ------------------

@router.get("/test/command_control")
async def control_loop(lin: float, ang: float):
    print("RECEIVED")
    uri = DIRECT_WS+"/ws/v2/topics"
    print("URL: ",uri)
    try:
        async with websockets.connect(uri) as ws:
            # Subscribe to twist feedback
            await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
            await ws.send(json.dumps({"enable_topic": ["/tracked_pose","/battery_state"]}))
            
            # Switch to remote mode (if required)
            # await ws.send(... set_control_mode ...)

            while True:
                # Receive feedback before next command
                feedback = await ws.recv()
                data = json.loads(feedback)
                print(data)

                # Prepare next command
                twist_cmd = {
                    "topic": "/twist",
                    "linear_velocity": lin,
                    "angular_velocity": ang
                }
                await ws.send(json.dumps(twist_cmd))
                await asyncio.sleep(0.1)  # 10Hz update rate
    except Exception as e:
        await ws.close()
        
@router.get("/test/direct_control")
async def control_loop():
    uri = DIRECT_WS+"/ws/v2/topics"
    print("URL: ",uri)
    async with websockets.connect(uri) as ws:
        # Subscribe to twist feedback
        await ws.send(json.dumps({"disable_topic": ["/slam/state"]}))
        await ws.send(json.dumps({"enable_topic": ["/tracked_pose","/battery_state"]}))
        
        # Switch to remote mode (if required)
        # await ws.send(... set_control_mode ...)

        while True:
            # Receive feedback before next command
            feedback = await ws.recv()
            data = json.loads(feedback)
            print(data)

            # Prepare next command
            twist_cmd = {
                "topic": "/twist",
                "linear_velocity": 0,
                "angular_velocity": -0.6
            }
            await ws.send(json.dumps(twist_cmd))
            await asyncio.sleep(0.1)  # 10Hz update rate

@router.websocket("/ws/get/lidar")
async def get_lidar_points(websocket: WebSocket):
    await websocket.accept()
    pubsub = websocket.app.state.redis.pubsub()
    await pubsub.subscribe("robot:lidar")
    print("Subscribed to robot:lidar")

    try:
        async for message in pubsub.listen():
            #print("REDIS SUB DATA: ",message)
            if message["type"] == "message":
                data = json.loads(message["data"])
                #print("Received robot pose:", data)
                await map.realtime_lidar(data["points"])
                #map.realtime_lidar(data["points"])
                await websocket.send_json(data["points"])

    except Exception as e:
        print("Subscriber error:", e)
        await map.close_plot()
    finally:
        await pubsub.close()
        await websocket.close()
        print("Subscriber closed")

#---------------- FUNCTIONS --------------------

async def stream_robot_pose(redis: Redis):
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

                #print("TOPIC PUBLISH: ", msg)
            
        except Exception as e:
            print("WebSocket closed:", e)
        finally:
            ws.close()

