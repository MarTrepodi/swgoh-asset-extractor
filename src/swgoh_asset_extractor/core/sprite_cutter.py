from __future__ import annotations

import io
import logging
import struct
from pathlib import Path

from PIL import Image

from .models import Atlas, SpriteItem

logger = logging.getLogger(__name__)


def _align4(stream: io.BytesIO) -> None:
    pos = stream.tell()
    mod = pos % 4
    if mod != 0:
        stream.seek(pos + (4 - mod))


def _read_int32(stream: io.BytesIO) -> int:
    return struct.unpack("<i", stream.read(4))[0]


def _read_int64(stream: io.BytesIO) -> int:
    return struct.unpack("<q", stream.read(8))[0]


def _read_bool(stream: io.BytesIO) -> bool:
    return struct.unpack("<?", stream.read(1))[0]


def _read_string(stream: io.BytesIO) -> str:
    length = _read_int32(stream)
    data = stream.read(length)
    _align4(stream)
    return data.decode("utf-8")


def parse_atlas(data: bytes) -> Atlas:
    stream = io.BytesIO(data)

    # PPtr<GameObject>
    _read_int32(stream)  # fileID
    _read_int64(stream)  # pathID

    # m_Enabled
    _read_bool(stream)
    _align4(stream)

    # PPtr<Script>
    _read_int32(stream)  # fileID
    _read_int64(stream)  # pathID

    # m_Name
    atlas_name = _read_string(stream)
    atlas = Atlas(name=atlas_name)

    # PPtr<Material>
    _read_int32(stream)  # fileID
    _read_int64(stream)  # pathID

    # Sprite count
    count = _read_int32(stream)

    for _ in range(count):
        sprite = SpriteItem()
        sprite.name = _read_string(stream)
        sprite.x = _read_int32(stream)
        sprite.y = _read_int32(stream)
        sprite.width = _read_int32(stream)
        sprite.height = _read_int32(stream)
        sprite.border_left = _read_int32(stream)
        sprite.border_right = _read_int32(stream)
        sprite.border_top = _read_int32(stream)
        sprite.border_bottom = _read_int32(stream)
        sprite.padding_left = _read_int32(stream)
        sprite.padding_right = _read_int32(stream)
        sprite.padding_top = _read_int32(stream)
        sprite.padding_bottom = _read_int32(stream)
        sprite.mirror_horizontal = _read_bool(stream)
        _align4(stream)
        sprite.mirror_vertical = _read_bool(stream)
        _align4(stream)
        sprite.mirror_rotate = _read_bool(stream)
        _align4(stream)

        atlas.sprites.append(sprite)

    return atlas


def _fix_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name


def cut_sprites(
    atlas: Atlas,
    export_path: Path,
    apply_masks: bool = True,
) -> list[str]:
    """Cut individual sprites from an atlas image.

    Args:
        atlas: Parsed Atlas with sprite coordinates.
        export_path: Directory containing the atlas PNG (and optional mask).
        apply_masks: If True, compose with alpha mask before cutting sprites.

    Returns:
        List of exported sprite file paths.
    """
    atlas_image_path = export_path / f"{atlas.name}.png"
    if not atlas_image_path.exists():
        logger.warning("Atlas image not found: %s", atlas_image_path)
        return []

    sprites_dir = export_path / "sprites" / atlas.name
    sprites_dir.mkdir(parents=True, exist_ok=True)

    # Load atlas image, optionally composing with its alpha mask
    if apply_masks:
        from .image_composer import compose_atlas_with_mask

        img = compose_atlas_with_mask(atlas_image_path)
    else:
        img = Image.open(atlas_image_path).convert("RGBA")

    exported = []

    for sprite in atlas.sprites:
        try:
            cropped = img.crop((
                sprite.x,
                sprite.y,
                sprite.x + sprite.width,
                sprite.y + sprite.height,
            ))
            filename = _fix_filename(sprite.name)
            out_path = sprites_dir / f"{filename}.png"
            cropped.save(str(out_path))
            exported.append(str(out_path))
        except Exception as e:
            logger.warning("Failed to cut sprite '%s': %s", sprite.name, e)

    return exported
