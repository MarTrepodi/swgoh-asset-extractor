# SWGOH Asset Extractor

Cross-platform GUI application for extracting game assets from **Star Wars: Galaxy of Heroes** Unity bundles. Works on Windows, macOS, and Linux.

## Features

- **Manifest browser** -- Download and browse game asset manifests with search and prefix filtering
- **Asset extraction** -- Extract images, sprites, audio, fonts, and text assets from Unity bundles
- **Alpha mask reconstruction** -- Automatically pair base textures with their alpha masks and compose final images with proper transparency
- **Sprite atlas cutting** -- Parse NGUI sprite atlases and extract individual sprites with mask support
- **Version diffing** -- Compare two manifest versions to find new or changed bundles
- **Audio extraction** -- Download and extract Wwise audio packages (.wwpkg/.pck)
- **Persistent settings** -- Asset version, platform, and output directory auto-save across sessions

## Supported Asset Types

| Type | Output Format |
|------|---------------|
| Texture2D | PNG |
| Sprite | PNG |
| AudioClip | WAV / OGG |
| Font | TTF / OTF |
| TextAsset | Original extension |
| Mesh | OBJ |
| Shader | .shader |
| Sprite Atlas (NGUI) | Individual PNGs |

## Requirements

- Python 3.10 or later
- A supported platform: Windows, macOS, or Linux

## Installation

```bash
# Clone the repository
git clone https://github.com/swgoh-utils/swgoh-asset-extractor.git
cd swgoh-asset-extractor

# Create a virtual environment and install
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -e .
```

## Usage

### GUI

```bash
python -m swgoh_asset_extractor.main
```

Or if installed:

```bash
swgoh-asset-extractor
```

### Quick Start

1. Launch the application
2. Enter the game asset version in the **Version** field (found in the [game metadata](https://github.com/swgoh-utils/gamedata/blob/main/meta.json))
3. Select a **Platform** (Windows, Android, or iOS)
4. Set an **Output** directory or use the default
5. Click **Download Manifest** to fetch the asset list
6. Browse, search, or filter assets in the tree view
7. Select assets and click **Extract Selected**, or use **Extract All**

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+,` | Open Settings |
| `Ctrl+O` | Open Output Folder |
| `Ctrl+L` | Clear Log |
| `Ctrl+1` | Switch to Assets tab |
| `Ctrl+2` | Switch to Diff tab |
| `Ctrl+Q` | Quit |

## Project Structure

```
swgoh-asset-extractor/
├── pyproject.toml
├── proto/
│   └── manifest.proto              # Protobuf schema (reference)
├── src/swgoh_asset_extractor/
│   ├── main.py                     # Application entry point
│   ├── core/
│   │   ├── models.py               # Data classes (Manifest, ExportOptions, etc.)
│   │   ├── settings.py             # JSON settings persistence
│   │   ├── downloader.py           # HTTP streaming downloads with progress
│   │   ├── manifest.py             # Protobuf parser + manifest diffing
│   │   ├── extractor.py            # Unity bundle extraction via UnityPy
│   │   ├── image_composer.py       # Alpha mask detection and compositing
│   │   ├── sprite_cutter.py        # NGUI atlas parser + sprite cropping
│   │   └── audio_extractor.py      # Wwise .wwpkg/.pck extraction
│   └── gui/
│       ├── main_window.py          # Main window with menu bar and tabs
│       ├── manifest_panel.py       # Manifest download, asset tree, search
│       ├── extraction_panel.py     # Export options, progress, log output
│       ├── diff_panel.py           # Version comparison
│       ├── settings_dialog.py      # Settings form
│       ├── asset_preview.py        # Image preview
│       └── workers.py              # QThread workers for background ops
└── tests/
```

## Configuration

Settings are stored at `~/.swgoh-asset-extractor/settings.json` and include:

| Setting | Default | Description |
|---------|---------|-------------|
| `working_directory` | `./AssetBundles` | Temp storage for downloads |
| `output_directory` | `./AssetBundles/Output` | Extracted asset output |
| `asset_version` | *(empty)* | Game asset version (auto-saved) |
| `asset_os` | `Windows` | Target platform |

## Alpha Mask Reconstruction

Many SWGOH textures are stored as separate RGB + alpha mask pairs. The extractor automatically detects these by naming convention and composites them:

- `tex_foo.png` + `tex_foo_a.png` -- suffix `_a`
- `tex_foo.png` + `tex_foo_alpha.png` -- suffix `_alpha`
- `tex_foo.png` + `tex_foo_mask.png` -- suffix `_mask`

The mask's RGB channels are averaged to grayscale and applied as the alpha channel of the base texture, matching the game engine's rendering pipeline. This can be toggled via the **Reconstruct from Masks** checkbox.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## Building Standalone Executables

```bash
# Install PyInstaller (included in dev dependencies)
pip install -e ".[dev]"

# Build for the current platform
pyinstaller --onefile --windowed --name SWGOHAssetExtractor \
    src/swgoh_asset_extractor/main.py
```

The executable will be in the `dist/` directory.

## Technology Stack

- **[PySide6](https://doc.qt.io/qtforpython-6/)** -- Cross-platform Qt GUI
- **[UnityPy](https://github.com/K0lb3/UnityPy)** -- Unity asset bundle parsing (Texture2D, Sprite, AudioClip, Font, etc.)
- **[Pillow](https://python-pillow.org/)** -- Image processing for sprite cutting and mask compositing
- **[httpx](https://www.python-httpx.org/)** -- HTTP client with streaming downloads
- **[Pydantic](https://docs.pydantic.dev/)** -- Data validation and settings management

## License

MIT
