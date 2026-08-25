from common import get_data, StreamFields, StreamFilters
from datetime import datetime
from dotenv import load_dotenv
import json
import os
import polars as pl
import requests
import time
from typing import Tuple

load_dotenv()


# Songs played less than this amount will be removed
# This is to prevent long tail from causing needless API calls
CUTOFF = 2

# Update genre_mappings every this amount of iterations
CHECKPOINT = 250

# Last.fm seems to enforce a 5 rps rate limit but we set to 4 just in case
DELAY_S = 0.25


# -----------------------------------------------------------------------------
#
#  API Setup
#
# -----------------------------------------------------------------------------

USER_AGENT = 'Spotify_Usage_Analysis'
API_KEY = os.getenv('LAST_FM_API_KEY')
URL = 'http://ws.audioscrobbler.com/2.0/'

# Request parameters
HEADERS = {'user-agent': USER_AGENT}
BASE_PAYLOAD = {
    'method': 'track.getTopTags',
    'api_key': API_KEY,
    'format': 'json',
    'autocorrect': 1,
}

# Import genre mappings or create one
if os.path.exists('genre_mappings.json'):
    with open('genre_mappings.json', 'r') as f:
        genre_mappings = json.load(f)
else:
    genre_mappings = {}


def api_request(artist, album, track, level='track') -> Tuple[int, dict]:
    # Outputs (status and dict):
    # -1: response error
    #  0: no tags obtained (only this one leads to fallback)
    #  1: success (and genre_mappings was updated)

    assert level in ('track', 'album', 'artist'), f'Unknown fallback level: {level}'
    
    if level == 'track':
        request_extra_params = dict(artist=artist, track=track)
    elif level == 'album':
        request_extra_params = dict(artist=artist, album=album)
    else:
        request_extra_params = dict(artist=artist)

    # Make the API call
    payload = BASE_PAYLOAD | request_extra_params
    payload['method'] = payload['method'].replace('track', level)
    resp = requests.get(URL, headers=HEADERS, params=payload)
    resp_json = resp.json()

    # Parse response
    # Data are indexed by artist, then track, to make pre-request lookups easier
    new_row = {
        'request_ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status_code': resp.status_code,
        'album': album,
        'genres': None,
        'genre_counts': None,
        'error_message': None,
        'level': level
    }

    try:
        resp.raise_for_status()
        curr_genres = []
        curr_counts = []

        if len(resp_json['toptags']['tag']) == 0:
            return (0, new_row)
        
        for el in resp_json['toptags']['tag']:
            curr_genres.append(el['name'])
            curr_counts.append(el['count'])
    
        new_row['genres'] = curr_genres
        new_row['genre_counts'] = curr_counts
    except requests.exceptions.HTTPError:
        new_row['error_message'] = resp_json['message']
        return (-1, new_row)

    return (1, new_row)


# -----------------------------------------------------------------------------
#
# Get artist - song entries from historic data
# This is sorted by play count, so as to prioritize most played tracks first
#
# -----------------------------------------------------------------------------

df = get_data()
df = df.filter(StreamFilters.IS_MUSIC) \
       .group_by([StreamFields.MUSIC, StreamFields.ALBUM, StreamFields.ARTIST]) \
       .len(name='count') \
       .sort('count', descending=True)

cutoff_impact = df.filter(pl.col('count') < CUTOFF)['count'].sum() / df['count'].sum()  * 100
print(f'Tracks played less than {CUTOFF} times make up {cutoff_impact:.2f}% of play counts.')

df = df.filter(pl.col('count') >= CUTOFF)

TOTAL_TRACKS = len(df)


# -----------------------------------------------------------------------------
#
# Fetch track tag info
#
# -----------------------------------------------------------------------------

checkpoint_counter = 0
print(f'Fetching {TOTAL_TRACKS} total tracks...')
for i, (track, album, artist, _) in enumerate(df.iter_rows()):
    # Check if there's already data for this track
    # Notice that this skips the entire request logic (including updating the json file and time.sleep)
    if artist in genre_mappings and track in genre_mappings[artist]:
        continue
    
    if artist not in genre_mappings:
        genre_mappings[artist] = {}

    status, row = api_request(artist=artist, album=album, track=track, level='track')
    time.sleep(DELAY_S)

    # Fallback to album level
    if status != 1:
        status, row = api_request(artist=artist, album=album, track=track, level='album')
        time.sleep(DELAY_S)

        # Fallback to artist level
        if status != 1:
            status, row = api_request(artist=artist, album=album, track=track, level='artist')
            time.sleep(DELAY_S)

    # Even if artist level returns no tags, we store the response either way
    genre_mappings[artist][track] = row

    # Store current mappings
    checkpoint_counter += 1
    if checkpoint_counter >= CHECKPOINT:
        with open('genre_mappings.json', 'w') as f:
            json.dump(genre_mappings, f)

        # Update progress indicator and prevent rate limiting
        # Only prints during checkpoint
        print(f'{i} / {TOTAL_TRACKS} tracks requested')

# Store upon completion
with open('genre_mappings.json', 'w') as f:
    json.dump(genre_mappings, f)

print('Finished requesting track tag data (check genre_mappings.json)')
