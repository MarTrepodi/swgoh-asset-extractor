from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.models import AppSettings, Manifest
from ..core.settings import load_settings, save_settings
from .diff_panel import DiffPanel
from .extraction_panel import ExtractionPanel
from .manifest_panel import ManifestPanel
from .settings_dialog import SettingsDialog

APP_VERSION = "0.1.0"
GITHUB_URL = "https://github.com/swgoh-utils/swgoh-asset-extractor"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SWGOH Asset Extractor")
        self.setMinimumSize(1000, 700)

        self._settings = load_settings()
        self._manifest: Manifest | None = None

        self._setup_menu_bar()
        self._setup_ui()
        self._apply_settings()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # ---- File ----
        file_menu = menu_bar.addMenu("&File")

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        open_output_action = QAction("Open &Output Folder", self)
        open_output_action.setShortcut(QKeySequence("Ctrl+O"))
        open_output_action.triggered.connect(self._open_output_folder)
        file_menu.addAction(open_output_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.setMenuRole(QAction.MenuRole.QuitRole)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ---- Edit ----
        edit_menu = menu_bar.addMenu("&Edit")

        clear_log_action = QAction("&Clear Log", self)
        clear_log_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_log_action.triggered.connect(self._clear_log)
        edit_menu.addAction(clear_log_action)

        # ---- View ----
        view_menu = menu_bar.addMenu("&View")

        assets_tab_action = QAction("&Assets Tab", self)
        assets_tab_action.setShortcut(QKeySequence("Ctrl+1"))
        assets_tab_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction(assets_tab_action)

        diff_tab_action = QAction("&Diff Tab", self)
        diff_tab_action.setShortcut(QKeySequence("Ctrl+2"))
        diff_tab_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction(diff_tab_action)

        # ---- Help ----
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        about_qt_action = QAction("About &Qt", self)
        about_qt_action.setMenuRole(QAction.MenuRole.AboutQtRole)
        about_qt_action.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(about_qt_action)

        help_menu.addSeparator()

        github_action = QAction("&GitHub Repository", self)
        github_action.triggered.connect(
            lambda: webbrowser.open(GITHUB_URL)
        )
        help_menu.addAction(github_action)

        report_issue_action = QAction("&Report Issue...", self)
        report_issue_action.triggered.connect(
            lambda: webbrowser.open(f"{GITHUB_URL}/issues/new")
        )
        help_menu.addAction(report_issue_action)

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()

        # Tab 1: Assets (manifest + extraction combined)
        assets_widget = QWidget()
        assets_layout = QVBoxLayout(assets_widget)

        self.manifest_panel = ManifestPanel()
        self.manifest_panel.manifest_loaded.connect(self._on_manifest_loaded)
        self.manifest_panel.extraction_requested.connect(self._on_extraction_requested)
        assets_layout.addWidget(self.manifest_panel, stretch=2)

        self.extraction_panel = ExtractionPanel()
        assets_layout.addWidget(self.extraction_panel, stretch=1)

        self.tabs.addTab(assets_widget, "Assets")

        # Tab 2: Diff
        self.diff_panel = DiffPanel()
        self.diff_panel.extraction_requested.connect(self._on_extraction_requested)
        self.tabs.addTab(self.diff_panel, "Diff")

        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _apply_settings(self):
        self.manifest_panel.set_settings(
            self._settings.asset_version,
            self._settings.output_directory,
            self._settings.asset_os,
        )

    def _open_settings(self):
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec():
            self._settings = dialog.get_settings()
            save_settings(self._settings)
            self._apply_settings()
            self.status_bar.showMessage("Settings saved")

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _open_output_folder(self):
        output_dir = self.manifest_panel.output_dir or self._settings.output_directory
        path = Path(output_dir).resolve()
        if not path.exists():
            QMessageBox.information(
                self, "Info",
                f"Output directory does not exist yet:\n{path}",
            )
            return
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _clear_log(self):
        self.extraction_panel.log_output.clear()
        self.status_bar.showMessage("Log cleared")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About SWGOH Asset Extractor",
            f"<h3>SWGOH Asset Extractor v{APP_VERSION}</h3>"
            "<p>Cross-platform tool for extracting game assets from "
            "Star Wars: Galaxy of Heroes Unity bundles.</p>"
            "<p><b>Supported assets:</b><br>"
            "Images (Texture2D, Sprites), Audio, Fonts, "
            "Text Assets, Meshes, Sprite Atlases</p>"
            "<p><b>Features:</b><br>"
            "Manifest browsing, version diffing, alpha mask "
            "reconstruction, batch extraction</p>"
            f'<p><a href="{GITHUB_URL}">GitHub Repository</a></p>',
        )

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _on_manifest_loaded(self, manifest: Manifest):
        self._manifest = manifest
        self.status_bar.showMessage(
            f"Manifest loaded: {len(manifest.bundle_records)} bundles, "
            f"{len(manifest.audio_records)} audio packages"
        )
        self.diff_panel.set_asset_os(self.manifest_panel.asset_os)
        working_dir = Path(self.manifest_panel.output_dir or "./AssetBundles").resolve()
        self.diff_panel.set_working_dir(working_dir)

        # Auto-save current values so they persist across restarts
        self._settings.asset_version = self.manifest_panel.version
        self._settings.asset_os = self.manifest_panel.asset_os
        if self.manifest_panel.output_dir:
            self._settings.output_directory = self.manifest_panel.output_dir
        save_settings(self._settings)

    def _on_extraction_requested(self, asset_names: list[str]):
        version = self.manifest_panel.version
        if not version:
            QMessageBox.warning(self, "Error", "Please set an asset version first.")
            return

        output_dir = Path(self.manifest_panel.output_dir or "./AssetBundles/Output").resolve()
        working_dir = Path(self.manifest_panel.output_dir or "./AssetBundles").resolve()

        self.status_bar.showMessage(f"Starting extraction of {len(asset_names)} assets...")
        self.tabs.setCurrentIndex(0)

        self.extraction_panel.start_extraction(
            asset_names,
            version,
            self.manifest_panel.asset_os,
            working_dir,
            output_dir,
        )
