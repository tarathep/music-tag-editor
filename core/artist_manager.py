import os
import json

class ArtistManager:
    """Manages operations related to the artist library file."""

    def __init__(self, current_directory):
        self.current_directory = current_directory
        self.artists_path = self._get_artists_path()
        self.artists_data = self._load_artists()

    def _get_artists_path(self):
        """Constructs the path to the artists.json file."""
        if not self.current_directory:
            return None
        parent_dir = os.path.dirname(self.current_directory)
        artists_dir = os.path.join(parent_dir, 'artists')
        os.makedirs(artists_dir, exist_ok=True)
        return os.path.join(artists_dir, 'artists.json')

    def _load_artists(self):
        """Loads the artist data from the JSON file."""
        if not self.artists_path or not os.path.exists(self.artists_path):
            return []
        try:
            with open(self.artists_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_artists(self):
        """Saves the current artist data to the JSON file."""
        if not self.artists_path:
            return
        with open(self.artists_path, 'w', encoding='utf-8') as f:
            json.dump(self.artists_data, f, ensure_ascii=False, indent=4)

    def update_library(self, artist_name, album_artist_name):
        """Adds new artists to the library."""
        names_to_add = {name.strip() for name in [artist_name, album_artist_name] if name.strip()}
        if not names_to_add:
            return 0

        existing_names = set()
        max_id = 0
        for artist in self.artists_data:
            if 'id' in artist and int(artist['id']) > max_id:
                max_id = int(artist['id'])
            if 'names' in artist:
                for name in artist['names']:
                    existing_names.add(name)

        new_artists_added = 0
        for name in names_to_add:
            if name not in existing_names:
                max_id += 1
                new_artist = {"id": str(max_id), "names": [name], "path": f"{max_id}.jpg"}
                self.artists_data.append(new_artist)
                existing_names.add(name)
                new_artists_added += 1

        if new_artists_added > 0:
            self._save_artists()

        return new_artists_added

    def standardize_names(self, artist_name, album_artist_name):
        """Finds the primary name for given artist aliases."""
        if not self.artists_data:
            return None, None

        artist_map = {alias: artist['names'][0] for artist in self.artists_data if 'names' in artist and artist['names']
                      for alias in artist['names']}

        standardized_artist = artist_map.get(artist_name.strip())
        standardized_album_artist = artist_map.get(album_artist_name.strip())

        return standardized_artist, standardized_album_artist