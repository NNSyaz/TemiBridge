from fastapi import FastAPI, WebSocket, APIRouter
from pymongo import MongoClient
from contextlib import asynccontextmanager
import asyncio
import time
import uvicorn
import websockets
import json
import httpx

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
    
@router.get("/set/poi/{name}")
async def set_poi_location(name):
    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/edge/v1/robot/position"
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            coord = data["pos"]
            ori = data['ori']

            poi = {"name" : name, "data" : {"target_x" : coord[0], "target_y" : coord[1], "target_ori" : ori}}
            robot_col.insert_one(poi)

            msg = f"POI named {name} successfully saved! : {poi['data']}"
            return msg
        
        except Exception as e:
            return f"{e}: Error retrieving position"
        
@router.post("/move/poi/{name}")
async def go_to_poi(name):
    header = {
        "Content-Type" : "application/json"
    }

    data = robot_col.find({"name" : name})
    payload = data["data"]

    async with httpx.AsyncClient() as client:
        url = EDGE_URL+"/move/poi"
        r = await client.post(url, headers=header, json=payload)
