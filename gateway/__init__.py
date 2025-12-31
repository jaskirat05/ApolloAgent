"""
ComfyUI Gateway

FastAPI-based gateway for managing multiple ComfyUI instances.
"""

from .main import app

__all__ = ['app']
__version__ = '1.0.0'
