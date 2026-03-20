"""Background worker threads for long-running operations.

Each worker subclasses QThread directly and overrides run().
Signals use only simple types (str, int) — never complex Python objects —
to avoid PySide6 cross-thread marshalling issues.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..core.downloader import build_asset_url, download_file
from ..core.extractor import extract_bundle
from ..core.manifest import download_manifest, parse_manifest_file, diff_manifests
from ..core.audio_extractor import download_and_extract_audio
from ..core.models import AssetOS, DiffType, ExportOptions


# ---------------------------------------------------------------------------
# Throttled progress helper
# ---------------------------------------------------------------------------
class _ProgressThrottle:
    """Emit at most once per *interval* seconds (always emits the final call)."""

    def __init__(self, signal: Signal, interval: float = 0.15):
        self._signal = signal
        self._interval = interval
        self._last: float = 0.0

    def __call__(self, current: int, total: int) -> None:
        now = time.monotonic()
        if now - self._last >= self._interval or current >= total:
            self._signal.emit(current, total)
            self._last = now


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class ManifestDownloadThread(QThread):
    """Downloads a manifest file in the background.

    Emits ``result_ready(str)`` with the file path on success (empty on failure).
    """

    download_progress = Signal(int, int)
    result_ready = Signal(str)          # manifest file path, or ""
    download_error = Signal(str)

    def __init__(
        self,
        version: str,
        asset_os: AssetOS,
        working_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.version = version
        self.asset_os = asset_os
        self.working_dir = working_dir

    def run(self) -> None:
        try:
            throttled = _ProgressThrottle(self.download_progress)
            path = download_manifest(
                self.version,
                self.asset_os,
                self.working_dir,
                progress_callback=throttled,
            )
            self.result_ready.emit(str(path))
        except Exception as e:
            self.download_error.emit(str(e))
            self.result_ready.emit("")


class AssetExtractionThread(QThread):
    """Downloads and extracts asset bundles in the background."""

    extraction_progress = Signal(int, int)       # current_asset, total_assets
    object_progress = Signal(int, int)            # current_object, total_objects
    status_update = Signal(str)
    extraction_done = Signal(int, int)            # success_count, error_count
    extraction_error = Signal(str)

    def __init__(
        self,
        asset_names: list[str],
        version: str,
        asset_os: AssetOS,
        working_dir: Path,
        output_dir: Path,
        options: ExportOptions,
        parent=None,
    ):
        super().__init__(parent)
        self.asset_names = asset_names
        self.version = version
        self.asset_os = asset_os
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.options = options
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total_success = 0
        total_errors = 0
        total = len(self.asset_names)

        tmp_dir = self.working_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        obj_throttle = _ProgressThrottle(self.object_progress)

        for i, name in enumerate(self.asset_names):
            if self._cancelled:
                break

            self.status_update.emit(f"Extracting {name} ({i + 1}/{total})")
            self.extraction_progress.emit(i + 1, total)

            try:
                url = build_asset_url(
                    self.version, self.asset_os.url_path, f"{name}.bundle",
                )
                bundle_path = tmp_dir / f"{name}.bundle"
                download_file(url, bundle_path)

                prefix = name.split("_")[0] if "_" in name else name
                asset_output = self.output_dir / prefix

                result = extract_bundle(
                    bundle_path,
                    asset_output,
                    self.options,
                    progress_callback=obj_throttle,
                )
                total_success += result.success_count
                total_errors += result.error_count

                bundle_path.unlink(missing_ok=True)

            except Exception as e:
                total_errors += 1
                self.extraction_error.emit(f"Error extracting {name}: {e}")

        self.extraction_done.emit(total_success, total_errors)


class DiffThread(QThread):
    """Compares two manifest versions in the background."""

    diff_done = Signal(str)     # newline-separated bundle names, or ""
    diff_error = Signal(str)

    def __init__(
        self,
        old_version: str,
        new_version: str,
        asset_os: AssetOS,
        working_dir: Path,
        diff_type: DiffType,
        parent=None,
    ):
        super().__init__(parent)
        self.old_version = old_version
        self.new_version = new_version
        self.asset_os = asset_os
        self.working_dir = working_dir
        self.diff_type = diff_type

    def run(self) -> None:
        try:
            old_path = download_manifest(
                self.old_version, self.asset_os, self.working_dir,
            )
            new_path = download_manifest(
                self.new_version, self.asset_os, self.working_dir,
            )
            old_manifest = parse_manifest_file(old_path)
            new_manifest = parse_manifest_file(new_path)

            names = diff_manifests(old_manifest, new_manifest, self.diff_type)
            self.diff_done.emit("\n".join(names))
        except Exception as e:
            self.diff_error.emit(str(e))
            self.diff_done.emit("")


class AudioExtractionThread(QThread):
    """Downloads and extracts audio packages in the background."""

    audio_progress = Signal(int, int)
    status_update = Signal(str)
    audio_done = Signal(int, int)       # success_count, error_count
    audio_error = Signal(str)

    def __init__(
        self,
        audio_names: list[str],
        version: str,
        asset_os: AssetOS,
        working_dir: Path,
        output_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.audio_names = audio_names
        self.version = version
        self.asset_os = asset_os
        self.working_dir = working_dir
        self.output_dir = output_dir
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total_success = 0
        total_errors = 0
        total = len(self.audio_names)

        for i, name in enumerate(self.audio_names):
            if self._cancelled:
                break

            self.status_update.emit(f"Extracting audio {name} ({i + 1}/{total})")
            self.audio_progress.emit(i + 1, total)

            try:
                files = download_and_extract_audio(
                    name,
                    self.version,
                    self.asset_os.url_path,
                    self.working_dir,
                    self.output_dir / "audio",
                )
                total_success += len(files)
            except Exception as e:
                total_errors += 1
                self.audio_error.emit(f"Error extracting audio {name}: {e}")

        self.audio_done.emit(total_success, total_errors)
