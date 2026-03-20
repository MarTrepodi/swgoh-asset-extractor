from __future__ import annotations

import logging
from pathlib import Path

import UnityPy
from UnityPy.enums import ClassIDType

from .models import ExportOptions, ExtractionResult

logger = logging.getLogger(__name__)


def load_bundle(bundle_path: Path) -> UnityPy.Environment:
    return UnityPy.load(str(bundle_path))


def _fix_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    if len(name) >= 260:
        import uuid
        name = str(uuid.uuid4())
    return name


def _export_texture2d(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"texture_{obj.path_id}")
    out_path = output_dir / f"{name}.png"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}.png"
    try:
        img = data.image
        img.save(str(out_path))
        return str(out_path)
    except Exception as e:
        logger.warning("Failed to export Texture2D '%s': %s", name, e)
        return None


def _export_sprite(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"sprite_{obj.path_id}")
    out_path = output_dir / f"{name}.png"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}.png"
    try:
        img = data.image
        img.save(str(out_path))
        return str(out_path)
    except Exception as e:
        logger.warning("Failed to export Sprite '%s': %s", name, e)
        return None


def _export_audio_clip(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"audio_{obj.path_id}")
    try:
        for sample_name, sample_data in data.samples.items():
            sample_name = _fix_filename(sample_name)
            out_path = output_dir / sample_name
            if out_path.exists():
                out_path = output_dir / f"{obj.path_id}_{sample_name}"
            out_path.write_bytes(sample_data)
            return str(out_path)
    except Exception as e:
        logger.warning("Failed to export AudioClip '%s': %s", name, e)
    return None


def _export_font(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"font_{obj.path_id}")
    font_data = data.m_FontData
    if not font_data:
        return None

    # Detect OTF by magic bytes (OTTO = 0x4F 0x54 0x54 0x4F)
    ext = ".ttf"
    if len(font_data) >= 4 and font_data[:4] == b"OTTO":
        ext = ".otf"

    out_path = output_dir / f"{name}{ext}"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}{ext}"
    out_path.write_bytes(font_data)
    return str(out_path)


def _export_text_asset(obj, output_dir: Path, container: str = "") -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"text_{obj.path_id}")

    ext = ".txt"
    if container:
        from pathlib import PurePosixPath
        container_ext = PurePosixPath(container).suffix
        if container_ext:
            ext = container_ext

    out_path = output_dir / f"{name}{ext}"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}{ext}"

    script = data.m_Script
    if isinstance(script, str):
        script = script.encode("utf-8")
    out_path.write_bytes(script)
    return str(out_path)


def _export_mesh(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"mesh_{obj.path_id}")
    out_path = output_dir / f"{name}.obj"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}.obj"

    try:
        mesh_data = data.export()
        out_path.write_text(mesh_data)
        return str(out_path)
    except Exception as e:
        logger.warning("Failed to export Mesh '%s': %s", name, e)
        return None


def _export_shader(obj, output_dir: Path) -> str | None:
    data = obj.read()
    name = _fix_filename(data.m_Name or f"shader_{obj.path_id}")
    out_path = output_dir / f"{name}.shader"
    if out_path.exists():
        out_path = output_dir / f"{name}_{obj.path_id}.shader"
    try:
        out_path.write_bytes(data.export())
        return str(out_path)
    except Exception as e:
        logger.warning("Failed to export Shader '%s': %s", name, e)
        return None


def extract_assets(
    env: UnityPy.Environment,
    output_dir: Path,
    options: ExportOptions | None = None,
    progress_callback=None,
) -> ExtractionResult:
    if options is None:
        options = ExportOptions()

    output_dir.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult()

    objects = list(env.objects)
    total = len(objects)

    for i, obj in enumerate(objects):
        try:
            exported = None
            obj_type = obj.type

            if obj_type == ClassIDType.Texture2D and options.export_textures:
                exported = _export_texture2d(obj, output_dir)
            elif obj_type == ClassIDType.Sprite and options.export_sprites:
                exported = _export_sprite(obj, output_dir)
            elif obj_type == ClassIDType.AudioClip and options.export_audio:
                exported = _export_audio_clip(obj, output_dir)
            elif obj_type == ClassIDType.Font and options.export_fonts:
                exported = _export_font(obj, output_dir)
            elif obj_type == ClassIDType.TextAsset and options.export_text_assets:
                container = obj.container or ""
                exported = _export_text_asset(obj, output_dir, container)
            elif obj_type == ClassIDType.Mesh and options.export_meshes:
                exported = _export_mesh(obj, output_dir)
            elif obj_type == ClassIDType.Shader and options.export_shaders:
                exported = _export_shader(obj, output_dir)

            if exported:
                result.exported_files.append(exported)

        except Exception as e:
            error_msg = f"Error processing object {obj.path_id} ({obj.type.name}): {e}"
            logger.warning(error_msg)
            result.errors.append(error_msg)

        result.total_processed = i + 1
        if progress_callback:
            progress_callback(i + 1, total)

    # Post-processing: reconstruct images from base textures + alpha masks
    if options.reconstruct_from_masks and options.export_textures:
        try:
            from .image_composer import compose_directory

            composed = compose_directory(output_dir, remove_masks=False)
            if composed:
                logger.info(
                    "Reconstructed %d images from alpha masks in %s",
                    len(composed), output_dir,
                )
        except Exception as e:
            error_msg = f"Error during mask reconstruction: {e}"
            logger.warning(error_msg)
            result.errors.append(error_msg)

    return result


def extract_bundle(
    bundle_path: Path,
    output_dir: Path,
    options: ExportOptions | None = None,
    progress_callback=None,
) -> ExtractionResult:
    env = load_bundle(bundle_path)
    return extract_assets(env, output_dir, options, progress_callback)
