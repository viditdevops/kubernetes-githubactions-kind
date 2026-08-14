"""main.py - App entrypoint. Wires routers together; no business logic lives here."""
from fastapi import FastAPI
import db
from routers import health, items
app = FastAPI(title="DevOps Challenge Completed")
app.include_router(health.router)
app.include_router(items.router)
@app.on_event("startup")
def on_startup():
    db.init_schema()
@app.get("/")
def root():
    return {"service": "fluid-ai-backend", "status": "running"}
