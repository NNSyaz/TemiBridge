from fastapi import FastAPI, WebSocket, APIRouter
from pymongo import MongoClient
from contextlib import asynccontextmanager
import asyncio
import time
import uvicorn
import websockets
import json
import httpx

mongo_client = MongoClient("mongodb://localhost:27017/")

db = mongo_client["robotDB"]

robot_col = db['robots']
poi_col = db['poi']

@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = MongoClient("mongodb://localhost:27017/")

    db = mongo_client["robotDB"]

    global robot_col
    robot_col = db['robots']

router = APIRouter(
    prefix='/api/v1/robot'
)

#Edge server http url
EDGE_URL = "http://192.168.0.137:8000"

#Edge server websocket url
EDGE_WS = "ws://192.168.0.137:8000"

@router.get('/edge/hello')
async def main_hello():
    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/hello"
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        return data
    
@router.get("/get/poi_list")
async def get_poi_list():
    poi_list = []

    poi_data = poi_col.find()
    for poi in poi_data:
        poi["_id"] = str(poi["_id"])
        poi_list.append(poi)

    print(poi_list)

    return poi_list
    
@router.get("/set/poi")
async def set_poi_location(name: str):
    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/edge/v1/robot/position"
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            coord = data["pos"]
            ori = data['ori']

            poi = {"name" : name, "data" : {"target_x" : coord[0], "target_y" : coord[1], "target_ori" : ori}, "time_created" : round(time.time(),1)}
            poi_col.insert_one(poi)

            msg = f"POI named {name} successfully saved! : {poi['data']}"
            return msg
        
        except Exception as e:
            return f"{e}: Error retrieving position"
        
@router.get("/move/charge")
async def go_to_charge():
    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/edge/v1/robot/move/charge"
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

        return
        
@router.get("/move/poi")
async def go_to_poi(name: str):
    header = {
        "Content-Type" : "application/json"
    }

    data = poi_col.find_one({"name" : name})
    print("DATA: ", data)
    payload = data["data"]

    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/edge/v1/robot/move/poi"
        r = await client.post(url, headers=header, json=payload)
        r.raise_for_status()
        data = r.json()

        return data
