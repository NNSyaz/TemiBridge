import asyncpg
from typing import Optional
import math
import asyncio
import datetime

pool: Optional[asyncpg.Pool] = None

async def init_postgres():
    """Initialize connection pool on startup"""
    global pool
    pool = await asyncpg.create_pool(
        host='localhost',
        port='5432',
        user='postgres',
        password='12345678',
        database='robotdb',
        min_size=5,
        max_size=20
    )
        
    print("PostgresSQL connection pool created")

async def close_postgres():
    """Close connection pool on shutdown"""
    global pool
    if pool:
        await pool.close()
        print("PostgreSQL connection pool closed")

def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance"""
    return math.sqrt((x2 - x1)**2 +(y2 - y1)**2)


# =========== ROBOT OPERATIONS ============

async def insert_robot(name: str, nickname: str, sn: str, ip: str, model: str = "AMR"):
    """Insert a new robot into db"""
    async with pool.acquire() as conn:
        robot_id = await conn.fetchval('''
            INSERT INTO robots (name, nickname, sn, ip, model, status, time_created)
            VALUES ($1, $2, $3, $4, $5, 'idle', NOW())
            RETURNING id
        ''', name, nickname, sn, ip, model)
        
        return robot_id
    
async def get_robot_id_by_sn(sn: str) -> Optional[int]:
    """Get robot ID from serial number"""
    async with pool.acquire() as conn:
        robot_id = await conn.fetchval(
            'SELECT id FROM robots WHERE sn = $1', sn
        )

        return robot_id
    
async def update_robot_status(robot_id: int, status: str, last_poi: str = None):
    """Update robot status and last POI"""
    async with pool.acquire() as conn:
        if last_poi:
            await conn.execute('''
                UPDATE robot SET status = $1, last_poi = $2 WHERE id = $3
            ''', status, last_poi, robot_id)
            
        else:
            await conn.execute('''
                UPDATE robot SET status = $1, WHERE id = $2
            ''', status, robot_id)

# =========== TASK OPERATIONS ============

async def create_task(robot_id: int, last_poi: str, target_poi: str, start_x: float, start_y: float, target_x: float, target_y: float) -> int:
    """Create new task record"""

    distance = calculate_distance(start_x, start_y, target_x, target_y)
    task_id = int(datetime.datetime.now().timestamp() * 1000)
    
    async with pool.acquire() as conn:
        await conn.execute('''
                INSERT INTO tasks_history 
                (task_id, robot_id, last_poi, target_poi, status, distance, start_time, end_time)
                VALUES ($1, $2, $3, $4, 'in_progress', $5, NOW(), NOW())
            ''', task_id, robot_id, last_poi, target_poi, distance)
        
        return task_id
    
async def update_task_status(task_id: int, status: str):
    """Update task status (Complete, Failed, Cancel )"""
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE tasks_history
            SET status = $1, end_time = NOW()
            WHERE task_id = $2
        ''', status, task_id)

async def get_task_history(robot_id: int = None, limit: int = 100):
    """Get task history"""
    async with pool.acquire() as conn:
        if robot_id:
            rows = await conn.fetch('''
                SELECT * FROM tasks_history
                WHERE robot_id = $1
                ORDER BY start_time DESC
                LIMIT $2
            ''', robot_id, limit)
        
        else:
            rows = await conn.fetch('''
                SELECT * FROM tasks_history
                ORDER BY start_time DESC
                LIMIT $1    
            ''', limit)

        return[dict(row) for row in rows]
    
# ============ MOVEMENT TRACKING ============

async def record_position(robot_id: int, x: float, y: float, ori: float, prev_x: float = None, prev_y: float = None):
    """Record robot position with distance calculation"""

    distance = 0.0
    if prev_x is not None and prev_y is not None:
        distance = calculate_distance(prev_x, prev_y, x, y)
    
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO robot_movement (time, robot_id, x, y, ori, distance)
            VALUES (NOW(), $1, $2, $3, $4, $5)
        ''', robot_id, x, y, ori, distance)

async def get_movement_history(robot_id: int, limit: int = 1000):
    """Get movement history"""
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM robot_movement
            WHERE robot_id = $1
            ORDER BY time DESC
            ''', robot_id, limit)
        
        return [dict(row) for row in rows]

async def get_total_distance(robot_id: int, start_date:datetime.datetime = None ):
    """Calculate total distance traveled"""
    async with pool.acquire() as conn:
        if start_date:
            total = await conn.fetchval('''
                SELECT COALESCE(SUM(distance), 0)
                FROM robot_movement
                WHERE robot_id = $1 AND time >= $2
            ''', robot_id, start_date)

        else:
            total = await conn.fetchval('''
                SELECT COALESCE(SUM(distance), 0)
                FROM robot_movement
                WHERE robot_id = $1     
            ''', robot_id)

        return float(total)
    
# ============ ANALYTICS ============

async def get_robot_stats(robot_id: int):
    """Get comprehensive robot statistics"""
    async with pool.acquire() as conn:

        task_stats = await conn.fetchrow('''
            SELECT
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
                AVG(distance) as avg_distance,
                SUM(distance) as total_task_distance
            FROM tasks_history
            WHERE robot_id = $1
        ''', robot_id)

        movement_distance = await conn.fetchval('''
            SELECT COALESCE(SUM(distance), 0)
            FROM robot_movement
            WHERE robot_id = $1
        ''', robot_id)

        return{
            "robot_id": robot_id,
            "total_tasks": task_stats['total_tasks'],
            "completed_tasks": task_stats['completed_tasks'],
            "failed_tasks": task_stats['failed_tasks'],
            "avg_task_distance": float(task_stats['avg_distance'] or 0),
            "total_distance_traveled": float(movement_distance)
        }



