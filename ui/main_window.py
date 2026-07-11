import os
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QFrame, QAbstractItemView, QCheckBox, QProgressDialog,
    QTreeView, QFileSystemModel, QSplitter, QScrollArea, QSizePolicy
)
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, QDir, QThreadPool

# App-specific imports
from config import GEMINI_API_KEY
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
        self.current_directory = None
        self.original_tags = {}
        self.threadpool = QThreadPool()

        self._create_menu_bar()
        self._create_widgets()
        self._create_layouts()
        self._apply_theme()

        self.statusBar().showMessage("Ready. Select a root directory for the browser.")

    def show_about_dialog(self):
        """Displays the application's About box."""
        QMessageBox.about(
            self,
            "About Music Tag Editor",
            "<h2>Music Tag Editor</h2>"
            "<p><b>Version 1.0.0 build 20251013</b></p>"
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
            "<li><b>Fetch Data:</b> suggest metadata using Gemini AI.</li>"
            "<li><b>File Naming:</b> rename tracks or folders from tag patterns.</li>"
            "<li><b>Audio Conversion:</b> convert FLAC and ALAC using FFmpeg.</li>"
            "</ul>"
            "<p><i>Tip: Keep backups before editing or converting multiple files.</i></p>"
            "<hr>"
            "<p>Copyright ©2025 Bokie Tarathep. All rights reserved.</p>"
        )

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Set Browser Root...", self)
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        # This role ensures it integrates correctly (e.g., "Quit" on macOS)
        exit_action.setMenuRole(QAction.MenuRole.QuitRole)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

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
        self.file_count_label = QLabel("0 tracks")
        self.file_count_label.setObjectName("countLabel")

        # --- Album Art and Tools ---
        self.album_art_label = QLabel("Select a directory to start.")
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art_label.setMinimumSize(220, 220)
        self.album_art_label.setMaximumSize(300, 300)
        self.album_art_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.album_art_label.setObjectName("albumArt")
        self.change_art_button = QPushButton("Change Album Art")
        self.change_art_button.clicked.connect(self.change_album_art)

        # --- Renaming ---
        self.rename_format_input = QLineEdit("{track} - {title}")
        self.rename_button = QPushButton("Rename Selected Files")
        self.rename_button.clicked.connect(self.rename_files)
        self.rename_dir_format_input = QLineEdit("[{quality}] {albumartist} - {album}")
        self.rename_dir_button = QPushButton("Rename Directory")
        self.rename_dir_button.clicked.connect(self.rename_directory)

        # --- Online Tools ---
        self.fetch_button = QPushButton("Fetch Data")
        self.fetch_button.clicked.connect(self.fetch_metadata_start)
        self.fetch_button.setEnabled(False)
        self.revert_button = QPushButton("Revert Changes")
        self.revert_button.clicked.connect(self.revert_tag_changes)
        self.revert_button.setEnabled(False)

        # --- Artist Management ---
        self.update_artists_button = QPushButton("Update Artist Library")
        self.update_artists_button.clicked.connect(self.update_artist_library)
        self.standardize_artists_button = QPushButton("Update Artist Name")
        self.standardize_artists_button.clicked.connect(self.standardize_artist_names)

        # --- Tag Fields ---
        self.tag_fields = {}
        tags_to_edit = ["Title", "Artist", "Album", "Album Artist", "Composer",
                        "Genre", "Year", "Track", "Disc", "Comment"]
        for tag_name in tags_to_edit:
            self.tag_fields[tag_name.lower().replace(" ", "")] = QLineEdit()

        # --- Info Labels ---
        self.info_labels = {}
        info_to_show = ["Quality", "Duration", "Format", "Bitrate", "Sample Rate", "File Size"]
        for info_name in info_to_show:
            self.info_labels[info_name.lower().replace(" ", "")] = QLabel("---")

        # --- Conversion Tools ---
        self.convert_button = QPushButton("Convert FLAC <-> ALAC")
        self.convert_button.clicked.connect(self.convert_files)
        self.convert_button.setEnabled(False)
        self.backup_checkbox = QCheckBox("Backup original file before converting")
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
        art_layout.addWidget(self.change_art_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("File Naming"))
        art_layout.addWidget(QLabel("File name pattern"))
        art_layout.addWidget(self.rename_format_input)
        art_layout.addWidget(self.rename_button)
        art_layout.addWidget(QLabel("Folder name pattern"))
        art_layout.addWidget(self.rename_dir_format_input)
        art_layout.addWidget(self.rename_dir_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("Smart Metadata", "Suggestions powered by Gemini AI"))
        fetch_layout = QHBoxLayout()
        fetch_layout.addWidget(self.fetch_button)
        fetch_layout.addWidget(self.revert_button)
        art_layout.addLayout(fetch_layout)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(self._section_label("Artist Names"))
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
        self.editable_fields_layout.setColumnStretch(1, 1)
        for i, (key, widget) in enumerate(self.tag_fields.items()):
            label_text = key.replace("albumartist", "album artist").capitalize()
            self.editable_fields_layout.addWidget(QLabel(f"{label_text}:"), i, 0)
            self.editable_fields_layout.addWidget(widget, i, 1)

        self.info_fields_layout = QGridLayout()
        self.info_fields_layout.setHorizontalSpacing(18)
        self.info_fields_layout.setVerticalSpacing(8)
        self.info_fields_layout.setColumnStretch(1, 1)
        for i, (key, widget) in enumerate(self.info_labels.items()):
            label_text = key.replace("samplerate", "sample rate").replace("filesize", "file size").capitalize()
            self.info_fields_layout.addWidget(QLabel(f"{label_text}:"), i, 0)
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
        metadata_layout.addWidget(self.save_button)

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

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f3fa; color: #27223a; font-size: 14px; }
            QFrame#panel { background: #ffffff; border: 1px solid #ddd8e9; border-radius: 12px; }
            QScrollArea#panelScroll, QScrollArea#panelScroll > QWidget > QWidget { background: transparent; }
            QLabel#sectionTitle { font-size: 17px; font-weight: 700; color: #31294f; }
            QLabel#mutedLabel { color: #756d89; font-size: 12px; }
            QLabel#countLabel { color: #44366f; background: #ece7f7; border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 600; }
            QLabel#albumArt { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f2eff9, stop:1 #e9e3f4); border: 1px dashed #afa5c8; border-radius: 10px; color: #716889; padding: 12px; }
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
        selected_items = self.file_list_widget.selectedItems()
        num_selected = len(selected_items)
        total = self.file_list_widget.count()
        if num_selected:
            self.file_count_label.setText(f"{num_selected} of {total} selected")
        else:
            self.file_count_label.setText(f"{total} track{'s' if total != 1 else ''}")

        self.fetch_button.setEnabled(num_selected == 1)
        self.revert_button.setEnabled(False)

        if num_selected == 0:
            self.current_file_path = None
            self.clear_editor_fields()
            self.convert_button.setEnabled(False)
            return

        first_item = selected_items[0]
        self.current_file_path = first_item.data(Qt.ItemDataRole.UserRole)
        self.new_art_path = None
        self.load_file_to_editor()

        is_all_flac = all(item.text().lower().endswith('.flac') for item in selected_items)
        is_all_m4a = all(item.text().lower().endswith('.m4a') for item in selected_items)
        self.convert_button.setEnabled(is_all_flac or is_all_m4a)

        if num_selected > 1:
            self.statusBar().showMessage(f"{num_selected} files selected. Editing common tags.")
            for key, field in self.tag_fields.items():
                is_disabled = key in ['title', 'track']
                field.setText("<Multiple Values>" if is_disabled else field.text())
                field.setEnabled(not is_disabled)
            for label in self.info_labels.values():
                label.setText("---")
        else:
            for field in self.tag_fields.values():
                field.setEnabled(True)

    def clear_editor_fields(self, clear_path=True):
        """Clears all input fields and labels in the editor pane."""
        for field in self.tag_fields.values(): field.clear()
        for label in self.info_labels.values(): label.setText("---")
        self.album_art_label.setText("Select a file to view its tags.")
        self.album_art_label.setPixmap(QPixmap())
        self.new_art_path = None
        self.original_tags = {}
        self.revert_button.setEnabled(False)
        if clear_path: self.current_file_path = None

    def load_file_to_editor(self):
        """Loads data from the current file path into the UI fields."""
        if not self.current_file_path: return
        try:
            self.clear_editor_fields(clear_path=False)
            data = tag_manager.load_file_data(self.current_file_path)
            if not data: return

            self.original_tags = data['tags']
            for key, value in data['tags'].items():
                if key in self.tag_fields:
                    self.tag_fields[key].setText(str(value))

            for key, value in data['info'].items():
                if key in self.info_labels:
                    self.info_labels[key].setText(str(value))

            art_data = tag_manager.load_album_art_data(self.current_file_path)
            if art_data:
                pixmap = QPixmap()
                pixmap.loadFromData(art_data)
                self.album_art_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            self.statusBar().showMessage(f"Loaded: {os.path.basename(self.current_file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load file: {e}")

    def change_album_art(self):
        """Opens a file dialog to select a new album art image."""
        if not self.file_list_widget.selectedItems():
            QMessageBox.warning(self, "Warning", "Please select one or more files first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Album Art", "", "Image Files (*.jpg *.jpeg *.png)")
        if path:
            self.new_art_path = path
            pixmap = QPixmap(path)
            self.album_art_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.statusBar().showMessage("Album art staged to be saved.")

    def save_tags(self):
        """Saves the current tags from the UI to all selected files."""
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return QMessageBox.warning(self, "Warning", "No files selected.")

        paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        reply = QMessageBox.question(self, "Confirm Save", f"Apply tags to {len(paths)} files?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        tags_to_save = {}
        for key, field in self.tag_fields.items():
            if field.isEnabled():
                tags_to_save[key] = field.text()

        progress = QProgressDialog("Saving tags...", "Cancel", 0, len(paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        success_count = 0
        for i, path in enumerate(paths):
            if progress.wasCanceled(): break
            progress.setValue(i)
            QApplication.processEvents()
            try:
                tag_manager.save_file_tags(path, tags_to_save, self.new_art_path)
                success_count += 1
            except Exception as e:
                print(f"Failed to save {os.path.basename(path)}: {e}")

        progress.setValue(len(paths))
        self.new_art_path = None
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
        if not GEMINI_API_KEY:
            return QMessageBox.warning(self, "API Key Missing",
                                       "Please set GEMINI_API_KEY in the project's .env file to use this feature.")
        if not self.current_file_path: return

        title = self.original_tags.get('title', '')
        artist = self.original_tags.get('artist', '')
        if not title or not artist:
            return QMessageBox.warning(self, "Warning", "File must have a title and artist to fetch metadata.")

        self.progress = QProgressDialog("Fetching metadata...", None, 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()

        worker = Worker(metadata_fetcher.fetch_metadata_from_api, title, artist)
        worker.signals.result.connect(self.fetch_metadata_finish)
        worker.signals.error.connect(self.fetch_metadata_error)
        self.threadpool.start(worker)

    def fetch_metadata_finish(self, fetched_data):
        self.progress.close()
        if not fetched_data:
            return QMessageBox.critical(self, "Error", "Failed to parse metadata from API.")

        for key, value in fetched_data.items():
            if key in self.tag_fields:
                clean_value = str(value).split('/')[0]
                self.tag_fields[key].setText(clean_value)

        self.revert_button.setEnabled(True)
        self.statusBar().showMessage("Metadata fetched. Review and save.")

    def fetch_metadata_error(self, err):
        self.progress.close()
        QMessageBox.critical(self, "Error", f"Failed to fetch metadata: {err[1]}")
        self.statusBar().showMessage("Error fetching metadata.")

    def revert_tag_changes(self):
        if not self.original_tags: return
        for key, value in self.original_tags.items():
            if key in self.tag_fields:
                self.tag_fields[key].setText(str(value))
        self.revert_button.setEnabled(False)
        self.statusBar().showMessage("Changes reverted.")

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
