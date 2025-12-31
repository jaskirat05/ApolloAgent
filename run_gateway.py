#!/usr/bin/env python
"""
Gateway startup script

Run from project root to start the FastAPI gateway.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "gateway.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
