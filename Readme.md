# Music Tag Editor

Music Tag Editor is a desktop application for viewing and editing metadata in MP3, FLAC, and M4A music files. It is built with Python and PySide6.

The application can:

- Edit title, artist, album, album artist, composer, genre, year, track, disc, and comment tags.
- Edit one file or apply shared tags and album art to multiple files.
- Display audio information such as quality, duration, format, bitrate, sample rate, and file size.
- Rename files and album directories using tag-based formats.
- Convert FLAC to ALAC and ALAC to FLAC with FFmpeg.
- Fetch suggested metadata with Gemini AI and Google Search grounding.
- Maintain a local artist-name library for consistent naming.

## Requirements

- Python 3.10 or newer
- FFmpeg available on `PATH` for FLAC/ALAC conversion
- A Gemini API key if you want to use **Fetch Data**

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For audio conversion, install FFmpeg and confirm that it is available:

```bash
ffmpeg -version
```

## Gemini API configuration

Gemini is optional. The editor works without it, but the metadata-fetching feature will be disabled.

### Configure securely inside the app

Open **Tools > Configure Gemini API Key...**, or select **Configure Gemini API Key...** under Smart Metadata. Paste the key and choose **Save Securely**.

The app stores the credential using the operating system's protected credential store:

- macOS: Keychain
- Windows: Credential Manager
- Linux: the available system keyring backend

The saved key is masked and is never displayed again by the application. You can remove it from the same dialog.

### Environment or `.env` configuration

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and add your key:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

You can create a key in [Google AI Studio](https://aistudio.google.com/app/apikey). The `.env` file is ignored by Git and should not be committed.

`GEMINI_API_KEY` from the operating-system environment or `.env` takes precedence over a key saved in the credential store.

## Run the project

Activate the virtual environment, then run:

```bash
python main.py
```

## Debug the project

Run Python in development mode to show additional runtime warnings:

```bash
python -X dev main.py
```

To stop at the first line and debug interactively with Python's built-in debugger:

```bash
python -m pdb main.py
```

Useful debugger commands are `n` (next line), `s` (step into), `c` (continue), `p expression` (print a value), and `q` (quit). Application and Gemini API errors are also printed to the terminal, so start the app from a terminal while investigating a problem.

## How to use

1. Start the application with `python main.py`.
2. Select **File > Set Browser Root...** and choose the root of your music library.
3. Select a directory in the left browser. Supported MP3, FLAC, and M4A files appear below it.
4. Select one or more audio files to view their current tags and audio details.
5. Edit the tag fields or choose **Change Album Art**.
6. Select **Save Tags**, review the confirmation, and save the changes.

When multiple files are selected, shared fields can be applied in bulk. Title and track are disabled to avoid accidentally assigning the same values to every selected file.

### Fetch metadata with Gemini

1. Configure `GEMINI_API_KEY` in `.env`.
2. Select one file that already has a title and artist.
3. Select **Fetch Data**.
4. Review the suggested metadata.
5. Select **Save Tags** to write it, or **Revert Changes** to discard the suggestion.

### Rename files and directories

File rename formats use placeholders such as:

```text
{track} - {title}
```

Available file placeholders include `{title}`, `{artist}`, `{album}`, `{albumartist}`, `{composer}`, `{genre}`, `{year}`, `{track}`, `{disc}`, and `{comment}`.

Directory rename formats support `{quality}`, `{albumartist}`, `{album}`, `{genre}`, and `{year}`. All files in the directory must have the same album and album artist.

### Convert FLAC and ALAC

1. Make sure FFmpeg is installed and available on `PATH`.
2. Select only FLAC files or only M4A/ALAC files.
3. Leave **Backup original file before converting** enabled if you want the originals moved into a `backup` directory.
4. Select **Convert FLAC <-> ALAC** and confirm.

## Export a macOS application

Build the standalone `.app` bundle with PyInstaller from macOS.

1. Activate the virtual environment and install the project dependencies:

   ```bash
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. Confirm that the icon and FFmpeg binary exist and that FFmpeg is executable:

   ```bash
   ls -l icon.icns ffmpeg
   chmod +x ffmpeg
   ```

3. Export the application and bundle FFmpeg inside it:

   ```bash
   pyinstaller --windowed --name="Music Tag Editor" --icon="icon.icns" --add-binary="ffmpeg:." main.py
   ```

4. The exported application will be available at:

   ```text
   dist/Music Tag Editor.app
   ```

5. Test the exported application:

   ```bash
   open "dist/Music Tag Editor.app"
   ```

To build the app without bundling FFmpeg, use:

```bash
pyinstaller --windowed --name="Music Tag Editor" --icon="icon.icns" main.py
```

That version requires FFmpeg to be installed separately and available on the user's `PATH`.

### Build with the specification file

The included `Music Tag Editor.spec` can also be used:

```bash
pyinstaller "Music Tag Editor.spec"
```

The specification currently expects Homebrew FFmpeg at `/opt/homebrew/bin/ffmpeg`. Update its `binaries` path if FFmpeg is installed elsewhere. PyInstaller creates intermediate files under `build/` and places the distributable application under `dist/`.

## Important

Tag editing, renaming, and conversion modify files on disk. Keep backups of important music files, especially before using bulk operations.
