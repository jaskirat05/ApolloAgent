"""
FastAPI Gateway for ComfyUI

A gateway API that can interact with multiple ComfyUI instances.
Provides endpoints to queue prompts, track progress, and download results.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .api import servers, workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    print("FastAPI Gateway starting...")
    yield
    # Shutdown
    print("FastAPI Gateway shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="ComfyUI Gateway API",
    description="Gateway API for managing multiple ComfyUI instances",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Include routers
app.include_router(servers.router)
app.include_router(workflow.router)
