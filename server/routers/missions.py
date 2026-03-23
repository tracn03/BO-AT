from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models import Mission, Waypoint
from waypoint_handler import generate_waypoints_file

router = APIRouter()

class WaypointIn(BaseModel):
    latitude: float
    longitude: float
    altitude: float = 0.0
    command: int = 16          # MAV_CMD_NAV_WAYPOINT
    frame: int = 3             # MAV_FRAME_GLOBAL_RELATIVE_ALT
    param1: float = 0.0
    param2: float = 2.0
    param3: float = 0.0
    param4: float = 0.0
    autocontinue: int = 1


class WaypointOut(WaypointIn):
    id: int
    sequence: int

    class Config:
        from_attributes = True


class MissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    waypoints: List[WaypointIn]


class MissionOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    waypoints: List[WaypointOut]

    class Config:
        from_attributes = True


class MissionSummary(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    waypoint_count: int

    class Config:
        from_attributes = True


# Routes

@router.post("/", response_model=MissionOut, status_code=201)
def create_mission(payload: MissionCreate, db: Session = Depends(get_db)):
    """
    Save a new mission with its waypoints to the database.
    The first waypoint is treated as home; all others are mission waypoints.
    """
    if not payload.waypoints:
        raise HTTPException(status_code=422, detail="A mission must have at least one waypoint.")

    mission = Mission(name=payload.name, description=payload.description)
    db.add(mission)
    db.flush()  # Get the mission.id before inserting waypoints

    for i, wp_data in enumerate(payload.waypoints):
        wp = Waypoint(
            mission_id=mission.id,
            sequence=i,
            **wp_data.model_dump(),
        )
        db.add(wp)

    db.commit()
    db.refresh(mission)
    return mission


@router.get("/", response_model=List[MissionSummary])
def list_missions(db: Session = Depends(get_db)):
    """Return all saved missions (without full waypoint detail)."""
    missions = db.query(Mission).order_by(Mission.created_at.desc()).all()
    return [
        MissionSummary(
            id=m.id,
            name=m.name,
            description=m.description,
            created_at=m.created_at,
            waypoint_count=len(m.waypoints),
        )
        for m in missions
    ]


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(mission_id: int, db: Session = Depends(get_db)):
    """Return a single mission with all waypoint details."""
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")
    return mission


@router.delete("/{mission_id}", status_code=204)
def delete_mission(mission_id: int, db: Session = Depends(get_db)):
    """Delete a mission and all its waypoints."""
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")
    db.delete(mission)
    db.commit()


@router.get("/{mission_id}/export", response_class=PlainTextResponse)
def export_mission_waypoints(mission_id: int, db: Session = Depends(get_db)):
    """
    Export the mission as a QGC WPL 110 .waypoints file.
    This file can be loaded directly into Mission Planner.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")
    if not mission.waypoints:
        raise HTTPException(status_code=422, detail="Mission has no waypoints to export.")

    file_content = generate_waypoints_file(sorted(mission.waypoints, key=lambda w: w.sequence))
    filename = mission.name.replace(" ", "_").lower()

    return PlainTextResponse(
        content=file_content,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.waypoints"',
        },
    )