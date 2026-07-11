import os
import datetime
import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.id3 import APIC
from mutagen.mp4 import MP4, MP4Cover


def get_file_quality(file_path):
    """Determines the quality of a single audio file."""
    try:
        audio_info = mutagen.File(file_path).info
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == '.flac':
            return "Hi-Res" if audio_info.bits_per_sample > 16 else "Lossless"
        elif file_ext == '.m4a':
            if audio_info.sample_rate > 48000: return "Hi-Res"
            return "Lossless" if hasattr(audio_info, 'codec_id') and audio_info.codec_id == 'alac' else "Lossy"
        elif file_ext == '.mp3':
            return "Lossy"
    except Exception:
        return "Unknown"
    return "Unknown"


def load_file_data(file_path):
    """Loads all tags and file info from an audio file and returns them as a dictionary."""
    if not os.path.exists(file_path):
        return None

    audio = mutagen.File(file_path, easy=True)
    if audio is None: raise ValueError("Unsupported file format.")

    audio_info = mutagen.File(file_path).info

    tags = {
        'title': audio.get("title", [""])[0],
        'artist': audio.get("artist", [""])[0],
        'album': audio.get("album", [""])[0],
        'albumartist': audio.get("albumartist", [""])[0],
        'composer': audio.get("composer", [""])[0],
        'genre': audio.get("genre", [""])[0],
        'year': audio.get("date", [""])[0],
        'track': audio.get("tracknumber", [""])[0].split('/')[0],
        'disc': audio.get("discnumber", [""])[0].split('/')[0],
        'comment': audio.get("comment", [""])[0]
    }

    # Surgical fix for loading M4A composer and albumartist tags
    if file_path.lower().endswith('.m4a'):
        audio_full = MP4(file_path)
        if audio_full.tags:
            tags['composer'] = audio_full.tags.get('\xa9wrt', [['']])[0]
            tags['albumartist'] = audio_full.tags.get('aART', [['']])[0]

    info = {
        'quality': get_file_quality(file_path),
        'duration': str(datetime.timedelta(seconds=int(audio_info.length))),
        'format': os.path.splitext(file_path)[1].upper(),
        'bitrate': f"{audio_info.bitrate / 1000:.2f} kbps",
        'samplerate': f"{audio_info.sample_rate / 1000:.1f} kHz",
        'filesize': f"{os.path.getsize(file_path) / (1024 * 1024):.2f} MB"
    }

    return {'tags': tags, 'info': info}


def load_album_art_data(file_path):
    """Extracts raw album art image data from a file."""
    audio = mutagen.File(file_path)
    if isinstance(audio, MP3) and 'APIC:' in audio:
        return audio.get('APIC:').data
    elif isinstance(audio, FLAC) and audio.pictures:
        return audio.pictures[0].data
    elif isinstance(audio, MP4) and 'covr' in audio and audio['covr']:
        return audio['covr'][0]
    return None


def save_file_tags(file_path, tags, new_art_path=None):
    """Saves the provided tags and new album art to a file."""
    # Use the Easy interface for most tags
    audio = mutagen.File(file_path, easy=True)
    if audio is None: raise ValueError("Unsupported file format for saving.")

    if 'title' in tags: audio['title'] = tags['title']
    if 'artist' in tags: audio['artist'] = tags['artist']
    if 'album' in tags: audio['album'] = tags['album']
    if 'genre' in tags: audio['genre'] = tags['genre']
    if 'year' in tags: audio['date'] = tags['year']
    if 'track' in tags: audio['tracknumber'] = tags['track']
    if 'disc' in tags: audio['discnumber'] = tags['disc']
    if 'comment' in tags: audio['comment'] = tags['comment']

    # For M4A, composer and albumartist are not reliably saved by Easy...
    if not file_path.lower().endswith('.m4a'):
        if 'albumartist' in tags: audio['albumartist'] = tags['albumartist']
        if 'composer' in tags: audio['composer'] = tags['composer']

    audio.save()

    # Surgical fix for M4A composer and albumartist tags
    if file_path.lower().endswith('.m4a'):
        audio_full = MP4(file_path)
        needs_resave = False
        if 'composer' in tags:
            audio_full['\xa9wrt'] = [tags['composer']]
            needs_resave = True
        if 'albumartist' in tags:
            audio_full['aART'] = [tags['albumartist']]
            needs_resave = True
        if needs_resave:
            audio_full.save()

    # Save new album art if provided
    if new_art_path:
        audio_full = mutagen.File(file_path)
        with open(new_art_path, 'rb') as art_file:
            art_data = art_file.read()

        if isinstance(audio_full, MP3):
            audio_full['APIC:'] = APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art_data)
        elif isinstance(audio_full, FLAC):
            pic = Picture()
            pic.data = art_data
            pic.type = 3
            pic.mime = 'image/jpeg'
            audio_full.clear_pictures()
            audio_full.add_picture(pic)
        elif isinstance(audio_full, MP4):
            ext = os.path.splitext(new_art_path)[1].lower()
            img_format = MP4Cover.FORMAT_PNG if ext == '.png' else MP4Cover.FORMAT_JPEG
            audio_full['covr'] = [MP4Cover(art_data, imageformat=img_format)]
        audio_full.save()