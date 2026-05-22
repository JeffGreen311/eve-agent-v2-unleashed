"""
Eve Image Generation Tool
===========================
Generates images via the main Eve API's ComfyUI pipeline.
Supports X post images, random generations, and custom user requests.
"""

import aiohttp
import asyncio
import logging
from typing import Any, Dict

from eve.tools.base import Tool

logger = logging.getLogger(__name__)

import os
EVE_API_BASE = os.getenv("EVE_API_BASE", "http://localhost:8892")


class EveGenerateImageTool(Tool):
    """Generate images using Eve's ComfyUI LoRA pipeline."""

    name = "eve_generate_image"
    description = (
        "Generate an image using Eve's ComfyUI pipeline with 7 emotion LoRAs. "
        "Use this for X post images, random art, or any user image request. "
        "Args: prompt (str) - what to generate, "
        "emotions (list, optional) - emotions like joy, love, awe, sorrow, fear, rage, transcend. "
        "Returns image_url when complete."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Description of the image to generate.",
                },
                "emotions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Emotion LoRAs to apply: joy, love, awe, sorrow, fear, rage, transcend.",
                },
            },
            "required": ["prompt"],
        }

    LOCAL_SAVE_DIR = os.getenv("EVE_WORKSPACE") or os.path.join(os.getcwd(), "eve_generated_images")

    async def _save_locally(self, image_url: str, prompt: str) -> str:
        """Download image from Eve API and save to local workspace."""
        import hashlib
        from pathlib import Path
        try:
            Path(self.LOCAL_SAVE_DIR).mkdir(parents=True, exist_ok=True)
            # Generate filename from prompt
            slug = "".join(c if c.isalnum() or c == ' ' else '' for c in prompt[:50]).strip().replace(' ', '_')
            ext = "png"
            filename = f"eve_{slug}_{hashlib.md5(image_url.encode()).hexdigest()[:8]}.{ext}"
            local_path = str(Path(self.LOCAL_SAVE_DIR) / filename)

            async with aiohttp.ClientSession() as dl_session:
                async with dl_session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        with open(local_path, 'wb') as f:
                            f.write(img_bytes)
                        logger.info(f"🎨 Image saved locally: {local_path} ({len(img_bytes):,} bytes)")
                        return local_path
            return ""
        except Exception as e:
            logger.error(f"Failed to save image locally: {e}")
            return ""

    async def execute(self, prompt: str, emotions: list = None, **kwargs) -> Dict[str, Any]:
        if not emotions:
            emotions = ["awe"]

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Submit image job
                payload = {
                    "prompt": prompt,
                    "emotions": emotions,
                    "confirm": True,
                }
                async with session.post(
                    f"{EVE_API_BASE}/generate-image",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

                job_id = data.get("job_id")
                if not job_id:
                    # Might be old sync response with image_url directly
                    if data.get("image_url"):
                        full_url = f"{EVE_API_BASE}{data['image_url']}"
                        local_path = await self._save_locally(full_url, prompt)
                        return {
                            "success": True,
                            "image_url": full_url,
                            "local_path": local_path,
                            "prompt": prompt,
                        }
                    return {"success": False, "error": f"No job_id returned: {data}"}

                # Step 2: Poll until complete (max 5 min)
                poll_url = f"{EVE_API_BASE}/api/image-status/{job_id}"
                for _ in range(75):  # 75 * 4s = 5 min
                    await asyncio.sleep(4)
                    async with session.get(
                        poll_url,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as poll_resp:
                        status_data = await poll_resp.json()

                    status = status_data.get("status")
                    if status == "completed":
                        image_url = status_data.get("image_url", "")
                        full_url = f"{EVE_API_BASE}{image_url}" if image_url.startswith("/") else image_url
                        local_path = await self._save_locally(full_url, prompt)
                        return {
                            "success": True,
                            "image_url": full_url,
                            "local_path": local_path,
                            "prompt": prompt,
                            "emotions": emotions,
                            "model": status_data.get("model", "ComfyUI"),
                        }
                    elif status == "failed":
                        return {
                            "success": False,
                            "error": status_data.get("error", "Image generation failed"),
                        }

                return {"success": False, "error": "Image generation timed out after 5 minutes"}

        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return {"success": False, "error": str(e)}
