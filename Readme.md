# Music Tag Editor

Music Tag Editor is a desktop application for viewing and editing metadata in MP3, FLAC, and M4A music files. It is built with Python and PySide6.

The application can:

- Edit title, artist, album, album artist, composer, genre, year, track, disc, and comment tags.
- Keep unsaved per-track drafts while reviewing other tracks.
- Apply only intentionally edited fields to multiple selected files.
- Display audio information such as quality, duration, format, bitrate, sample rate, and file size.
- Preview artwork dimensions and file size, and prepare new covers as centered `1000 × 1000` images.
- Rename files and album directories using tag-based formats.
- Convert FLAC to ALAC and ALAC to FLAC with FFmpeg.
- Fetch one or many metadata suggestions with Gemini AI and Google Search grounding.
- Validate Gemini matches by title, artist, recording version, release consistency, sources, and confidence.
- Store the Gemini API key securely in macOS Keychain or Windows Credential Manager.
- Maintain a local artist-name library for consistent naming.

## Requirements

- Python 3.10 or newer
- FFmpeg available on `PATH` for FLAC/ALAC conversion
- A Gemini API key if you want to use **Fetch Smart Metadata**

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

On macOS, you can inspect the saved item in **Keychain Access** by searching for `Music Tag Editor`. Its account name is `GEMINI_API_KEY`.

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

You can also set it for the current terminal session before launching the app:

```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
python main.py
```

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
python main.py
```

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
2. Select **Choose Music Folder** or **File > Open Music Folder...** and choose the root of your music library.
3. Select a directory in the left browser. Supported MP3, FLAC, and M4A files appear below it.
4. Select one or more audio files to view their current tags and audio details.
5. Edit the tag fields or choose **Change Album Art**.
6. Select **Save Tags**, review the confirmation, and save the changes.

The bottom action bar keeps **Revert Changes** and **Save Tags** available while the metadata panel scrolls.

### Review tracks without losing edits

1. Select one track and edit its metadata.
2. Select another track without saving the first one.
3. Return to the first track; its unsaved draft is restored.
4. Select **Save Tags** to write the selected track's draft.
5. Select **Revert Changes** to discard that track's draft and reload its saved tags.

Drafts remain in memory only while the application is running.

### Edit multiple tracks

1. Select multiple tracks with `Command` on macOS or `Ctrl` on Windows/Linux. Use `Shift` to select a range.
2. Fields shared by every selected track display their common value.
3. Mixed fields display **Multiple values — type to replace all**.
4. Enter a new value only in fields you want to apply to every selected track.
5. Select **Save Tags** to apply those intentional bulk changes.

Only fields changed during the multi-selection are applied to all selected tracks. Title and track number remain protected from bulk replacement. **Revert Changes** discards staged bulk edits and Smart Metadata drafts for the selected tracks.

### Fetch metadata with Gemini

1. Configure the key with **Tools > Configure Gemini API Key...**, the Smart Metadata setup button, an OS environment variable, or `.env`.
2. Select one or more files that already have title and artist tags.
3. Select **Fetch Smart Metadata**.
4. Gemini searches all selected tracks in one request and validates each match independently.
5. Review the title, artist, and confidence summary.
6. Accept the results to keep them as unsaved per-track drafts. No files are changed yet.
7. Review individual tracks or make additional bulk edits.
8. Select **Save Tags** to write the drafts, or **Revert Changes** to discard them.

Files without an existing title or artist are skipped. Ambiguous or low-confidence matches are rejected instead of being silently applied. Source URLs are saved in the Comment tag when the results are accepted and saved.

The free Gemini tier may enforce request or token limits. If the API returns `429 RESOURCE_EXHAUSTED`, wait for the requested retry period or check the project's usage and rate limits in Google AI Studio.

### Change album artwork

1. Select one or more tracks.
2. Select **Change Album Art**. The picker opens in the selected track's directory.
3. Choose a JPEG or PNG image.
4. The app displays the original dimensions and prepares a centered square cover at `1000 × 1000` pixels.
5. Review the complete 1:1 preview and select **Save Tags** to embed it.

When multiple tracks are selected, the prepared cover is applied to all of them. The original source image is not modified.

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
3. Leave **Keep original files in a backup folder** enabled if you want the originals moved into a `backup` directory.
4. Select **Convert Selected FLAC ↔ ALAC** and confirm.

## Menus and shortcuts

- **File > Open Music Folder...** — `Command/Ctrl + O`
- **File > Save Tags** — `Command/Ctrl + S`
- **Edit > Revert Unsaved Changes** — `Command/Ctrl + Z`
- **Tools > Fetch Smart Metadata**
- **Tools > Configure Gemini API Key...**
- **Tools > Change Album Artwork...**
- **Help > About Music Tag Editor** — includes a quick-start guide

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
   python -m PyInstaller --windowed --name="Music Tag Editor" --icon="icon.icns" --add-binary="ffmpeg:." main.py
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
python -m PyInstaller --windowed --name="Music Tag Editor" --icon="icon.icns" main.py
```

That version requires FFmpeg to be installed separately and available on the user's `PATH`.

### Build with the specification file

The included `Music Tag Editor.spec` can also be used:

```bash
python -m PyInstaller --clean --noconfirm "Music Tag Editor.spec"
```

Always run PyInstaller through the activated project environment as shown above. This prevents a globally installed or unrelated virtual-environment copy of PyInstaller from producing a bundle with missing dependencies. The specification bundles the project's `ffmpeg` binary and explicitly collects the dotenv and OS-keyring modules. PyInstaller creates intermediate files under `build/` and places the distributable application under `dist/`.

## Important

Tag editing, renaming, and conversion modify files on disk. Keep backups of important music files, especially before using bulk operations.
