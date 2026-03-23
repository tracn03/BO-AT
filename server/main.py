from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import engine, Base
from routers import missions

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BO-AT Mission Planner API",
    description="Backend for the autonomous RC sailboat mission planner",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(missions.router, prefix="/api/missions", tags=["missions"])


@app.get("/api/health")
def health_check():
    return JSONResponse({"status": "ok", "service": "BO-AT Mission Planner API"})