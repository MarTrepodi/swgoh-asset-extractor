from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://eaassets-a.akamaihd.net/assetssw.capitalgames.com/PROD"
CHUNK_SIZE = 65536


def build_asset_url(version: str, os_path: str, filename: str) -> str:
    return f"{BASE_URL}/{version}{os_path}{filename}"


def download_file(
    url: str,
    target_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    timeout: float = 300.0,
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(target_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(downloaded, total)

    logger.info("Downloaded %s -> %s", url, target_path)
    return target_path
