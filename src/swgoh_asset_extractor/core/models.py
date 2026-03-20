from __future__ import annotations

from enum import IntEnum
from pathlib import Path

from pydantic import BaseModel, Field


class AssetOS(IntEnum):
    WINDOWS = 0
    ANDROID = 1
    IOS = 2

    @property
    def url_path(self) -> str:
        return {
            AssetOS.WINDOWS: "/Windows/ETC/",
            AssetOS.ANDROID: "/Android/ETC/",
            AssetOS.IOS: "/iOS/PVRTC/",
        }[self]

    @property
    def label(self) -> str:
        return self.name.capitalize()


class DiffType(IntEnum):
    NEW = 0
    CHANGED = 1
    ALL = 2


class ManifestEntry(BaseModel):
    asset_name: str = ""
    runtime_size: int = 0
    clone_runtime_size: int = 0


class ManifestRecord(BaseModel):
    name: str = ""
    version: int = 0
    size: int = 0
    uncompressed_size: int = 0
    shared: bool = False
    rank: int = 0
    package_type: int = 0
    entries: list[ManifestEntry] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    crc: int = 0

    @property
    def is_bundle(self) -> bool:
        return self.package_type == 0

    @property
    def is_audio(self) -> bool:
        return self.package_type == 1

    @property
    def prefix(self) -> str:
        parts = self.name.split("_")
        return parts[0] if parts else self.name


class Manifest(BaseModel):
    version: int = 0
    records: list[ManifestRecord] = Field(default_factory=list)
    platform: str = ""
    tex_format: str = ""
    environment: str = ""
    timestamp: int = 0
    revision: int = 0

    @property
    def bundle_records(self) -> list[ManifestRecord]:
        return [r for r in self.records if r.is_bundle]

    @property
    def audio_records(self) -> list[ManifestRecord]:
        return [r for r in self.records if r.is_audio]

    @property
    def prefixes(self) -> list[str]:
        return sorted({r.prefix for r in self.bundle_records})


class SpriteItem(BaseModel):
    name: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    border_left: int = 0
    border_right: int = 0
    border_top: int = 0
    border_bottom: int = 0
    padding_left: int = 0
    padding_right: int = 0
    padding_top: int = 0
    padding_bottom: int = 0
    mirror_horizontal: bool = False
    mirror_vertical: bool = False
    mirror_rotate: bool = False


class Atlas(BaseModel):
    name: str = ""
    sprites: list[SpriteItem] = Field(default_factory=list)


class ExportOptions(BaseModel):
    export_textures: bool = True
    export_sprites: bool = True
    export_audio: bool = True
    export_fonts: bool = True
    export_text_assets: bool = True
    export_meshes: bool = False
    export_shaders: bool = False
    export_mono_behaviours: bool = False
    export_sprite_atlases: bool = True
    reconstruct_from_masks: bool = True


class AppSettings(BaseModel):
    working_directory: str = "./AssetBundles"
    output_directory: str = "./AssetBundles/Output"
    asset_version: str = ""
    asset_os: AssetOS = AssetOS.WINDOWS
    export_options: ExportOptions = Field(default_factory=ExportOptions)

    @property
    def working_path(self) -> Path:
        return Path(self.working_directory).expanduser().resolve()

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory).expanduser().resolve()


class ExtractionResult(BaseModel):
    exported_files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    total_processed: int = 0

    @property
    def success_count(self) -> int:
        return len(self.exported_files)

    @property
    def error_count(self) -> int:
        return len(self.errors)
