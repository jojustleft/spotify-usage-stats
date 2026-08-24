from dotenv import load_dotenv
from dataclasses import dataclass
import os
import polars as pl

from quoi.time import duration_to_interval

load_dotenv()


# Common columns
@dataclass(frozen=True)
class StreamFields:
    # Music columns
    MUSIC = 'master_metadata_track_name'
    ARTIST = 'master_metadata_album_artist_name'
    ALBUM = 'master_metadata_album_album_name'
    
    # Podcast columns
    EPISODE = 'episode_name'
    PODCAST = 'episode_show_name'


# Common filters
@dataclass(frozen=True)
class StreamFilters:
    IS_MUSIC = ~pl.col(StreamFields.MUSIC).is_null()
    IS_PODCAST = ~pl.col(StreamFields.EPISODE).is_null()
    FULL_STREAM = pl.col('reason_end') == 'trackdone'
    SKIP_STREAM = pl.col('reason_end').is_in(['backbtn', 'fwdbtn', 'endplay', 'unexpected-exit', 'unexpected-exit-while-paused'])

# List of words that cannot occur in tags
# This list is not extensive by any means, it was made by looking at the top occurring words
EXCLUDE_TAG_WORDS = [
    'of',                        # E.g.: "Best of {year}"
    'the',                       # Often with band names starting with "The ..."
    'music',
    'albums', 'album',
    'to',                        # E.g.: "Songs to dance to"
    'best',                      # Same as 'of' (likely redundant)
    'i', 'a',                    # Reminder: standalone words
    'records', 'record'          # Often associated with Record Labels
    'this',                      # E.g.: "I like this"
    'in',
    'my',
    'on',
    'listen',                    # E.g.: "Must listen"
    'male', 'female',
    'with',
    'good', 'great',
    'love',
    'releases',
    'you',
    'all',                       # E.g.: "All time favourite"
    'cover', 'covers',
    'own', 'have', 'want',
    'top',                       # E.g.: "Top 10"
    'is',
    'radio',
    'sound', 'sounds',           # Reminder: standalone words
    'artist', 'artists',
    'vinyl', 'cd',
    'favorite', 'favourite',
    'favorites', 'favourites',
    'your',
    'at',
    'for',
    'out',
    'song', 'songs',
    'time',
    'world',
    'no', 'not',
    'stars',
    'hot',
    'cool',
    'night',
    'vocalists', 'singer',
    'while',
    'it',
    'check',
    'core',
    'mostly',
    'get',
    'really',
    'these',
    'morgan',
    'more',
    'idol',
    'so',
    'up',
    'but',
    'life',
    'go',
    'songwriter',
    'real',
    'live',
    'buy',
    'olivia',
    'one',
    'fire',
    'just',
    'vibe', 'vibes',
    'canada', 'canadian'
]


def get_data():
    filepath = os.getenv('DATA_FILEPATH')

    if not filepath:
        raise EnvironmentError("Please set 'DATA_FILEPATH' variable in .env to read activity logs.")
    
    file_pattern = 'Streaming_History_Audio_'
    
    schema = {
        'ts': pl.Datetime,
        'platform': pl.String,
        'ms_played': pl.Int64,
        'conn_country': pl.String,
        'ip_addr': pl.String,
        'master_metadata_track_name': pl.String,
        'master_metadata_album_artist_name': pl.String,
        'master_metadata_album_album_name': pl.String,
        'spotify_track_uri': pl.String,
        'episode_name': pl.String,
        'episode_show_name': pl.String,
        'spotify_episode_uri': pl.String,
        'audiobook_title': pl.String,
        'audiobook_uri': pl.String,
        'audiobook_chapter_uri': pl.String,
        'audiobook_chapter_title': pl.String,
        'reason_start': pl.String,
        'reason_end': pl.String,
        'shuffle': pl.Boolean,
        'skipped': pl.Boolean,
        'offline': pl.Boolean,
        'offline_timestamp': pl.String,
        'incognito_mode': pl.Boolean
    }
    
    entries = []
    
    for file in os.listdir(filepath):
        if file.startswith(file_pattern):
            entries.append(pl.read_json(os.path.join(filepath, file), schema=schema))
    
    if not entries:
        raise EnvironmentError("No 'Streaming_History_Audio_*' files have been found.")

    df = pl.concat(entries).sort('ts')
    return df

def ms_to_interval_str(x):
    interval = duration_to_interval(x, units='ms')
    
    day_str = '{}d '.format(interval['days']) if interval['days'] else ''
    hour_str = '{}h '.format(interval['hours'])
    minute_str = '{}m'.format(interval['minutes'])

    return day_str + hour_str + minute_str
