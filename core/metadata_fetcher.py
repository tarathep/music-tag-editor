import json
import re
from difflib import SequenceMatcher
from google import genai
from google.genai import types
from config import GEMINI_API_KEY


def _normalize_identity(value):
    """Normalize text for a conservative title/artist identity comparison."""
    value = value.casefold()
    value = re.sub(r"\b(feat|featuring|ft)\.?\b", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _identity_similarity(expected, actual):
    expected = _normalize_identity(expected)
    actual = _normalize_identity(actual)
    if not expected or not actual:
        return 0.0
    if expected in actual or actual in expected:
        return 1.0
    return SequenceMatcher(None, expected, actual).ratio()


def _validate_match(metadata, requested_title, requested_artist):
    confidence = float(metadata.get("match_confidence", 0))
    title_score = _identity_similarity(requested_title, str(metadata.get("title", "")))
    artist_score = _identity_similarity(requested_artist, str(metadata.get("artist", "")))

    if confidence < 0.72 or title_score < 0.68 or artist_score < 0.55:
        reason = metadata.get("match_reason", "The result did not match the requested recording closely enough.")
        raise ValueError(f"Low-confidence metadata match: {reason}")


def fetch_metadata_from_api(title, artist, context=None):
    """
    Fetches music metadata from the Gemini API.
    Returns a dictionary of tags or raises an exception on error.
    """
    # This function runs in a background thread
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        config = types.GenerateContentConfig(tools=[grounding_tool], temperature=0.1)

        context = context or {}
        prompt = f"""
You are matching one audio file to an authoritative music release. Accuracy is more important than filling every field.

## Input identity
- Title tag: {title!r}
- Artist tag: {artist!r}
- Existing album tag: {context.get('album', '')!r}
- Existing year tag: {context.get('year', '')!r}
- Filename: {context.get('filename', '')!r}

## Match criteria (in priority order)
1. Treat title and primary artist as identity anchors. Allow harmless punctuation, capitalization, transliteration, and featured-artist variations.
2. Do not confuse studio, live, acoustic, remix, radio edit, remaster, instrumental, karaoke, or cover recordings. Version qualifiers must agree with the input title, album, or filename.
3. Identify one specific release containing that recording. Album, year, track, and disc must all refer to that same release; never combine fields from different releases.
4. Prefer official artist/label pages, MusicBrainz, Discogs, Bandcamp, Apple Music, Spotify, or other established catalogs. Cross-check identity and release facts with at least two sources when possible.
5. Use the earliest year for the identified release edition, not a later streaming-page update date. Use only the four-digit year.
6. Use a conservative, widely recognized genre. Do not invent composer, genre, track, or disc values when sources disagree.
7. If there are multiple plausible recordings or releases and the input does not disambiguate them, set uncertain fields to empty strings and lower match_confidence.

## Output
Return only one compact JSON object. Use empty strings for unknown values. Track and disc must contain only their number for the chosen release. `comment` must contain up to three source URLs separated by spaces.

Required keys: title, artist, album, albumartist, composer, genre, year, track, disc, comment, match_confidence, match_reason.
- match_confidence: number from 0.0 to 1.0 measuring confidence that this is the exact recording and release.
- match_reason: one short sentence explaining the identity/version evidence.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config,
        )
        # print(response.text)
        json_text = response.text.strip().replace("```json", "").replace("```", "")

        metadata = json.loads(json_text)
        _validate_match(metadata, title, artist)
        return metadata
    except Exception as e:
        # We print the error to the console for debugging
        print(f"API Error: {e}")
        # And we return None to signal that an error occurred
        raise e


def fetch_metadata_batch(tracks):
    """Fetch Gemini metadata for multiple tracks without failing the whole batch."""
    results = []
    errors = []

    for track in tracks:
        try:
            metadata = fetch_metadata_from_api(track["title"], track["artist"], track.get("context"))
            results.append({"path": track["path"], "metadata": metadata})
        except Exception as exc:
            errors.append({"path": track["path"], "error": str(exc)})

    return {"batch": True, "results": results, "errors": errors}
