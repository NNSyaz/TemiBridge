"""
Migration script to sync existing MongoDB robots to PostgreSQL
Run this once to fix your current database state
"""
import asyncio
import asyncpg
from pymongo import MongoClient

async def migrate_robots():
    # Connect to MongoDB
    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["robotDB"]
    robot_col = db['robots']
    
    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(
        host='localhost',
        port='5432',
        user='postgres',
        password='12345678',
        database='robotdb'
    )
    
    try:
        # Get all robots from MongoDB
        mongo_robots = list(robot_col.find())
        print(f"Found {len(mongo_robots)} robots in MongoDB")
        
        for robot in mongo_robots:
            nickname = robot.get('nickname')
            name = robot.get('name')
            sn = robot['data'].get('sn')
            ip = robot['data'].get('ip')
            
            print(f"\nProcessing: {nickname} (SN: {sn})")
            
            # Check if already exists in PostgreSQL
            existing = await pg_conn.fetchval(
                'SELECT id FROM robots WHERE sn = $1', sn
            )
            
            if existing:
                print(f"  ✓ Already exists in PostgreSQL (ID: {existing})")
                continue
            
            # Insert into PostgreSQL
            robot_id = await pg_conn.fetchval('''
                INSERT INTO robots (name, nickname, sn, ip, model, status, time_created)
                VALUES ($1, $2, $3, $4, 'AMR', 'idle', NOW())
                RETURNING id
            ''', name, nickname, sn, ip)
            
            print(f"  ✓ Inserted into PostgreSQL (ID: {robot_id})")
        
        print("\n✅ Migration completed successfully!")
        
        # Show final count
        pg_count = await pg_conn.fetchval('SELECT COUNT(*) FROM robots')
        print(f"PostgreSQL now has {pg_count} robots")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        await pg_conn.close()
        mongo_client.close()

if __name__ == "__main__":
    asyncio.run(migrate_robots())