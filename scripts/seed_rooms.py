import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base 
from app.models.meeting_room import MeetingRoom

INITIAL_ROOMS = [
    {
        "name": "Executive Room",
        "capacity": 10,
        "status": "active",
        "devices": ["Smart TV", "Video Conference", "Whiteboard"]
    },
    {
        "name": "Summit Room",
        "capacity": 15,
        "status": "active",
        "devices": ["Smart TV", "Mic System", "Video Conference", "Whiteboard"]
    },
    {
        "name": "Focus Room",
        "capacity": 5,
        "status": "active",
        "devices": ["TV Screen", "Whiteboard"]
    },
    {
        "name": "Board Room",
        "capacity": 25,
        "status": "active",
        "devices": ["Projector 4K", "Smart TV", "Premium Mic", "Speakers", "Video Conference", "Whiteboard"]
    }
]

def seed_meeting_rooms(db: Session):
    Base.metadata.create_all(bind=engine)

    print("🌱 Seeding meeting rooms into database...")
    
    for room_data in INITIAL_ROOMS:
        existing_room = db.query(MeetingRoom).filter(MeetingRoom.name == room_data["name"]).first()
        
        if not existing_room:
            new_room = MeetingRoom(
                name=room_data["name"],
                capacity=room_data["capacity"],
                status=room_data["status"],
                devices=room_data["devices"]
            )
            db.add(new_room)
            print(f" Added room: {room_data['name']}")
        else:
            print(f" Room already exists: {room_data['name']}")
            
    db.commit()
    print(" Meeting rooms seeding completed successfully!")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_meeting_rooms(db)
    finally:
        db.close()
