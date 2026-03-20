"""Image composition utilities for reconstructing final images from base textures and alpha masks.

SWGOH uses two approaches for transparency:
1. **Sprite-level alphaTexture** — UnityPy handles this automatically via Sprite.image
2. **Separate mask textures** — A base RGB texture paired with a grayscale mask texture.
   The mask's RGB is averaged to grayscale and used to replace the base texture's alpha channel.
   This is how Unity's SpriteHelper.ApplyRGBMask works in the reference project.

Mask textures are typically named with common suffixes/patterns relative to their base texture:
  - base: "foo"      mask: "foo_a"
  - base: "foo"      mask: "foo_alpha"
  - base: "foo"      mask: "foo_mask"
  - base: "foo"      mask: "fooa"  (no separator)

This module provides:
  - apply_rgb_mask(): Core compositing — replaces alpha with mask grayscale
  - find_mask_pairs(): Scans a directory and pairs base textures with their masks
  - compose_directory(): Batch-compose all paired textures in a directory
  - compose_atlas_with_mask(): Compose an atlas texture with its mask before sprite cutting
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Suffixes that identify an image as an alpha mask (order = matching priority)
MASK_SUFFIXES = ("_a", "_alpha", "_mask", "a")

# Regex to strip a mask suffix from the end of a stem to find the base name
_MASK_SUFFIX_PATTERN = re.compile(r"(?:_(?:a|alpha|mask)|a)$", re.IGNORECASE)


def apply_rgb_mask(
    base: Image.Image,
    mask: Image.Image,
    resample: int = Image.Resampling.BICUBIC,
) -> Image.Image:
    """Apply an RGB mask to a base texture, replacing the alpha channel.

    The mask's RGB channels are averaged to produce a grayscale value (0-255)
    which becomes the alpha channel of the base texture. This replicates the
    ApplyRGBMask logic from AssetStudio's SpriteHelper.cs.

    Args:
        base: The base RGB/RGBA texture.
        mask: The mask texture (RGB channels are averaged to grayscale for alpha).
        resample: Resampling filter if mask needs resizing (default: BICUBIC).

    Returns:
        A new RGBA image with the mask applied as the alpha channel.
    """
    # Ensure base is RGBA
    base_rgba = base.convert("RGBA")

    # Resize mask to match base if needed
    if mask.size != base_rgba.size:
        mask = mask.resize(base_rgba.size, resample)

    # Convert mask to RGB to access channels
    mask_rgb = mask.convert("RGB")

    # Average RGB channels to grayscale for alpha
    r, g, b = mask_rgb.split()

    # Use numpy if available for performance, otherwise pixel-by-pixel
    try:
        import numpy as np

        r_arr = np.array(r, dtype=np.uint16)
        g_arr = np.array(g, dtype=np.uint16)
        b_arr = np.array(b, dtype=np.uint16)
        alpha_arr = ((r_arr + g_arr + b_arr) // 3).astype(np.uint8)
        alpha_channel = Image.fromarray(alpha_arr, mode="L")
    except ImportError:
        # Fallback: use Pillow's built-in blend
        # Convert to grayscale via ITU-R 601-2 luma, then use as approximation
        # For exact match: (R+G+B)/3
        alpha_channel = Image.merge("RGB", (r, g, b)).convert("L")
        # The .convert("L") uses weighted average (0.299R + 0.587G + 0.114B)
        # For exact (R+G+B)/3 without numpy, do pixel-by-pixel:
        pixels_r = r.load()
        pixels_g = g.load()
        pixels_b = b.load()
        alpha_channel = Image.new("L", mask.size)
        alpha_pixels = alpha_channel.load()
        for y in range(mask.size[1]):
            for x in range(mask.size[0]):
                alpha_pixels[x, y] = (pixels_r[x, y] + pixels_g[x, y] + pixels_b[x, y]) // 3

    # Replace alpha channel
    base_r, base_g, base_b, _ = base_rgba.split()
    composed = Image.merge("RGBA", (base_r, base_g, base_b, alpha_channel))

    return composed


def _is_mask_name(stem: str) -> bool:
    """Check if a filename stem looks like a mask texture."""
    lower = stem.lower()
    for suffix in MASK_SUFFIXES:
        if lower.endswith(suffix):
            return True
    return False


def _get_base_name(mask_stem: str) -> str | None:
    """Extract the base texture name from a mask filename stem.

    Examples:
        "tex_atlas_foo_a"     -> "tex_atlas_foo"
        "tex_atlas_foo_alpha" -> "tex_atlas_foo"
        "tex_atlas_foo_mask"  -> "tex_atlas_foo"
        "tex_atlas_fooa"      -> "tex_atlas_foo"
    """
    match = _MASK_SUFFIX_PATTERN.search(mask_stem)
    if match:
        return mask_stem[: match.start()]
    return None


def find_mask_pairs(directory: Path, extensions: set[str] | None = None) -> list[tuple[Path, Path]]:
    """Scan a directory and find (base_texture, mask_texture) pairs.

    Args:
        directory: Directory containing exported texture PNGs.
        extensions: File extensions to consider (default: {".png"}).

    Returns:
        List of (base_path, mask_path) tuples.
    """
    if extensions is None:
        extensions = {".png"}

    # Index all image files by stem
    files_by_stem: dict[str, Path] = {}
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in extensions:
            files_by_stem[f.stem] = f

    pairs = []
    matched_masks = set()

    for stem, path in files_by_stem.items():
        if not _is_mask_name(stem):
            continue

        base_name = _get_base_name(stem)
        if base_name and base_name in files_by_stem:
            base_path = files_by_stem[base_name]
            pairs.append((base_path, path))
            matched_masks.add(stem)
            logger.debug("Paired: %s + %s", base_path.name, path.name)

    return pairs


def compose_image(base_path: Path, mask_path: Path, output_path: Path | None = None) -> Path:
    """Compose a single base texture with its alpha mask.

    Args:
        base_path: Path to the base RGB texture.
        mask_path: Path to the mask texture.
        output_path: Output path. If None, overwrites the base texture.

    Returns:
        Path to the composed output image.
    """
    if output_path is None:
        output_path = base_path

    base = Image.open(base_path)
    mask = Image.open(mask_path)
    composed = apply_rgb_mask(base, mask)
    composed.save(str(output_path))

    logger.info("Composed: %s + %s -> %s", base_path.name, mask_path.name, output_path.name)
    return output_path


def compose_directory(
    directory: Path,
    output_dir: Path | None = None,
    remove_masks: bool = False,
) -> list[Path]:
    """Find and compose all base+mask pairs in a directory.

    Args:
        directory: Directory containing exported textures.
        output_dir: Output directory for composed images. If None, overwrites base textures.
        remove_masks: If True, delete mask files after compositing.

    Returns:
        List of paths to composed images.
    """
    pairs = find_mask_pairs(directory)
    if not pairs:
        logger.info("No mask pairs found in %s", directory)
        return []

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    composed_paths = []
    for base_path, mask_path in pairs:
        try:
            out = output_dir / base_path.name if output_dir else None
            result = compose_image(base_path, mask_path, out)
            composed_paths.append(result)

            if remove_masks:
                mask_path.unlink(missing_ok=True)
                logger.debug("Removed mask: %s", mask_path.name)

        except Exception as e:
            logger.warning("Failed to compose %s + %s: %s", base_path.name, mask_path.name, e)

    logger.info("Composed %d image pairs in %s", len(composed_paths), directory)
    return composed_paths


def compose_atlas_with_mask(
    atlas_image_path: Path,
    mask_path: Path | None = None,
) -> Image.Image:
    """Load an atlas image and apply its alpha mask if found.

    If mask_path is not provided, attempts to find it by naming convention.

    Args:
        atlas_image_path: Path to the atlas base texture.
        mask_path: Explicit path to the mask. If None, auto-detected.

    Returns:
        The composed RGBA image (or original if no mask found).
    """
    base = Image.open(atlas_image_path)

    # Auto-detect mask if not provided
    if mask_path is None:
        parent = atlas_image_path.parent
        stem = atlas_image_path.stem
        ext = atlas_image_path.suffix

        for suffix in MASK_SUFFIXES:
            candidate = parent / f"{stem}{suffix}{ext}"
            if candidate.exists():
                mask_path = candidate
                break

    if mask_path and mask_path.exists():
        mask = Image.open(mask_path)
        return apply_rgb_mask(base, mask)

    return base.convert("RGBA")
