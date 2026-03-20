from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..core.manifest import parse_manifest_file
from ..core.models import AssetOS, Manifest
from .workers import ManifestDownloadThread


class ManifestPanel(QWidget):
    manifest_loaded = Signal(object)  # Manifest
    extraction_requested = Signal(list)  # list of asset names

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manifest: Manifest | None = None
        self._thread: ManifestDownloadThread | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Configuration section
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout(config_group)

        config_layout.addWidget(QLabel("Platform:"))
        self.os_combo = QComboBox()
        for os in AssetOS:
            self.os_combo.addItem(os.label, os)
        config_layout.addWidget(self.os_combo)

        config_layout.addWidget(QLabel("Version:"))
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 2046")
        self.version_edit.setMinimumWidth(100)
        config_layout.addWidget(self.version_edit)

        config_layout.addWidget(QLabel("Output:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output directory")
        self.output_edit.setMinimumWidth(200)
        config_layout.addWidget(self.output_edit)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_output)
        config_layout.addWidget(self.browse_btn)

        self.download_btn = QPushButton("Download Manifest")
        self.download_btn.clicked.connect(self._download_manifest)
        config_layout.addWidget(self.download_btn)

        layout.addWidget(config_group)

        # Search and filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter assets by name...")
        self.search_edit.textChanged.connect(self._filter_changed)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addWidget(QLabel("Prefix:"))
        self.prefix_combo = QComboBox()
        self.prefix_combo.addItem("All")
        self.prefix_combo.currentTextChanged.connect(self._filter_changed)
        filter_layout.addWidget(self.prefix_combo)

        self.asset_count_label = QLabel("")
        filter_layout.addWidget(self.asset_count_label)
        layout.addLayout(filter_layout)

        # Asset tree view
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Name", "Size", "Type", "Entries"])

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setRecursiveFilteringEnabled(True)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree_view, stretch=1)

        # Actions
        actions_layout = QHBoxLayout()
        self.extract_selected_btn = QPushButton("Extract Selected")
        self.extract_selected_btn.clicked.connect(self._extract_selected)
        self.extract_selected_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_selected_btn)

        self.extract_prefix_btn = QPushButton("Extract Prefix")
        self.extract_prefix_btn.clicked.connect(self._extract_prefix)
        self.extract_prefix_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_prefix_btn)

        self.extract_all_btn = QPushButton("Extract All")
        self.extract_all_btn.clicked.connect(self._extract_all)
        self.extract_all_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_all_btn)

        layout.addLayout(actions_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def set_settings(self, version: str, output_dir: str, asset_os: AssetOS):
        self.version_edit.setText(version)
        self.output_edit.setText(output_dir)
        self.os_combo.setCurrentIndex(asset_os.value)

    @property
    def asset_os(self) -> AssetOS:
        return self.os_combo.currentData()

    @property
    def version(self) -> str:
        return self.version_edit.text().strip()

    @property
    def output_dir(self) -> str:
        return self.output_edit.text().strip()

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)

    def _download_manifest(self):
        if not self.version:
            QMessageBox.warning(self, "Error", "Please enter an asset version.")
            return

        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate

        working_dir = Path(self.output_dir or "./AssetBundles").resolve()
        self._thread = ManifestDownloadThread(
            self.version, self.asset_os, working_dir, parent=self,
        )
        self._thread.download_progress.connect(self._on_download_progress)
        self._thread.result_ready.connect(self._on_manifest_downloaded)
        self._thread.download_error.connect(self._on_error)
        self._thread.start()

    def _on_download_progress(self, downloaded: int, total: int):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(downloaded)

    def _on_manifest_downloaded(self, manifest_path: str):
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._thread = None

        if not manifest_path:
            return

        # Parse on the main thread — keeps complex objects off cross-thread signals
        try:
            manifest = parse_manifest_file(Path(manifest_path))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse manifest: {e}")
            return

        self._manifest = manifest
        self._populate_tree()
        self.extract_selected_btn.setEnabled(True)
        self.extract_prefix_btn.setEnabled(True)
        self.extract_all_btn.setEnabled(True)
        self.manifest_loaded.emit(manifest)

    def _on_error(self, error: str):
        QMessageBox.critical(self, "Error", error)

    def _populate_tree(self):
        self.model.removeRows(0, self.model.rowCount())
        self.prefix_combo.clear()
        self.prefix_combo.addItem("All")

        if not self._manifest:
            return

        # Group by prefix
        prefixes: dict[str, list] = {}
        for record in self._manifest.bundle_records:
            prefix = record.prefix
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(record)

        for prefix in sorted(prefixes.keys()):
            self.prefix_combo.addItem(prefix)

            prefix_item = QStandardItem(prefix)
            prefix_item.setEditable(False)
            count_item = QStandardItem("")
            type_item = QStandardItem(f"{len(prefixes[prefix])} bundles")
            entries_item = QStandardItem("")

            for record in prefixes[prefix]:
                name_item = QStandardItem(record.name)
                name_item.setData(record.name, Qt.ItemDataRole.UserRole)
                name_item.setEditable(False)
                size_item = QStandardItem(self._format_size(record.size))
                size_item.setEditable(False)
                type_child = QStandardItem("bundle" if record.is_bundle else "audio")
                type_child.setEditable(False)
                entries_child = QStandardItem(str(len(record.entries)))
                entries_child.setEditable(False)
                prefix_item.appendRow([name_item, size_item, type_child, entries_child])

            self.model.appendRow([prefix_item, count_item, type_item, entries_item])

        total = len(self._manifest.bundle_records)
        self.asset_count_label.setText(f"{total} bundles")

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _filter_changed(self):
        text = self.search_edit.text()
        prefix = self.prefix_combo.currentText()

        if prefix != "All" and text:
            self.proxy_model.setFilterRegularExpression(f"(?=.*{prefix})(?=.*{text})")
        elif prefix != "All":
            self.proxy_model.setFilterFixedString(prefix)
        else:
            self.proxy_model.setFilterFixedString(text)

    def _get_selected_names(self) -> list[str]:
        names = []
        for index in self.tree_view.selectionModel().selectedIndexes():
            if index.column() != 0:
                continue
            source_index = self.proxy_model.mapToSource(index)
            item = self.model.itemFromIndex(source_index)
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                names.append(name)
            else:
                # Prefix group - get all children
                for row in range(item.rowCount()):
                    child = item.child(row, 0)
                    child_name = child.data(Qt.ItemDataRole.UserRole)
                    if child_name:
                        names.append(child_name)
        return list(dict.fromkeys(names))  # dedupe preserving order

    def _extract_selected(self):
        names = self._get_selected_names()
        if not names:
            QMessageBox.information(self, "Info", "No assets selected.")
            return
        self.extraction_requested.emit(names)

    def _extract_prefix(self):
        prefix = self.prefix_combo.currentText()
        if prefix == "All" or not self._manifest:
            QMessageBox.information(self, "Info", "Select a prefix first.")
            return
        names = [r.name for r in self._manifest.bundle_records if r.prefix == prefix]
        self.extraction_requested.emit(names)

    def _extract_all(self):
        if not self._manifest:
            return
        names = [r.name for r in self._manifest.bundle_records]
        self.extraction_requested.emit(names)
