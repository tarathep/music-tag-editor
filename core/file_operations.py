import os
import re
import subprocess
import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from . import tag_manager


def rename_file(old_path, format_string):
    """Renames a single file based on its tags and a format string."""
    audio = mutagen.File(old_path, easy=True)
    if audio is None:
        raise ValueError("Unsupported file format for renaming.")

    tags = {
        'title': audio.get("title", [""])[0], 'artist': audio.get("artist", [""])[0],
        'album': audio.get("album", [""])[0], 'albumartist': audio.get("albumartist", [""])[0],
        'composer': audio.get("composer", [""])[0], 'genre': audio.get("genre", [""])[0],
        'year': audio.get("date", [""])[0],
        'track': audio.get("tracknumber", ["0"])[0].split('/')[0].zfill(2),
        'disc': audio.get("discnumber", ["0"])[0].split('/')[0].zfill(2),
        'comment': audio.get("comment", [""])[0],
    }

    new_name_part = format_string
    for key, value in tags.items():
        new_name_part = new_name_part.replace(f'{{{key}}}', str(value))

    sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", new_name_part)
    directory = os.path.dirname(old_path)
    extension = os.path.splitext(old_path)[1]
    new_filename = f"{sanitized_name}{extension}"
    new_path = os.path.join(directory, new_filename)

    if old_path != new_path:
        os.rename(old_path, new_path)

    return new_path, new_filename

def convert_alac_to_flac(source_path, dest_path):
    """Converts a single ALAC to FLAC and copies tags."""
    command = ['ffmpeg', '-y', '-i', source_path, '-vn', '-c:a', 'flac', dest_path]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    source_mp4 = MP4(source_path)
    dest_flac = FLAC(dest_path)
    dest_flac.add_tags()

    tag_map = {
        '\xa9nam': 'TITLE', '\xa9ART': 'ARTIST', '\xa9alb': 'ALBUM',
        'aART': 'ALBUMARTIST', '\xa9wrt': 'COMPOSER', '\xa9gen': 'GENRE',
        '\xa9day': 'DATE', 'trkn': 'TRACKNUMBER', 'disk': 'DISCNUMBER',
        '\xa9cmt': 'COMMENT'
    }
    for mp4_key, value in source_mp4.tags.items():
        flac_key = tag_map.get(mp4_key)
        if flac_key:
            if flac_key in ['TRACKNUMBER', 'DISCNUMBER']:
                num, total = value[0]
                dest_flac[flac_key] = f"{num}/{total}" if total else str(num)
            else:
                dest_flac[flac_key] = value[0]

    if 'covr' in source_mp4.tags and source_mp4.tags['covr']:
        pic_data = source_mp4.tags['covr'][0]
        pic = Picture()
        pic.data = pic_data
        pic.type = 3
        pic.mime = 'image/jpeg' if pic_data.imageformat == MP4Cover.FORMAT_JPEG else 'image/png'
        dest_flac.add_picture(pic)

    dest_flac.save()


def convert_flac_to_alac(source_path, dest_path):
    """
    Converts a FLAC to ALAC, using a specific FFmpeg command to ensure
    all tags and the album art are correctly copied.
    """
    command = [
        'ffmpeg',
        '-y',                         # Overwrite output file if it exists
        '-i', source_path,            # Input file
        '-c:a', 'alac',               # Set the audio codec to ALAC
        '-map', '0:a',                # Explicitly map the audio stream from the first input
        '-map', '0:v?',               # **Crucial**: Map the video stream (album art) IF it exists
        '-c:v', 'copy',               # Copy the video stream (album art) without re-encoding
        '-disposition:v', 'attached_pic', # **Crucial**: Mark the video stream as the cover art
        dest_path                     # Output file
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def calculate_new_directory_name(current_dir, format_string, all_file_paths):
    """Calculates the prospective new directory name based on tags without renaming."""
    if not all_file_paths:
        raise ValueError("No files in directory to determine new name.")

    first_audio = mutagen.File(all_file_paths[0], easy=True)
    base_album = first_audio.get('album', [''])[0]
    base_albumartist = first_audio.get('albumartist', [''])[0]

    for path in all_file_paths[1:]:
        audio = mutagen.File(path, easy=True)
        if audio.get('album', [''])[0] != base_album or audio.get('albumartist', [''])[0] != base_albumartist:
            raise ValueError("All files must have the same Album and Album Artist to rename directory.")

    quality_levels = {"Lossy": 0, "Lossless": 1, "Hi-Res": 2, "Unknown": -1}
    min_quality = "Hi-Res"
    for path in all_file_paths:
        current_quality = tag_manager.get_file_quality(path)
        if quality_levels.get(current_quality, -1) < quality_levels.get(min_quality, -1):
            min_quality = current_quality

    tags = {
        'quality': min_quality, 'albumartist': base_albumartist, 'album': base_album,
        'genre': first_audio.get('genre', [''])[0], 'year': first_audio.get('date', [''])[0]
    }

    new_name_part = format_string
    for key, value in tags.items():
        new_name_part = new_name_part.replace(f'{{{key}}}', str(value))

    sanitized_name = re.sub(r'[\\/*?:"<>|]', "_", new_name_part)
    parent_dir = os.path.dirname(current_dir)
    new_dir_path = os.path.join(parent_dir, sanitized_name)

    return new_dir_path, sanitized_name