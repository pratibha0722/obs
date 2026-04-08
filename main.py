from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import webbrowser
import threading
import time

from app.routes.overlay import router as overlay_router

app = FastAPI(
    title="OBS Overlay API",
    version="1.0.0",
    description="Controls OBS text overlays and scene switching for conference talks."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(overlay_router)

# Serve UI
app.mount("/ui", StaticFiles(directory="app/static", html=True), name="ui")


# Auto open UI
def open_browser():
    time.sleep(1)
    webbrowser.open("http://localhost:8000/ui")


@app.on_event("startup")
def startup_event():
    threading.Thread(target=open_browser).start()


@app.get("/")
def root():
    return {"message": "API running"}