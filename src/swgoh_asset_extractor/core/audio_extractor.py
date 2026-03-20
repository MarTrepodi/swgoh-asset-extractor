from __future__ import annotations

import logging
import struct
import zipfile
from pathlib import Path

from .downloader import build_asset_url, download_file

logger = logging.getLogger(__name__)


def extract_wwpkg(wwpkg_path: Path, output_dir: Path) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(str(wwpkg_path), "r") as zf:
            pck_entries = [e for e in zf.namelist() if e.endswith(".pck")]
            if not pck_entries:
                logger.warning("No .pck file found in %s", wwpkg_path)
                return None

            pck_name = pck_entries[0]
            target = output_dir / Path(pck_name).name
            with zf.open(pck_name) as src, open(target, "wb") as dst:
                dst.write(src.read())
            return target
    except Exception as e:
        logger.error("Failed to extract wwpkg %s: %s", wwpkg_path, e)
        return None


def extract_pck(pck_path: Path, output_dir: Path) -> list[str]:
    """Extract WEM audio files from a Wwise PCK (sound package) file.

    The PCK format:
    - Header: magic (4 bytes "AKPK"), header_size (u32 LE), unknown (u32 LE)
    - Language map section
    - Sound bank section
    - Streamed audio section with file entries containing: id, block_size, size, offset, folder_id
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []

    try:
        data = pck_path.read_bytes()
        if len(data) < 16:
            logger.warning("PCK file too small: %s", pck_path)
            return []

        magic = data[:4]
        if magic != b"AKPK":
            logger.warning("Invalid PCK magic in %s: %s", pck_path, magic)
            return []

        pos = 4
        header_size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        # Skip version/flags
        pos += 4

        # Language map
        num_languages = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        for _ in range(num_languages):
            # offset, id, name_length (in wchars)
            _offset = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            _lang_id = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            name_len = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            pos += name_len * 2  # UTF-16 name

        # Sound banks section
        num_sound_banks = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        for _ in range(num_sound_banks):
            # id, block_size, size, offset, folder_id
            pos += 4 * 5

        # Streamed audio section
        if pos + 4 > len(data):
            return exported

        num_streamed = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        for _ in range(num_streamed):
            if pos + 20 > len(data):
                break
            file_id = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            _block_size = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            file_size = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            file_offset = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            _folder_id = struct.unpack_from("<I", data, pos)[0]
            pos += 4

            if file_offset + file_size <= len(data):
                wem_data = data[file_offset : file_offset + file_size]
                out_path = output_dir / f"{file_id}.wem"
                out_path.write_bytes(wem_data)
                exported.append(str(out_path))

    except Exception as e:
        logger.error("Failed to extract PCK %s: %s", pck_path, e)

    return exported


def download_and_extract_audio(
    asset_name: str,
    version: str,
    asset_os_path: str,
    working_dir: Path,
    output_dir: Path,
    progress_callback=None,
) -> list[str]:
    working_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = working_dir / "tmp_audio"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pck_dir = working_dir / "tmp_audio_pck"
    pck_dir.mkdir(parents=True, exist_ok=True)

    # Download .wwpkg
    url = build_asset_url(version, asset_os_path, f"{asset_name}.wwpkg")
    wwpkg_path = tmp_dir / f"{asset_name}.wwpkg"
    download_file(url, wwpkg_path, progress_callback=progress_callback)

    # Extract .pck from .wwpkg
    pck_path = extract_wwpkg(wwpkg_path, pck_dir)
    if pck_path is None:
        return []

    # Extract WEM files from .pck
    return extract_pck(pck_path, output_dir)
