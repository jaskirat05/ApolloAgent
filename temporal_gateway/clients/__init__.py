"""
Client implementations for various services

This package contains dedicated client implementations that we maintain directly
to avoid dependency on external libraries that may become unmaintained.
"""

from temporal_gateway.clients.comfy import ComfyUIClient

__all__ = ['ComfyUIClient']
