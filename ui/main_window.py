import os
import shutil
import tempfile
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QFrame, QAbstractItemView, QCheckBox, QProgressDialog,
    QTreeView, QFileSystemModel, QSplitter, QScrollArea, QDialog, QDialogButtonBox,
    QFormLayout
)
from PySide6.QtGui import QPixmap, QAction, QImage, QKeySequence
from PySide6.QtCore import Qt, QDir, QThreadPool

# App-specific imports
from config import (
    delete_gemini_api_key, get_gemini_api_key, get_gemini_key_source,
    save_gemini_api_key,
)
from utils.workers import Worker
from core import tag_manager, file_operations, metadata_fetcher, artist_manager


class MusicTagEditor(QMainWindow):
    """Main application window for the Music Tag Editor."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Tag Editor")
        self.resize(1360, 860)
        self.setMinimumSize(1080, 700)

        # State variables
        self.current_file_path = None
        self.new_art_path = None
        self.staged_art_temp_path = None
        self.current_directory = None
        self.original_tags = {}
        self.tag_drafts = {}
        self.active_selection_count = 0
        self.multi_edit_fields = set()
        self.loading_editor = False
        self.threadpool = QThreadPool()

        self._create_menu_bar()
        self._create_widgets()
        self._create_layouts()
        self._apply_theme()

        self.statusBar().showMessage("Ready — choose a music folder to begin.")

    def show_about_dialog(self):
        """Displays the application's About box."""
        QMessageBox.about(
            self,
            "About Music Tag Editor",
            "<h2>Music Tag Editor</h2>"
            "<p><b>Version 1.0.0 Build 20260712</b></p>"
            "<p>Edit metadata, album artwork, and filenames for MP3, FLAC, and M4A music files.</p>"
            "<hr>"
            "<h3>How to use</h3>"
            "<ol>"
            "<li>Click <b>Choose Music Folder</b> and select your music library.</li>"
            "<li>Choose a folder, then select one or more tracks.</li>"
            "<li>Edit the metadata fields or change the album artwork.</li>"
            "<li>Review your changes and click <b>Save Tags</b>.</li>"
            "</ol>"
            "<p><b>More tools</b></p>"
            "<ul>"
            "<li><b>Fetch Smart Metadata:</b> suggest metadata using Gemini AI.</li>"
            "<li><b>File Naming:</b> rename tracks or folders from tag patterns.</li>"
            "<li><b>Audio Conversion:</b> convert FLAC and ALAC using FFmpeg.</li>"
            "</ul>"
            "<p><i>Tip: Keep backups before editing or converting multiple files.</i></p>"
            "<hr>"
            "<p><b>License:</b> GNU General Public License v3.0</p>"
            "<p>Copyright ©2026 Bokie Tarathep. All rights reserved.</p>"
        )

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open Music Folder…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Tags", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_tags)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        # This role ensures it integrates correctly (e.g., "Quit" on macOS)
        exit_action.setMenuRole(QAction.MenuRole.QuitRole)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        revert_action = QAction("&Revert Unsaved Changes", self)
        revert_action.setShortcut(QKeySequence.StandardKey.Undo)
        revert_action.triggered.connect(self.revert_tag_changes)
        edit_menu.addAction(revert_action)

        tools_menu = menu_bar.addMenu("&Tools")
        fetch_action = QAction("Fetch &Smart Metadata", self)
        fetch_action.triggered.connect(self.fetch_metadata_start)
        tools_menu.addAction(fetch_action)
        api_key_action = QAction("Configure Gemini API &Key…", self)
        api_key_action.triggered.connect(self.show_gemini_key_dialog)
        tools_menu.addAction(api_key_action)
        tools_menu.addSeparator()
        artwork_action = QAction("Change Album &Artwork…", self)
        artwork_action.triggered.connect(self.change_album_art)
        tools_menu.addAction(artwork_action)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About Music Tag Editor", self)
        # This role is crucial for placing it in the app menu on macOS
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def _create_widgets(self):
        # --- Directory Browser ---
        self.dir_model = QFileSystemModel()
        self.dir_model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.Dirs)
        self.dir_model.setRootPath(QDir.homePath())
        self.dir_tree = QTreeView()
        self.dir_tree.setModel(self.dir_model)
        self.dir_tree.setRootIndex(self.dir_model.index(QDir.homePath()))
        self.dir_tree.setHeaderHidden(True)
        for i in range(1, 4): self.dir_tree.hideColumn(i)
        self.dir_tree.clicked.connect(self._on_directory_clicked)
        self.dir_tree.setToolTip("Choose a folder to list its MP3, FLAC, and M4A tracks.")

        self.open_folder_button = QPushButton("Choose Music Folder")
        self.open_folder_button.setObjectName("primaryButton")
        self.open_folder_button.clicked.connect(self.open_directory)
        self.library_path_label = QLabel("No folder selected")
        self.library_path_label.setObjectName("mutedLabel")
        self.library_path_label.setWordWrap(True)

        # --- File List ---
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.file_list_widget.setToolTip("Select one track to edit it, or multiple tracks for bulk editing.")
        self.file_count_label = QLabel("0 tracks")
        self.file_count_label.setObjectName("countLabel")

        # --- Album Art and Tools ---
        self.album_art_label = QLabel("Select a directory to start.")
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art_label.setFixedSize(300, 300)
        self.album_art_label.setScaledContents(False)
        self.album_art_label.setObjectName("albumArt")
        self.album_art_info_label = QLabel("No artwork selected")
        self.album_art_info_label.setObjectName("artInfoLabel")
        self.album_art_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.change_art_button = QPushButton("Change Album Art")
        self.change_art_button.setToolTip("Choose an image from the selected track's folder and prepare a square cover.")
        self.change_art_button.clicked.connect(self.change_album_art)

        # --- Renaming ---
        self.rename_format_input = QLineEdit("{track} - {title}")
        self.rename_format_input.setToolTip("Build filenames with tags such as {track}, {title}, and {artist}.")
        self.rename_button = QPushButton("Rename Selected Files")
        self.rename_button.clicked.connect(self.rename_files)
        self.rename_dir_format_input = QLineEdit("[{quality}] {albumartist} - {album}")
        self.rename_dir_format_input.setToolTip("Build the folder name with album-level tag placeholders.")
        self.rename_dir_button = QPushButton("Rename Directory")
        self.rename_dir_button.clicked.connect(self.rename_directory)

        # --- Online Tools ---
        self.fetch_button = QPushButton("Fetch Smart Metadata")
        self.fetch_button.setToolTip("Search Gemini for metadata and keep the results as unsaved drafts.")
        self.fetch_button.clicked.connect(self.fetch_metadata_start)
        self.fetch_button.setEnabled(False)
        self.configure_api_button = QPushButton("Configure Gemini API Key…")
        self.configure_api_button.setToolTip("Securely store the key in macOS Keychain or Windows Credential Manager.")
        self.configure_api_button.clicked.connect(self.show_gemini_key_dialog)
        self.revert_button = QPushButton("Revert Changes")
        self.revert_button.clicked.connect(self.revert_tag_changes)
        self.revert_button.setEnabled(False)
        self.revert_button.setMinimumHeight(48)

        # --- Artist Management ---
        self.update_artists_button = QPushButton("Add Names to Artist Library")
        self.update_artists_button.clicked.connect(self.update_artist_library)
        self.standardize_artists_button = QPushButton("Standardize Artist Names")
        self.standardize_artists_button.clicked.connect(self.standardize_artist_names)

        # --- Tag Fields ---
        self.tag_fields = {}
        tags_to_edit = ["Title", "Artist", "Album", "Album Artist", "Composer",
                        "Genre", "Year", "Track", "Disc", "Comment"]
        for tag_name in tags_to_edit:
            field = QLineEdit()
            # textChanged also captures values inserted by Smart Metadata and
            # artist standardization. loading_editor prevents disk reloads from
            # being mistaken for user changes.
            field.textChanged.connect(self._on_tag_edited)
            self.tag_fields[tag_name.lower().replace(" ", "")] = field
        self.tag_fields["title"].setPlaceholderText("Track title")
        self.tag_fields["artist"].setPlaceholderText("Primary track artist")
        self.tag_fields["album"].setPlaceholderText("Album or release title")
        self.tag_fields["albumartist"].setPlaceholderText("Primary album artist")
        self.tag_fields["composer"].setPlaceholderText("Composer or songwriter")
        self.tag_fields["genre"].setPlaceholderText("Genre")
        self.tag_fields["year"].setPlaceholderText("YYYY")
        self.tag_fields["track"].setPlaceholderText("Track number")
        self.tag_fields["disc"].setPlaceholderText("Disc number")
        self.tag_fields["comment"].setPlaceholderText("Notes or metadata source URLs")

        # --- Info Labels ---
        self.info_labels = {}
        info_to_show = ["Quality", "Duration", "Format", "Bitrate", "Sample Rate", "File Size"]
        for info_name in info_to_show:
            self.info_labels[info_name.lower().replace(" ", "")] = QLabel("---")

        # --- Conversion Tools ---
        self.convert_button = QPushButton("Convert Selected FLAC ↔ ALAC")
        self.convert_button.clicked.connect(self.convert_files)
        self.convert_button.setEnabled(False)
        self.backup_checkbox = QCheckBox("Keep original files in a backup folder")
        self.backup_checkbox.setChecked(True)

        # --- Save Button ---
        self.save_button = QPushButton("Save Tags")
        self.save_button.setObjectName("saveButton")
        self.save_button.setMinimumHeight(48)
        self.save_button.clicked.connect(self.save_tags)

    def _create_layouts(self):
        # Library pane
        library_panel = QFrame()
        library_panel.setObjectName("panel")
        library_panel.setMinimumWidth(270)
        library_panel.setMaximumWidth(390)
        library_layout = QVBoxLayout(library_panel)
        library_layout.setContentsMargins(18, 18, 18, 18)
        library_layout.setSpacing(10)
        library_layout.addWidget(self._section_label("Music Library", "Browse folders and select tracks"))
        library_layout.addWidget(self.open_folder_button)
        library_layout.addWidget(self.library_path_label)
        library_layout.addWidget(self.dir_tree, 3)

        tracks_header = QHBoxLayout()
        tracks_header.addWidget(self._section_label("Tracks"))
        tracks_header.addStretch()
        tracks_header.addWidget(self.file_count_label)
        library_layout.addLayout(tracks_header)
        library_layout.addWidget(self.file_list_widget, 2)

        # Artwork and actions pane
        art_tools_container = QFrame()
        art_tools_container.setObjectName("panel")
        art_tools_container.setMinimumWidth(300)
        art_tools_container.setMaximumWidth(380)
        art_layout = QVBoxLayout(art_tools_container)
        art_layout.setContentsMargins(18, 18, 18, 18)
        art_layout.setSpacing(10)
        art_layout.addWidget(self._section_label("Album Artwork", "Preview or replace the embedded cover"))
        art_layout.addWidget(self.album_art_label, alignment=Qt.AlignmentFlag.AlignCenter)
        art_layout.addWidget(self.album_art_info_label)
        art_layout.addWidget(self.change_art_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("File Naming", "Rename from the selected tracks' saved tags"))
        art_layout.addWidget(self._field_label("File name pattern"))
        art_layout.addWidget(self.rename_format_input)
        art_layout.addWidget(self.rename_button)
        art_layout.addSpacing(4)
        art_layout.addWidget(self._field_label("Folder name pattern"))
        art_layout.addWidget(self.rename_dir_format_input)
        art_layout.addWidget(self.rename_dir_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("Smart Metadata", "Suggestions powered by Gemini AI"))
        art_layout.addWidget(self.fetch_button)
        art_layout.addWidget(self.configure_api_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("Artist Names", "Build and apply consistent artist naming"))
        artist_mgmt_layout = QVBoxLayout()
        artist_mgmt_layout.setSpacing(8)
        artist_mgmt_layout.addWidget(self.update_artists_button)
        artist_mgmt_layout.addWidget(self.standardize_artists_button)
        art_layout.addLayout(artist_mgmt_layout)
        art_layout.addStretch()

        art_scroll = QScrollArea()
        art_scroll.setObjectName("panelScroll")
        art_scroll.setWidgetResizable(True)
        art_scroll.setFrameShape(QFrame.Shape.NoFrame)
        art_scroll.setWidget(art_tools_container)

        # Metadata pane
        fields_container = QFrame()
        fields_container.setObjectName("panel")
        fields_container.setMinimumWidth(390)
        fields_pane_layout = QVBoxLayout(fields_container)
        fields_pane_layout.setContentsMargins(20, 18, 20, 18)
        fields_pane_layout.setSpacing(12)
        fields_pane_layout.addWidget(self._section_label("Track Metadata", "Edit values, then save them to the selected files"))
        self.editable_fields_layout = QGridLayout()
        self.editable_fields_layout.setHorizontalSpacing(14)
        self.editable_fields_layout.setVerticalSpacing(10)
        self.editable_fields_layout.setContentsMargins(8, 4, 0, 4)
        self.editable_fields_layout.setColumnMinimumWidth(0, 100)
        self.editable_fields_layout.setColumnStretch(1, 1)
        tag_labels = {
            "title": "Title", "artist": "Artist", "album": "Album",
            "albumartist": "Album Artist", "composer": "Composer", "genre": "Genre",
            "year": "Year", "track": "Track Number", "disc": "Disc Number", "comment": "Comment",
        }
        for i, (key, widget) in enumerate(self.tag_fields.items()):
            label = self._field_label(f"{tag_labels[key]}:", form=True)
            self.editable_fields_layout.addWidget(label, i, 0)
            self.editable_fields_layout.addWidget(widget, i, 1)

        self.info_fields_layout = QGridLayout()
        self.info_fields_layout.setHorizontalSpacing(18)
        self.info_fields_layout.setVerticalSpacing(8)
        self.info_fields_layout.setContentsMargins(8, 2, 0, 4)
        self.info_fields_layout.setColumnMinimumWidth(0, 100)
        self.info_fields_layout.setColumnStretch(1, 1)
        info_names = {
            "quality": "Quality", "duration": "Duration", "format": "Format",
            "bitrate": "Bitrate", "samplerate": "Sample Rate", "filesize": "File Size",
        }
        for i, (key, widget) in enumerate(self.info_labels.items()):
            label = self._field_label(f"{info_names[key]}:", form=True)
            self.info_fields_layout.addWidget(label, i, 0)
            self.info_fields_layout.addWidget(widget, i, 1)

        fields_pane_layout.addLayout(self.editable_fields_layout)
        fields_pane_layout.addWidget(self._create_separator())
        fields_pane_layout.addWidget(self._section_label("Audio Details"))
        fields_pane_layout.addLayout(self.info_fields_layout)
        fields_pane_layout.addWidget(self._create_separator())
        fields_pane_layout.addWidget(self._section_label("Audio Conversion", "Convert between FLAC and Apple Lossless using FFmpeg"))
        fields_pane_layout.addWidget(self.convert_button)
        fields_pane_layout.addWidget(self.backup_checkbox)
        fields_pane_layout.addStretch()

        fields_scroll = QScrollArea()
        fields_scroll.setObjectName("panelScroll")
        fields_scroll.setWidgetResizable(True)
        fields_scroll.setFrameShape(QFrame.Shape.NoFrame)
        fields_scroll.setWidget(fields_container)

        metadata_pane = QWidget()
        metadata_layout = QVBoxLayout(metadata_pane)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(10)
        metadata_layout.addWidget(fields_scroll, 1)
        save_actions_layout = QHBoxLayout()
        save_actions_layout.setSpacing(10)
        save_actions_layout.addWidget(self.revert_button, 1)
        save_actions_layout.addWidget(self.save_button, 2)
        metadata_layout.addLayout(save_actions_layout)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setObjectName("mainSplitter")
        main_splitter.addWidget(library_panel)
        main_splitter.addWidget(art_scroll)
        main_splitter.addWidget(metadata_pane)
        main_splitter.setSizes([300, 340, 560])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 0)
        main_splitter.setStretchFactor(2, 1)

        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.addWidget(main_splitter)
        self.setCentralWidget(central_widget)

    def _section_label(self, title, subtitle=None):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        if subtitle:
            detail = QLabel(subtitle)
            detail.setObjectName("mutedLabel")
            detail.setWordWrap(True)
            layout.addWidget(detail)
        return container

    def _field_label(self, text, form=False):
        label = QLabel(text)
        label.setObjectName("formLabel" if form else "fieldLabel")
        if form:
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def show_gemini_key_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Gemini API Key")
        dialog.setMinimumWidth(520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(self._section_label(
            "Gemini API Key",
            "Stored securely in macOS Keychain or Windows Credential Manager. The key is never displayed after saving.",
        ))

        source = get_gemini_key_source()
        if source == "environment":
            status_text = "Active source: GEMINI_API_KEY from the operating-system environment"
        elif source == "keyring":
            status_text = "Active source: secure operating-system credential store"
        else:
            status_text = "No Gemini API key is currently configured"

        status_label = QLabel(status_text)
        status_label.setObjectName("credentialStatus")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        key_input = QLineEdit()
        key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_input.setClearButtonEnabled(True)
        key_input.setPlaceholderText("Paste a new Gemini API key")
        form.addRow(self._field_label("API Key:", form=True), key_input)
        layout.addLayout(form)

        help_label = QLabel(
            "Environment priority: if GEMINI_API_KEY is defined by the operating system or .env, "
            "it overrides the credential-store value. Remove that environment variable and restart "
            "the app to use the saved credential instead."
        )
        help_label.setObjectName("mutedLabel")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        remove_button = buttons.addButton("Remove Saved Key", QDialogButtonBox.ButtonRole.DestructiveRole)
        save_button = buttons.addButton("Save Securely", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if source == "environment":
            key_input.setEnabled(False)
            save_button.setEnabled(False)
            key_input.setPlaceholderText("Managed by GEMINI_API_KEY environment variable")

        def save_key():
            try:
                save_gemini_api_key(key_input.text())
            except Exception as exc:
                QMessageBox.critical(dialog, "Could Not Save API Key", str(exc))
                return
            QMessageBox.information(dialog, "API Key Saved", "The key was saved in the secure OS credential store.")
            dialog.accept()

        def remove_key():
            try:
                delete_gemini_api_key()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could Not Remove API Key", str(exc))
                return
            QMessageBox.information(dialog, "API Key Removed", "The saved credential-store key was removed.")
            dialog.accept()

        save_button.clicked.connect(save_key)
        remove_button.clicked.connect(remove_key)
        dialog.exec()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f3fa; color: #27223a; font-size: 14px; }
            QFrame#panel { background: #ffffff; border: 1px solid #ddd8e9; border-radius: 12px; }
            QScrollArea#panelScroll, QScrollArea#panelScroll > QWidget > QWidget { background: transparent; }
            QLabel#sectionTitle { font-size: 17px; font-weight: 700; color: #31294f; }
            QLabel#mutedLabel { color: #756d89; font-size: 12px; }
            QLabel#fieldLabel { color: #514866; font-size: 12px; font-weight: 600; }
            QLabel#formLabel { color: #4d455f; font-size: 13px; font-weight: 600; padding-right: 3px; }
            QLabel#countLabel { color: #44366f; background: #ece7f7; border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 600; }
            QLabel#albumArt { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f2eff9, stop:1 #e9e3f4); border: 1px dashed #afa5c8; border-radius: 10px; color: #716889; padding: 0px; }
            QLabel#artInfoLabel { color: #685f79; background: #eee9f7; border-radius: 8px; padding: 5px 9px; font-size: 11px; font-weight: 600; }
            QLineEdit { background: #ffffff; border: 1px solid #cec8dc; border-radius: 7px; padding: 8px 10px; min-height: 20px; selection-color: #ffffff; selection-background-color: #43366d; }
            QLineEdit:hover { border-color: #a99fc1; }
            QLineEdit:focus { border: 2px solid #493b75; padding: 7px 9px; }
            QLineEdit:disabled { background: #f1eff5; color: #958da5; }
            QPushButton { color: #332b4d; background: #faf9fc; border: 1px solid #cec8dc; border-radius: 7px; padding: 8px 12px; font-weight: 600; }
            QPushButton:hover { color: #3f3268; background: #eee9f7; border-color: #a99fc1; }
            QPushButton:pressed { background: #e2dbef; }
            QPushButton:disabled { color: #aaa4b5; background: #f3f1f6; border-color: #e3dfea; }
            QPushButton#primaryButton, QPushButton#saveButton { color: white; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #493d78, stop:1 #382e5f); border-color: #3f346a; }
            QPushButton#primaryButton:hover, QPushButton#saveButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #57478d, stop:1 #433670); border-color: #493b75; }
            QPushButton#primaryButton:pressed, QPushButton#saveButton:pressed { background: #30274f; }
            QTreeView, QListWidget { background: #fcfbfd; border: 1px solid #dfdae9; border-radius: 8px; padding: 4px; outline: none; }
            QTreeView::item, QListWidget::item { min-height: 28px; border-radius: 5px; padding: 2px 5px; }
            QTreeView::item:hover, QListWidget::item:hover { background: #f0ecf7; }
            QTreeView::item:selected, QListWidget::item:selected { color: #35275f; background: #e4dcf3; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator:checked { background: #463970; border: 1px solid #463970; }
            QFrame[frameShape="4"] { color: #e2ddea; }
            QSplitter#mainSplitter::handle { background: transparent; width: 8px; }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
            QScrollBar::handle:vertical { background: #c5bed3; border-radius: 4px; min-height: 28px; }
            QScrollBar::handle:vertical:hover { background: #a99fc0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QStatusBar { background: #ffffff; border-top: 1px solid #ddd8e9; color: #685f79; }
            QMenuBar { background: #ffffff; color: #302947; border-bottom: 1px solid #e1ddea; padding: 2px 6px; }
            QMenuBar::item { background: transparent; border-radius: 5px; padding: 5px 9px; }
            QMenuBar::item:selected { background: #ece7f7; }
            QMenu { background: #ffffff; color: #302947; border: 1px solid #d9d3e5; padding: 5px; }
            QMenu::item { border-radius: 5px; padding: 7px 28px 7px 10px; }
            QMenu::item:selected { background: #e8e1f4; color: #35275f; }
            QMenu::separator { background: #e6e1ec; height: 1px; margin: 5px 8px; }
        """)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    # --- Event Handlers and UI Logic ---
    def open_directory(self):
        """Sets the root directory for the browser."""
        path = QFileDialog.getExistingDirectory(self, "Select Root Directory", QDir.homePath())
        if path:
            self.dir_tree.setRootIndex(self.dir_model.index(path))
            self._populate_file_list(path)

    def _on_directory_clicked(self, index):
        path = self.dir_model.filePath(index)
        self._populate_file_list(path)

    def _populate_file_list(self, path):
        """Populates the file list with supported audio files."""
        self.current_directory = path
        self.library_path_label.setText(path)
        self.library_path_label.setToolTip(path)
        self.file_list_widget.clear()
        self.clear_editor_fields()
        supported = ('.mp3', '.flac', '.m4a')
        try:
            for filename in sorted(os.listdir(path)):
                if filename.lower().endswith(supported):
                    full_path = os.path.join(path, filename)
                    item = QListWidgetItem(filename)
                    item.setData(Qt.ItemDataRole.UserRole, full_path)
                    self.file_list_widget.addItem(item)
            count = self.file_list_widget.count()
            self.file_count_label.setText(f"{count} track{'s' if count != 1 else ''}")
            self.statusBar().showMessage(f"Loaded directory: {path}")
        except OSError as e:
            self.file_count_label.setText("0 tracks")
            self.statusBar().showMessage(f"Cannot access directory: {e}")

    def on_selection_changed(self):
        """Handles changes in the file list selection."""
        self._store_current_draft()
        selected_items = self.file_list_widget.selectedItems()
        num_selected = len(selected_items)
        total = self.file_list_widget.count()
        if num_selected:
            self.file_count_label.setText(f"{num_selected} of {total} selected")
        else:
            self.file_count_label.setText(f"{total} track{'s' if total != 1 else ''}")

        self.fetch_button.setEnabled(num_selected > 0)
        self.revert_button.setEnabled(False)

        if num_selected == 0:
            self.active_selection_count = 0
            self.current_file_path = None
            self.clear_editor_fields()
            self.convert_button.setEnabled(False)
            return

        first_item = selected_items[0]
        self.current_file_path = first_item.data(Qt.ItemDataRole.UserRole)
        self.load_file_to_editor()

        is_all_flac = all(item.text().lower().endswith('.flac') for item in selected_items)
        is_all_m4a = all(item.text().lower().endswith('.m4a') for item in selected_items)
        self.convert_button.setEnabled(is_all_flac or is_all_m4a)

        if num_selected > 1:
            self.statusBar().showMessage(f"{num_selected} files selected. Editing common tags.")
            self._configure_multi_selection(selected_items)
            for label in self.info_labels.values():
                label.setText("---")
        else:
            self.multi_edit_fields.clear()
            for field in self.tag_fields.values():
                field.setEnabled(True)
        self.active_selection_count = num_selected

    def _configure_multi_selection(self, selected_items):
        """Show true common/mixed values and prepare fields for explicit bulk edits."""
        all_tags = []
        has_drafts = False
        for item in selected_items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self.tag_drafts:
                has_drafts = True
                all_tags.append(self.tag_drafts[path])
                continue
            try:
                all_tags.append(tag_manager.load_file_data(path)["tags"])
            except Exception:
                all_tags.append({})

        self.loading_editor = True
        self.multi_edit_fields.clear()
        for key, field in self.tag_fields.items():
            values = [str(tags.get(key, "")) for tags in all_tags]
            common_value = values[0] if values and all(value == values[0] for value in values) else None
            field.setPlaceholderText("")

            if key in ("title", "track"):
                field.setEnabled(False)
                field.setText(common_value if common_value is not None else "<Multiple Values>")
            else:
                field.setEnabled(True)
                if common_value is None:
                    field.clear()
                    field.setPlaceholderText("Multiple values — type to replace all")
                else:
                    field.setText(common_value)
        self.loading_editor = False
        self.revert_button.setEnabled(has_drafts)

    def clear_editor_fields(self, clear_path=True):
        """Clears all input fields and labels in the editor pane."""
        was_loading = self.loading_editor
        self.loading_editor = True
        for field in self.tag_fields.values(): field.clear()
        for label in self.info_labels.values(): label.setText("---")
        self.album_art_label.setText("Select a file to view its tags.")
        self.album_art_label.setPixmap(QPixmap())
        self.album_art_info_label.setText("No artwork selected")
        self._clear_staged_art()
        self.original_tags = {}
        self.revert_button.setEnabled(False)
        if clear_path: self.current_file_path = None
        self.loading_editor = was_loading

    def load_file_to_editor(self):
        """Loads data from the current file path into the UI fields."""
        if not self.current_file_path: return
        self.loading_editor = True
        try:
            self.clear_editor_fields(clear_path=False)
            data = tag_manager.load_file_data(self.current_file_path)
            if not data: return

            self.original_tags = data['tags']
            displayed_tags = self.tag_drafts.get(self.current_file_path, data['tags'])
            for key, value in displayed_tags.items():
                if key in self.tag_fields:
                    self.tag_fields[key].setText(str(value))

            for key, value in data['info'].items():
                if key in self.info_labels:
                    self.info_labels[key].setText(str(value))

            art_data = tag_manager.load_album_art_data(self.current_file_path)
            if art_data:
                pixmap = QPixmap()
                pixmap.loadFromData(art_data)
                self._show_square_artwork(pixmap)
                self.album_art_info_label.setText(
                    f"Embedded • {pixmap.width()} × {pixmap.height()} px • {self._format_bytes(len(art_data))}"
                )

            self.statusBar().showMessage(f"Loaded: {os.path.basename(self.current_file_path)}")
            self.revert_button.setEnabled(self.current_file_path in self.tag_drafts)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load file: {e}")
        finally:
            self.loading_editor = False

    def _current_field_values(self):
        return {key: field.text() for key, field in self.tag_fields.items() if field.isEnabled()}

    def _store_current_draft(self):
        """Keep unsaved single-track edits when the user changes selection."""
        if self.loading_editor or not self.current_file_path or self.active_selection_count != 1:
            return
        values = self._current_field_values()
        original = {key: str(self.original_tags.get(key, "")) for key in values}
        if values != original:
            self.tag_drafts[self.current_file_path] = values
        else:
            self.tag_drafts.pop(self.current_file_path, None)

    def _on_tag_edited(self):
        if self.loading_editor or not self.current_file_path:
            return
        if self.active_selection_count > 1:
            edited_widget = self.sender()
            for key, field in self.tag_fields.items():
                if field is edited_widget:
                    self.multi_edit_fields.add(key)
                    break
            self.revert_button.setEnabled(bool(self.multi_edit_fields))
            self.statusBar().showMessage(
                f"Bulk edit staged for {self.active_selection_count} selected tracks. Click Save Tags to apply."
            )
            return
        if self.active_selection_count != 1:
            return
        self.tag_drafts[self.current_file_path] = self._current_field_values()
        self.revert_button.setEnabled(True)
        self.statusBar().showMessage("Unsaved changes are kept while you review other tracks.")

    def change_album_art(self):
        """Opens a file dialog to select a new album art image."""
        if not self.file_list_widget.selectedItems():
            QMessageBox.warning(self, "Warning", "Please select one or more files first.")
            return
        if self.current_file_path:
            initial_directory = os.path.dirname(self.current_file_path)
        elif self.current_directory:
            initial_directory = self.current_directory
        else:
            initial_directory = QDir.homePath()

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Album Art",
            initial_directory,
            "Image Files (*.jpg *.jpeg *.png)",
        )
        if path:
            source_image = QImage(path)
            if source_image.isNull():
                return QMessageBox.warning(self, "Invalid Image", "The selected image could not be loaded.")

            original_width = source_image.width()
            original_height = source_image.height()
            side = min(original_width, original_height)
            square_image = source_image.copy(
                (original_width - side) // 2,
                (original_height - side) // 2,
                side,
                side,
            ).scaled(1000, 1000, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

            self._clear_staged_art()
            suffix = ".png" if path.lower().endswith(".png") else ".jpg"
            temp_file = tempfile.NamedTemporaryFile(prefix="music-tag-art-", suffix=suffix, delete=False)
            temp_file.close()
            quality = -1 if suffix == ".png" else 92
            if not square_image.save(temp_file.name, quality=quality):
                os.unlink(temp_file.name)
                return QMessageBox.warning(self, "Image Error", "The square artwork could not be prepared.")

            self.staged_art_temp_path = temp_file.name
            self.new_art_path = temp_file.name
            self._show_square_artwork(QPixmap.fromImage(square_image))
            self.album_art_info_label.setText(
                f"Original {original_width} × {original_height} px  →  Saved 1000 × 1000 px • "
                f"{self._format_bytes(os.path.getsize(temp_file.name))}"
            )
            self.statusBar().showMessage("Album art center-cropped to 1:1 and staged to be saved.")

    def _show_square_artwork(self, pixmap):
        """Display the complete centered square artwork without clipping or stretching."""
        if pixmap.isNull():
            return
        side = min(pixmap.width(), pixmap.height())
        square = pixmap.copy(
            (pixmap.width() - side) // 2,
            (pixmap.height() - side) // 2,
            side,
            side,
        )
        # Leave a small inset for the dashed frame. Scaling to the old hard-coded
        # 300 px size caused Qt to clip the image inside the label's padded area.
        preview_side = min(self.album_art_label.width(), self.album_art_label.height()) - 16
        preview = square.scaled(
            preview_side,
            preview_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        preview.setDevicePixelRatio(1.0)
        self.album_art_label.setPixmap(preview)

    def _clear_staged_art(self):
        if self.staged_art_temp_path and os.path.exists(self.staged_art_temp_path):
            try:
                os.unlink(self.staged_art_temp_path)
            except OSError:
                pass
        self.staged_art_temp_path = None
        self.new_art_path = None

    def closeEvent(self, event):
        self._clear_staged_art()
        super().closeEvent(event)

    @staticmethod
    def _format_bytes(size):
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def save_tags(self):
        """Saves the current tags from the UI to all selected files."""
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return QMessageBox.warning(self, "Warning", "No files selected.")

        paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        reply = QMessageBox.question(self, "Confirm Save", f"Apply tags to {len(paths)} files?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        self._store_current_draft()
        if len(paths) > 1:
            shared_tags = {key: self.tag_fields[key].text() for key in self.multi_edit_fields}
        else:
            shared_tags = self._current_field_values()

        progress = QProgressDialog("Saving tags...", "Cancel", 0, len(paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        success_count = 0
        save_errors = []
        for i, path in enumerate(paths):
            if progress.wasCanceled(): break
            progress.setValue(i)
            QApplication.processEvents()
            try:
                tags_to_save = dict(self.tag_drafts.get(path, {}))
                tags_to_save.update(shared_tags)
                tag_manager.save_file_tags(path, tags_to_save, self.new_art_path)
                self.tag_drafts.pop(path, None)
                success_count += 1
            except Exception as e:
                print(f"Failed to save {os.path.basename(path)}: {e}")
                save_errors.append(f"{os.path.basename(path)}: {e}")

        progress.setValue(len(paths))
        self._clear_staged_art()
        self.multi_edit_fields.clear()
        self.revert_button.setEnabled(False)
        if len(paths) == 1 and success_count == 1:
            self.load_file_to_editor()
        elif len(paths) > 1:
            self._configure_multi_selection(self.file_list_widget.selectedItems())
        if save_errors:
            error_preview = "\n".join(f"• {error}" for error in save_errors[:5])
            if len(save_errors) > 5:
                error_preview += f"\n• …and {len(save_errors) - 5} more"
            QMessageBox.warning(
                self,
                "Save Completed with Errors",
                f"Updated {success_count} of {len(paths)} files.\n\n{error_preview}",
            )
        else:
            QMessageBox.information(self, "Success", f"Successfully updated {success_count} of {len(paths)} files.")
        self.statusBar().showMessage(f"Successfully updated {success_count} of {len(paths)} files.")

    def rename_files(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return QMessageBox.warning(self, "Warning", "No files selected to rename.")

        format_string = self.rename_format_input.text()
        if not format_string: return QMessageBox.warning(self, "Warning", "Rename format cannot be empty.")

        reply = QMessageBox.question(self, "Confirm Rename", f"Rename {len(selected_items)} files?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        progress = QProgressDialog("Renaming files...", "Cancel", 0, len(selected_items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        success_count = 0
        for i, item in enumerate(selected_items):
            if progress.wasCanceled(): break
            progress.setValue(i)
            QApplication.processEvents()
            old_path = item.data(Qt.ItemDataRole.UserRole)
            try:
                new_path, new_filename = file_operations.rename_file(old_path, format_string)
                item.setText(new_filename)
                item.setData(Qt.ItemDataRole.UserRole, new_path)
                success_count += 1
            except Exception as e:
                print(f"Failed to rename {os.path.basename(old_path)}: {e}")

        progress.setValue(len(selected_items))
        self.file_list_widget.sortItems()
        QMessageBox.information(self, "Success", f"Renamed {success_count} of {len(selected_items)} files.")
        self.statusBar().showMessage(f"Renamed {success_count} of {len(selected_items)} files.")

    def rename_directory(self):
        if not self.current_directory or self.file_list_widget.count() == 0:
            return QMessageBox.warning(self, "Warning", "No directory or files are loaded.")

        format_string = self.rename_dir_format_input.text()
        if not format_string:
            return QMessageBox.warning(self, "Warning", "Directory rename format is empty.")

        try:
            all_paths = [self.file_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in
                         range(self.file_list_widget.count())]

            # Step 1: Calculate the new name without performing any action yet.
            new_dir_path, sanitized_name = file_operations.calculate_new_directory_name(
                self.current_directory, format_string, all_paths
            )

            if self.current_directory == new_dir_path:
                return QMessageBox.information(self, "Info", "Directory name is already correct.")

            # Step 2: Get user confirmation.
            reply = QMessageBox.question(self, "Confirm Rename",
                                         f"Rename directory to:\n\n{sanitized_name}\n\nAre you sure?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

            # --- CRITICAL SECTION ---
            # Step 3: Perform the actual rename on the disk.
            os.rename(self.current_directory, new_dir_path)

            # Step 4: Update ALL internal state to match the change.
            # Update the application's tracked current directory.
            self.current_directory = new_dir_path

            # Update the path data stored within each item in the file list.
            for i in range(self.file_list_widget.count()):
                item = self.file_list_widget.item(i)
                filename = os.path.basename(item.data(Qt.ItemDataRole.UserRole))
                new_file_path = os.path.join(new_dir_path, filename)
                item.setData(Qt.ItemDataRole.UserRole, new_file_path)

            # (THIS IS THE KEY FIX) Update the directory tree view on the left.
            # Find the model index of the newly renamed directory and set it as current.
            # This synchronizes the left pane with the file system change.
            new_dir_index = self.dir_model.index(new_dir_path)
            if new_dir_index.isValid():
                self.dir_tree.setCurrentIndex(new_dir_index)

            self.statusBar().showMessage(f"Directory renamed to: {sanitized_name}")
            QMessageBox.information(self, "Success", "Directory renamed successfully.")

        except ValueError as ve:
            QMessageBox.warning(self, "Validation Error", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename directory: {e}")
            self.statusBar().showMessage("Error renaming directory.")

    def convert_files(self):
        if not shutil.which("ffmpeg"):
            return QMessageBox.critical(self, "Error",
                                        "FFmpeg not found. Please install FFmpeg and add it to your system's PATH.")

        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return

        first_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if first_path.lower().endswith('.flac'):
            conversion_func, target_ext = file_operations.convert_flac_to_alac, '.m4a'
        elif first_path.lower().endswith('.m4a'):
            conversion_func, target_ext = file_operations.convert_alac_to_flac, '.flac'
        else:
            return

        reply = QMessageBox.question(self, "Confirm Conversion",
                                     f"Convert {len(selected_items)} files to {target_ext.upper()}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        backup_dir = os.path.join(self.current_directory, "backup")
        if self.backup_checkbox.isChecked(): os.makedirs(backup_dir, exist_ok=True)

        progress = QProgressDialog("Converting files...", "Cancel", 0, len(selected_items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        success_count = 0
        for i, item in enumerate(selected_items):
            if progress.wasCanceled(): break
            progress.setValue(i)
            QApplication.processEvents()

            source_path = item.data(Qt.ItemDataRole.UserRole)
            try:
                if self.backup_checkbox.isChecked():
                    backup_path = os.path.join(backup_dir, os.path.basename(source_path))
                    shutil.move(source_path, backup_path)
                    source_path = backup_path

                base_name = os.path.splitext(os.path.basename(source_path))[0]
                dest_path = os.path.join(self.current_directory, f"{base_name}{target_ext}")

                conversion_func(source_path, dest_path)

                if not self.backup_checkbox.isChecked(): os.remove(source_path)

                # --- CHANGE 1: These lines are no longer needed, so we remove them. ---
                # item.setText(os.path.basename(dest_path))
                # item.setData(Qt.ItemDataRole.UserRole, dest_path)
                success_count += 1
            except Exception as e:
                print(f"Failed to process {os.path.basename(source_path)}: {e}")

        progress.setValue(len(selected_items))

        # --- CHANGE 2: The old sortItems call is also removed. ---
        # self.file_list_widget.sortItems()

        QMessageBox.information(self, "Conversion Complete",
                                f"Successfully converted {success_count} of {len(selected_items)} files.")
        self.statusBar().showMessage(f"Converted {success_count} of {len(selected_items)} files.")

        # --- CHANGE 3: Add this line to refresh the entire file list from the directory. ---
        self._populate_file_list(self.current_directory)

    def fetch_metadata_start(self):
        if not get_gemini_api_key():
            reply = QMessageBox.question(
                self,
                "Gemini API Key Required",
                "No Gemini API key is configured. Open the secure credential settings now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.show_gemini_key_dialog()
            if not get_gemini_api_key():
                return
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items:
            return

        if len(selected_items) > 1:
            tracks = []
            skipped = []
            for item in selected_items:
                path = item.data(Qt.ItemDataRole.UserRole)
                try:
                    tags = self.tag_drafts.get(path) or tag_manager.load_file_data(path)["tags"]
                    title = tags.get("title", "").strip()
                    artist = tags.get("artist", "").strip()
                    if title and artist:
                        tracks.append({
                            "path": path,
                            "title": title,
                            "artist": artist,
                            "context": {
                                "album": tags.get("album", ""),
                                "year": tags.get("year", ""),
                                "filename": os.path.basename(path),
                            },
                        })
                    else:
                        skipped.append(os.path.basename(path))
                except Exception:
                    skipped.append(os.path.basename(path))

            if not tracks:
                return QMessageBox.warning(
                    self, "Metadata Missing",
                    "The selected files need existing title and artist tags before Gemini can search for them."
                )

            message = f"Search Gemini for metadata for {len(tracks)} tracks?"
            if skipped:
                message += f"\n\n{len(skipped)} track(s) without a title or artist will be skipped."
            message += "\n\nYou can review a summary before any tags are saved."
            reply = QMessageBox.question(
                self, "Fetch Smart Metadata", message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.progress = QProgressDialog(
                f"Searching Gemini for {len(tracks)} tracks...", None, 0, 0, self
            )
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.show()

            worker = Worker(metadata_fetcher.fetch_metadata_batch, tracks)
            worker.signals.result.connect(self.fetch_metadata_finish)
            worker.signals.error.connect(self.fetch_metadata_error)
            self.threadpool.start(worker)
            return

        if not self.current_file_path:
            return

        title = self.original_tags.get('title', '')
        artist = self.original_tags.get('artist', '')
        if not title or not artist:
            return QMessageBox.warning(self, "Warning", "File must have a title and artist to fetch metadata.")

        self.progress = QProgressDialog("Fetching metadata...", None, 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()

        worker = Worker(
            metadata_fetcher.fetch_metadata_from_api,
            title,
            artist,
            {
                "album": self.original_tags.get("album", ""),
                "year": self.original_tags.get("year", ""),
                "filename": os.path.basename(self.current_file_path),
            },
        )
        worker.signals.result.connect(self.fetch_metadata_finish)
        worker.signals.error.connect(self.fetch_metadata_error)
        self.threadpool.start(worker)

    def fetch_metadata_finish(self, fetched_data):
        self.progress.close()
        if not fetched_data:
            return QMessageBox.critical(self, "Error", "Failed to parse metadata from API.")

        if fetched_data.get("batch"):
            return self._finish_batch_metadata(fetched_data)

        for key, value in fetched_data.items():
            if key in self.tag_fields:
                clean_value = str(value).split('/')[0] if key in ("track", "disc") else str(value)
                self.tag_fields[key].setText(clean_value)

        self.revert_button.setEnabled(True)
        self.statusBar().showMessage("Metadata fetched. Review and save.")

    def _finish_batch_metadata(self, batch_data):
        results = batch_data.get("results", [])
        errors = batch_data.get("errors", [])
        if not results:
            return QMessageBox.critical(
                self, "Metadata Search Failed",
                f"Gemini could not find metadata for the selected tracks ({len(errors)} failed)."
            )

        preview_lines = []
        for result in results[:8]:
            metadata = result.get("metadata", {})
            title = metadata.get("title") or os.path.basename(result["path"])
            artist = metadata.get("artist", "")
            confidence = float(metadata.get("match_confidence", 0))
            preview_lines.append(
                f"• {title}" + (f" — {artist}" if artist else "") + f" ({confidence:.0%} match)"
            )
        if len(results) > 8:
            preview_lines.append(f"• …and {len(results) - 8} more")

        message = (
            f"Gemini found metadata for {len(results)} track(s).\n\n"
            + "\n".join(preview_lines)
        )
        if errors:
            message += f"\n\n{len(errors)} track(s) failed and will not be changed."
        message += "\n\nKeep these results as unsaved drafts for review?"

        reply = QMessageBox.question(
            self, "Review Smart Metadata", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Batch metadata results discarded. No files were changed.")
            return

        for result in results:
            clean_metadata = {
                key: (str(value).split("/")[0] if key in ("track", "disc") else str(value))
                for key, value in result.get("metadata", {}).items()
                if key in self.tag_fields and value is not None
            }
            self.tag_drafts[result["path"]] = clean_metadata

        selected_items = self.file_list_widget.selectedItems()
        if len(selected_items) > 1:
            self._configure_multi_selection(selected_items)
        elif self.current_file_path:
            self.load_file_to_editor()
        QMessageBox.information(
            self, "Smart Metadata Drafts Ready",
            f"Prepared unsaved metadata drafts for {len(results)} tracks. Review them and click Save Tags when ready."
        )
        self.revert_button.setEnabled(True)
        self.statusBar().showMessage(f"Smart metadata drafts ready for {len(results)} tracks. Nothing has been saved yet.")

    def fetch_metadata_error(self, err):
        self.progress.close()
        QMessageBox.critical(self, "Error", f"Failed to fetch metadata: {err[1]}")
        self.statusBar().showMessage("Error fetching metadata.")

    def revert_tag_changes(self):
        if self.active_selection_count > 1:
            for item in self.file_list_widget.selectedItems():
                path = item.data(Qt.ItemDataRole.UserRole)
                self.tag_drafts.pop(path, None)
            self.multi_edit_fields.clear()
            self._configure_multi_selection(self.file_list_widget.selectedItems())
            self.statusBar().showMessage("Bulk edits and Smart Metadata drafts reverted. No files were changed.")
            return
        if not self.original_tags or not self.current_file_path:
            return
        self.tag_drafts.pop(self.current_file_path, None)
        self.loading_editor = True
        for key, field in self.tag_fields.items():
            field.setText(str(self.original_tags.get(key, "")))
        self.loading_editor = False
        self.revert_button.setEnabled(False)
        self.statusBar().showMessage("Unsaved changes reverted to the last saved tags.")

    def update_artist_library(self):
        if not self.current_directory: return QMessageBox.warning(self, "Warning", "Please open a directory first.")

        mgr = artist_manager.ArtistManager(self.current_directory)
        added_count = mgr.update_library(
            self.tag_fields['artist'].text(),
            self.tag_fields['albumartist'].text()
        )
        if added_count > 0:
            QMessageBox.information(self, "Success", f"{added_count} new artist(s) added to the library.")
        else:
            QMessageBox.information(self, "Info", "All artist names already exist in the library.")

    def standardize_artist_names(self):
        if not self.current_directory: return QMessageBox.warning(self, "Warning", "Please open a directory first.")

        mgr = artist_manager.ArtistManager(self.current_directory)
        std_artist, std_album_artist = mgr.standardize_names(
            self.tag_fields['artist'].text(),
            self.tag_fields['albumartist'].text()
        )

        updated = False
        if std_artist and std_artist != self.tag_fields['artist'].text():
            self.tag_fields['artist'].setText(std_artist)
            updated = True
        if std_album_artist and std_album_artist != self.tag_fields['albumartist'].text():
            self.tag_fields['albumartist'].setText(std_album_artist)
            updated = True

        if updated:
            QMessageBox.information(self, "Success", "Artist names have been standardized.")
        else:
            QMessageBox.information(self, "Info", "Artist names are already standard or not in the library.")
