import os
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QFrame, QAbstractItemView, QCheckBox, QProgressDialog,
    QTreeView, QFileSystemModel, QSplitter
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
        self.setGeometry(100, 200, 1000, 700)

        # State variables
        self.current_file_path = None
        self.new_art_path = None
        self.current_directory = None
        self.original_tags = {}
        self.threadpool = QThreadPool()

        self._create_menu_bar()
        self._create_widgets()
        self._create_layouts()

        self.statusBar().showMessage("Ready. Select a root directory for the browser.")

    def show_about_dialog(self):
        """Displays the application's About box."""
        QMessageBox.about(
            self,
            "About Music Tag Editor",
            "<h2>Music Tag Editor</h2>"
            "<p>Version 1.0.0 build 20251013</p>"
            "<p>This application allows you to edit the metadata of your music files.</p>"
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

        # --- File List ---
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list_widget.itemSelectionChanged.connect(self.on_selection_changed)

        # --- Album Art and Tools ---
        self.album_art_label = QLabel("Select a directory to start.")
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art_label.setFixedSize(300, 300)
        self.album_art_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
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
        self.save_button.setMinimumHeight(60)
        self.save_button.clicked.connect(self.save_tags)

    def _create_layouts(self):
        # --- Left Pane (Directory and File lists) ---
        file_list_container = QWidget()
        file_list_layout = QVBoxLayout(file_list_container)

        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.addWidget(QLabel("WORKSPACE - File(s) Selected"))
        file_list_layout.addWidget(self.file_list_widget)

        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.addWidget(self.dir_tree)
        left_splitter.addWidget(file_list_container)
        left_splitter.setSizes([250, 400])

        # --- Right Pane (Editor) ---
        # Art and tools sub-pane
        art_tools_container = QWidget()
        art_tools_container.setFixedWidth(320)

        art_layout = QVBoxLayout(art_tools_container)
        art_layout.addWidget(QLabel("ALBUM ART COVER"))
        art_layout.addWidget(self.album_art_label, alignment=Qt.AlignmentFlag.AlignCenter)
        art_layout.addWidget(self.change_art_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(QLabel("FILE OPERATION"))
        art_layout.addWidget(QLabel("Rename File Format:"))
        art_layout.addWidget(self.rename_format_input)
        art_layout.addWidget(self.rename_button)
        # art_layout.addWidget(self._create_separator())
        art_layout.addWidget(QLabel("Rename Directory Format:"))
        art_layout.addWidget(self.rename_dir_format_input)
        art_layout.addWidget(self.rename_dir_button)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(QLabel("LOAD METADATA (Gemini AI)"))
        fetch_layout = QHBoxLayout()
        fetch_layout.addWidget(self.fetch_button)
        fetch_layout.addWidget(self.revert_button)
        art_layout.addLayout(fetch_layout)
        art_layout.addWidget(self._create_separator())
        art_layout.addWidget(QLabel("ARTIST MANAGEMENT"))
        artist_mgmt_layout = QHBoxLayout()
        artist_mgmt_layout.addWidget(self.update_artists_button)
        artist_mgmt_layout.addWidget(self.standardize_artists_button)
        art_layout.addLayout(artist_mgmt_layout)
        art_layout.addStretch()

        # Fields sub-pane
        fields_pane_layout = QVBoxLayout()
        fields_pane_layout.addWidget(QLabel("METADATA EDITABLE"))
        self.editable_fields_layout = QGridLayout()
        for i, (key, widget) in enumerate(self.tag_fields.items()):
            label_text = key.replace("albumartist", "album artist").capitalize()
            self.editable_fields_layout.addWidget(QLabel(f"{label_text}:"), i, 0)
            self.editable_fields_layout.addWidget(widget, i, 1)

        self.info_fields_layout = QGridLayout()
        for i, (key, widget) in enumerate(self.info_labels.items()):
            label_text = key.replace("samplerate", "sample rate").replace("filesize", "file size").capitalize()
            self.info_fields_layout.addWidget(QLabel(f"{label_text}:"), i, 0)
            self.info_fields_layout.addWidget(widget, i, 1)

        fields_pane_layout.addLayout(self.editable_fields_layout)
        fields_pane_layout.addWidget(self._create_separator())
        fields_pane_layout.addWidget(QLabel("TRACK INFORMATION"))
        fields_pane_layout.addLayout(self.info_fields_layout)

        # --- THIS IS THE CORRECTED SECTION ---
        # The Tools are now added here, after the file info and before the stretch.
        fields_pane_layout.addWidget(self._create_separator())
        fields_pane_layout.addWidget(QLabel("FILE CONVERTER\n Support external using ffmpeg\n for Apple Lossless"))
        fields_pane_layout.addWidget(self.convert_button)
        fields_pane_layout.addWidget(self.backup_checkbox)
        # --- END OF CORRECTION ---

        fields_pane_layout.addStretch()
        fields_pane_layout.addWidget(self.save_button)

        editor_pane_layout = QHBoxLayout()
        editor_pane_layout.addWidget(art_tools_container)
        editor_pane_layout.addLayout(fields_pane_layout)

        # --- Main Layout ---
        main_layout = QHBoxLayout()
        main_layout.addWidget(left_splitter, 1)
        main_layout.addLayout(editor_pane_layout, 2)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

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
            self.statusBar().showMessage(f"Loaded directory: {path}")
        except OSError as e:
            self.statusBar().showMessage(f"Cannot access directory: {e}")

    def on_selection_changed(self):
        """Handles changes in the file list selection."""
        selected_items = self.file_list_widget.selectedItems()
        num_selected = len(selected_items)

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
