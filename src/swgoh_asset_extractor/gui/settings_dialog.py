from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core.models import AppSettings, AssetOS


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._settings = settings
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Working directory
        working_layout = QHBoxLayout()
        self.working_dir_edit = QLineEdit(self._settings.working_directory)
        working_layout.addWidget(self.working_dir_edit)
        browse_working = QPushButton("Browse...")
        browse_working.clicked.connect(lambda: self._browse(self.working_dir_edit))
        working_layout.addWidget(browse_working)
        form.addRow("Working Directory:", working_layout)

        # Output directory
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit(self._settings.output_directory)
        output_layout.addWidget(self.output_dir_edit)
        browse_output = QPushButton("Browse...")
        browse_output.clicked.connect(lambda: self._browse(self.output_dir_edit))
        output_layout.addWidget(browse_output)
        form.addRow("Output Directory:", output_layout)

        # Default version
        self.version_edit = QLineEdit(self._settings.asset_version)
        form.addRow("Default Version:", self.version_edit)

        # Default OS
        self.os_combo = QComboBox()
        for os in AssetOS:
            self.os_combo.addItem(os.label, os)
        self.os_combo.setCurrentIndex(self._settings.asset_os.value)
        form.addRow("Default Platform:", self.os_combo)

        layout.addLayout(form)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self, line_edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            line_edit.setText(path)

    def get_settings(self) -> AppSettings:
        return AppSettings(
            working_directory=self.working_dir_edit.text(),
            output_directory=self.output_dir_edit.text(),
            asset_version=self.version_edit.text(),
            asset_os=self.os_combo.currentData(),
            export_options=self._settings.export_options,
        )
