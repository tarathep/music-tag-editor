import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY


def fetch_metadata_from_api(title, artist):
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

        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )

        prompt = (f"Find detailed music metadata for the song titled \"{title}\" by \"{artist}\". "
                  f"Provide the information in a single, compact JSON object. If a value is not found, use an empty string. "
                  f"The JSON object must have these exact keys: title, artist, album, albumartist, composer, genre, year, track, disc. "
                  f"For track and disc number, provide it in 'number' format if available, otherwise just the number."
                  f"Provide URL source to search it in 'comment'.")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config,
        )
        # print(response.text)
        json_text = response.text.strip().replace("```json", "").replace("```", "")

        return json.loads(json_text)
    except Exception as e:
        # We print the error to the console for debugging
        print(f"API Error: {e}")
        # And we return None to signal that an error occurred
        raise e