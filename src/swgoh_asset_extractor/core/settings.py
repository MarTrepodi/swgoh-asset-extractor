from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import AppSettings

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_DIR = Path.home() / ".swgoh-asset-extractor"
DEFAULT_SETTINGS_FILE = DEFAULT_SETTINGS_DIR / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    path = path or DEFAULT_SETTINGS_FILE
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AppSettings.model_validate(data)
        except Exception:
            logger.warning("Failed to load settings from %s, using defaults", path)
    return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    path = path or DEFAULT_SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        settings.model_dump_json(indent=2),
        encoding="utf-8",
    )
