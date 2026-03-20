from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AssetPreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel("Select an asset to preview")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area, stretch=1)

    def preview_image(self, path: str):
        p = Path(path)
        if not p.exists():
            self.info_label.setText(f"File not found: {path}")
            self.image_label.clear()
            return

        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp"):
            pixmap = QPixmap(str(p))
            if pixmap.isNull():
                self.info_label.setText(f"Cannot load image: {p.name}")
                self.image_label.clear()
                return

            # Scale to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                800, 600,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
            self.info_label.setText(f"{p.name} ({pixmap.width()}x{pixmap.height()})")
        else:
            self.info_label.setText(f"Preview not available for: {p.suffix}")
            self.image_label.clear()

    def clear_preview(self):
        self.info_label.setText("Select an asset to preview")
        self.image_label.clear()
