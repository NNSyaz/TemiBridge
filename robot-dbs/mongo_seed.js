import { MongoClient } from "mongodb";

async function seedMongo() {
  const client = new MongoClient("mongodb://localhost:27017"); // adjust URL if needed
  await client.connect();

  const db = client.db("robotDB");

  // Drop existing collections
  await db.collection("poi").drop().catch(() => {});
  await db.collection("robots").drop().catch(() => {});

  // Insert POIs
  await db.collection("poi").insertMany([
    { name: "center", data: { target_x: -0.985, target_y: 2.9825, target_ori: -0.02 }, time_created: 1762477544.8 },
    { name: "workstation", data: { target_x: 3.2075, target_y: 2.7925, target_ori: -0.02 }, time_created: 1762477636.8 },
    { name: "research", data: { target_x: 4.5775, target_y: 5.885, target_ori: 3.1 }, time_created: 1762477682.7 },
    { name: "software", data: { target_x: 6.745, target_y: 0.8975, target_ori: 4.7 }, time_created: 1762477731.7 },
    { name: "storage", data: { target_x: 13.5175, target_y: 3.3275, target_ori: 3.15 }, time_created: 1762477792.7 },
    { name: "standby", data: { target_x: -0.0275, target_y: 0.5775, target_ori: 1.57 }, time_created: 1762477938.7 }
  ]);

  // Insert Robots
  await db.collection("robots").insertMany([
    {
      nickname: "Kennon 1",
      name: "Kennon S100",
      data: { sn: "4323432535", ip: "192.168.0.43", time_created: 1763460506.6 }
    },
    {
      nickname: "Fielder 1",
      name: "Fielder Robot",
      status: "idle",
      last_poi: "",
      data: { sn: "2682406203417T7", ip: "192.168.0.47", time_created: 1763966069.2 }
    }
  ]);

  console.log("MongoDB initialization complete!");
  await client.close();
}

seedMongo().catch(console.error);
