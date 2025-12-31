"""
Image Storage Manager

Handles downloading, storing, and serving images from ComfyUI.
"""

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .comfyui_client import ComfyUIClient


class ImageStorage:
    """Manages storage and retrieval of generated images"""

    def __init__(self, storage_dir: str = "generated_images"):
        """
        Initialize image storage

        Args:
            storage_dir: Directory to store images (relative to backend folder)
        """
        self.storage_dir = Path(__file__).parent / storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def download_and_store_images(
        self,
        prompt_id: str,
        server_address: str,
        history_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Download images from ComfyUI and store them locally

        Args:
            prompt_id: The prompt ID
            server_address: ComfyUI server address
            history_data: History data from ComfyUI containing outputs

        Returns:
            List of image info with local paths and metadata
        """
        client = ComfyUIClient(server_address=server_address)
        stored_images = []

        outputs = history_data.get('outputs', {})

        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                for img_info in node_output['images']:
                    filename = img_info['filename']
                    subfolder = img_info.get('subfolder', '')
                    img_type = img_info.get('type', 'output')

                    # Generate unique filename
                    file_ext = Path(filename).suffix
                    unique_filename = f"{prompt_id}_{uuid.uuid4().hex[:8]}{file_ext}"
                    local_path = self.storage_dir / unique_filename

                    # Download image
                    try:
                        client.download_image(
                            filename=filename,
                            subfolder=subfolder,
                            image_type=img_type,
                            save_path=local_path
                        )

                        stored_images.append({
                            "filename": unique_filename,
                            "original_filename": filename,
                            "local_path": str(local_path),
                            "node_id": node_id,
                            "prompt_id": prompt_id,
                            "server_address": server_address,
                            "downloaded_at": datetime.utcnow().isoformat()
                        })
                    except Exception as e:
                        print(f"Failed to download {filename}: {e}")

        return stored_images

    def get_image_path(self, filename: str) -> Optional[Path]:
        """
        Get the local path for a stored image

        Args:
            filename: Image filename

        Returns:
            Path to image file or None if not found
        """
        path = self.storage_dir / filename
        if path.exists():
            return path
        return None

    def delete_image(self, filename: str) -> bool:
        """
        Delete a stored image

        Args:
            filename: Image filename

        Returns:
            True if deleted, False if not found
        """
        path = self.storage_dir / filename
        if path.exists():
            path.unlink()
            return True
        return False

    def cleanup_old_images(self, days: int = 7):
        """
        Delete images older than specified days

        Args:
            days: Number of days to keep images
        """
        import time
        current_time = time.time()
        cutoff_time = current_time - (days * 86400)

        for image_path in self.storage_dir.glob("*"):
            if image_path.is_file():
                if image_path.stat().st_mtime < cutoff_time:
                    image_path.unlink()
                    print(f"Deleted old image: {image_path.name}")


# Global storage instance
image_storage = ImageStorage()
