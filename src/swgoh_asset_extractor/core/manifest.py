from __future__ import annotations

import logging
from pathlib import Path

from .downloader import build_asset_url, download_file
from .models import (
    AssetOS,
    DiffType,
    Manifest,
    ManifestEntry,
    ManifestRecord,
)

logger = logging.getLogger(__name__)

# We parse the protobuf manually since we don't want to require protoc compilation.
# The manifest.data uses standard proto3 wire format.

# Wire types
VARINT = 0
FIXED64 = 1
LENGTH_DELIMITED = 2
FIXED32 = 5


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, pos


def _read_length_delimited(data: bytes, pos: int) -> tuple[bytes, int]:
    length, pos = _read_varint(data, pos)
    return data[pos : pos + length], pos + length


def _skip_field(data: bytes, pos: int, wire_type: int) -> int:
    if wire_type == VARINT:
        _, pos = _read_varint(data, pos)
    elif wire_type == FIXED64:
        pos += 8
    elif wire_type == LENGTH_DELIMITED:
        length, pos = _read_varint(data, pos)
        pos += length
    elif wire_type == FIXED32:
        pos += 4
    return pos


def _parse_entry(data: bytes) -> ManifestEntry:
    entry = ManifestEntry()
    pos = 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 1 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            entry.asset_name = val.decode("utf-8")
        elif field_number == 2 and wire_type == VARINT:
            entry.runtime_size, pos = _read_varint(data, pos)
        elif field_number == 3 and wire_type == VARINT:
            entry.clone_runtime_size, pos = _read_varint(data, pos)
        else:
            pos = _skip_field(data, pos, wire_type)
    return entry


def _parse_record(data: bytes) -> ManifestRecord:
    record = ManifestRecord()
    pos = 0
    entries = []
    deps = []
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 1 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            record.name = val.decode("utf-8")
        elif field_number == 2 and wire_type == VARINT:
            record.version, pos = _read_varint(data, pos)
        elif field_number == 3 and wire_type == VARINT:
            val, pos = _read_varint(data, pos)
            record.size = val
        elif field_number == 4 and wire_type == VARINT:
            val, pos = _read_varint(data, pos)
            record.uncompressed_size = val
        elif field_number == 5 and wire_type == VARINT:
            val, pos = _read_varint(data, pos)
            record.shared = bool(val)
        elif field_number == 6 and wire_type == VARINT:
            val, pos = _read_varint(data, pos)
            record.rank = val
        elif field_number == 7 and wire_type == VARINT:
            val, pos = _read_varint(data, pos)
            record.package_type = val
        elif field_number == 8 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            entries.append(_parse_entry(val))
        elif field_number == 9 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            deps.append(val.decode("utf-8"))
        elif field_number == 10 and wire_type == VARINT:
            record.crc, pos = _read_varint(data, pos)
        else:
            pos = _skip_field(data, pos, wire_type)
    record.entries = entries
    record.dependencies = deps
    return record


def parse_manifest(data: bytes) -> Manifest:
    manifest = Manifest()
    pos = 0
    records = []
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 1 and wire_type == VARINT:
            manifest.version, pos = _read_varint(data, pos)
        elif field_number == 2 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            records.append(_parse_record(val))
        elif field_number == 3 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            manifest.platform = val.decode("utf-8")
        elif field_number == 4 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            manifest.tex_format = val.decode("utf-8")
        elif field_number == 5 and wire_type == LENGTH_DELIMITED:
            val, pos = _read_length_delimited(data, pos)
            manifest.environment = val.decode("utf-8")
        elif field_number == 6 and wire_type == VARINT:
            manifest.timestamp, pos = _read_varint(data, pos)
        elif field_number == 7 and wire_type == VARINT:
            manifest.revision, pos = _read_varint(data, pos)
        else:
            pos = _skip_field(data, pos, wire_type)
    manifest.records = records
    return manifest


def parse_manifest_file(path: Path) -> Manifest:
    data = path.read_bytes()
    return parse_manifest(data)


def download_manifest(
    version: str,
    asset_os: AssetOS,
    working_dir: Path,
    progress_callback=None,
) -> Path:
    working_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = working_dir / "Manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    target_path = manifest_dir / f"{version}_manifest.data"
    url = build_asset_url(version, asset_os.url_path, "manifest.data")

    logger.info("Downloading manifest for version %s from %s", version, url)
    download_file(url, target_path, progress_callback=progress_callback)
    return target_path


def diff_manifests(
    old_manifest: Manifest,
    new_manifest: Manifest,
    diff_type: DiffType = DiffType.ALL,
) -> list[str]:
    old_bundles = {r.name: r for r in old_manifest.bundle_records}
    new_bundles = {r.name: r for r in new_manifest.bundle_records}

    result = []

    if diff_type in (DiffType.NEW, DiffType.ALL):
        for name in new_bundles:
            if name not in old_bundles:
                result.append(name)

    if diff_type in (DiffType.CHANGED, DiffType.ALL):
        for name, new_record in new_bundles.items():
            if name in old_bundles:
                old_record = old_bundles[name]
                if old_record.version != new_record.version or old_record.crc != new_record.crc:
                    result.append(name)

    return sorted(set(result))
