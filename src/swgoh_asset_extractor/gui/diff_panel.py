from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import AssetOS, DiffType
from .workers import DiffThread


class DiffPanel(QWidget):
    extraction_requested = Signal(list)  # list of bundle names

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: DiffThread | None = None
        self._diff_results: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Diff configuration
        config_group = QGroupBox("Version Comparison")
        config_layout = QHBoxLayout(config_group)

        config_layout.addWidget(QLabel("Old Version:"))
        self.old_version_edit = QLineEdit()
        self.old_version_edit.setPlaceholderText("e.g. 2045")
        config_layout.addWidget(self.old_version_edit)

        config_layout.addWidget(QLabel("New Version:"))
        self.new_version_edit = QLineEdit()
        self.new_version_edit.setPlaceholderText("e.g. 2046")
        config_layout.addWidget(self.new_version_edit)

        config_layout.addWidget(QLabel("Diff Type:"))
        self.diff_type_combo = QComboBox()
        self.diff_type_combo.addItem("All Changes", DiffType.ALL)
        self.diff_type_combo.addItem("New Only", DiffType.NEW)
        self.diff_type_combo.addItem("Changed Only", DiffType.CHANGED)
        config_layout.addWidget(self.diff_type_combo)

        self.compare_btn = QPushButton("Compare")
        self.compare_btn.clicked.connect(self._compare)
        config_layout.addWidget(self.compare_btn)

        layout.addWidget(config_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Results
        self.results_label = QLabel("")
        layout.addWidget(self.results_label)

        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.results_list, stretch=1)

        # Actions
        actions_layout = QHBoxLayout()
        self.extract_selected_btn = QPushButton("Extract Selected")
        self.extract_selected_btn.clicked.connect(self._extract_selected)
        self.extract_selected_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_selected_btn)

        self.extract_all_btn = QPushButton("Extract All Diff")
        self.extract_all_btn.clicked.connect(self._extract_all)
        self.extract_all_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_all_btn)

        layout.addLayout(actions_layout)

    def set_asset_os(self, asset_os: AssetOS):
        self._asset_os = asset_os

    def set_working_dir(self, working_dir):
        self._working_dir = working_dir

    @property
    def _current_asset_os(self) -> AssetOS:
        return getattr(self, "_asset_os", AssetOS.WINDOWS)

    @property
    def _current_working_dir(self):
        from pathlib import Path
        return getattr(self, "_working_dir", Path("./AssetBundles").resolve())

    def _compare(self):
        old_ver = self.old_version_edit.text().strip()
        new_ver = self.new_version_edit.text().strip()
        if not old_ver or not new_ver:
            QMessageBox.warning(self, "Error", "Please enter both versions.")
            return

        self.compare_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        diff_type = self.diff_type_combo.currentData()
        self._thread = DiffThread(
            old_ver, new_ver, self._current_asset_os,
            self._current_working_dir, diff_type,
            parent=self,
        )
        self._thread.diff_done.connect(self._on_diff_finished)
        self._thread.diff_error.connect(self._on_error)
        self._thread.start()

    def _on_diff_finished(self, results_str: str):
        self.compare_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._thread = None

        results = [r for r in results_str.split("\n") if r] if results_str else []
        self._diff_results = results

        self.results_list.clear()
        self.results_list.addItems(results)
        self.results_label.setText(f"{len(results)} bundles differ")
        self.extract_selected_btn.setEnabled(bool(results))
        self.extract_all_btn.setEnabled(bool(results))

    def _on_error(self, error: str):
        self.compare_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", error)

    def _extract_selected(self):
        items = self.results_list.selectedItems()
        if not items:
            QMessageBox.information(self, "Info", "No items selected.")
            return
        names = [item.text() for item in items]
        self.extraction_requested.emit(names)

    def _extract_all(self):
        if self._diff_results:
            self.extraction_requested.emit(self._diff_results)
