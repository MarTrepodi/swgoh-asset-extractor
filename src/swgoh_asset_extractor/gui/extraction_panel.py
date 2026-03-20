from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import AssetOS, ExportOptions
from .workers import AssetExtractionThread


class ExtractionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: AssetExtractionThread | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Export options
        options_group = QGroupBox("Export Options")
        options_layout = QHBoxLayout(options_group)

        self.cb_textures = QCheckBox("Textures")
        self.cb_textures.setChecked(True)
        options_layout.addWidget(self.cb_textures)

        self.cb_sprites = QCheckBox("Sprites")
        self.cb_sprites.setChecked(True)
        options_layout.addWidget(self.cb_sprites)

        self.cb_audio = QCheckBox("Audio")
        self.cb_audio.setChecked(True)
        options_layout.addWidget(self.cb_audio)

        self.cb_fonts = QCheckBox("Fonts")
        self.cb_fonts.setChecked(True)
        options_layout.addWidget(self.cb_fonts)

        self.cb_text = QCheckBox("Text Assets")
        self.cb_text.setChecked(True)
        options_layout.addWidget(self.cb_text)

        self.cb_meshes = QCheckBox("Meshes")
        options_layout.addWidget(self.cb_meshes)

        self.cb_shaders = QCheckBox("Shaders")
        options_layout.addWidget(self.cb_shaders)

        self.cb_sprite_atlases = QCheckBox("Sprite Atlases")
        self.cb_sprite_atlases.setChecked(True)
        options_layout.addWidget(self.cb_sprite_atlases)

        self.cb_reconstruct_masks = QCheckBox("Reconstruct from Masks")
        self.cb_reconstruct_masks.setChecked(True)
        self.cb_reconstruct_masks.setToolTip(
            "Automatically find alpha mask textures (e.g. foo_a.png) and\n"
            "compose them with their base textures to reconstruct final\n"
            "images with proper transparency."
        )
        options_layout.addWidget(self.cb_reconstruct_masks)

        layout.addWidget(options_group)

        # Progress section
        progress_layout = QHBoxLayout()
        self.overall_label = QLabel("Ready")
        progress_layout.addWidget(self.overall_label)
        progress_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        progress_layout.addWidget(self.cancel_btn)
        layout.addLayout(progress_layout)

        self.overall_progress = QProgressBar()
        layout.addWidget(self.overall_progress)

        self.asset_progress = QProgressBar()
        self.asset_progress.setFormat("Objects: %v / %m")
        layout.addWidget(self.asset_progress)

        # Log output
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(5000)
        layout.addWidget(self.log_output, stretch=1)

    def get_export_options(self) -> ExportOptions:
        return ExportOptions(
            export_textures=self.cb_textures.isChecked(),
            export_sprites=self.cb_sprites.isChecked(),
            export_audio=self.cb_audio.isChecked(),
            export_fonts=self.cb_fonts.isChecked(),
            export_text_assets=self.cb_text.isChecked(),
            export_meshes=self.cb_meshes.isChecked(),
            export_shaders=self.cb_shaders.isChecked(),
            export_mono_behaviours=False,
            export_sprite_atlases=self.cb_sprite_atlases.isChecked(),
            reconstruct_from_masks=self.cb_reconstruct_masks.isChecked(),
        )

    def start_extraction(
        self,
        asset_names: list[str],
        version: str,
        asset_os: AssetOS,
        working_dir: Path,
        output_dir: Path,
    ):
        if self._thread is not None and self._thread.isRunning():
            return

        self.log_output.clear()
        self.overall_progress.setRange(0, len(asset_names))
        self.overall_progress.setValue(0)
        self.asset_progress.setValue(0)
        self.cancel_btn.setEnabled(True)

        options = self.get_export_options()
        self._thread = AssetExtractionThread(
            asset_names, version, asset_os, working_dir, output_dir, options,
            parent=self,
        )
        self._thread.extraction_progress.connect(self._on_progress)
        self._thread.object_progress.connect(self._on_asset_progress)
        self._thread.status_update.connect(self._on_status)
        self._thread.extraction_done.connect(self._on_finished)
        self._thread.extraction_error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, current: int, total: int):
        self.overall_progress.setRange(0, total)
        self.overall_progress.setValue(current)

    def _on_asset_progress(self, current: int, total: int):
        self.asset_progress.setRange(0, total)
        self.asset_progress.setValue(current)

    def _on_status(self, status: str):
        self.overall_label.setText(status)
        self.log_output.appendPlainText(status)

    def _on_finished(self, success_count: int, error_count: int):
        self.overall_label.setText(
            f"Done: {success_count} assets exported, {error_count} errors"
        )
        self.log_output.appendPlainText(
            f"\nExtraction complete: {success_count} exported, {error_count} errors"
        )
        self.cancel_btn.setEnabled(False)
        self._thread = None

    def _on_error(self, error: str):
        self.log_output.appendPlainText(f"ERROR: {error}")

    def _cancel(self):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self.overall_label.setText("Cancelling...")
