from difflib import get_close_matches
import json
import os
import polars as pl
from common import EXCLUDE_TAG_WORDS, StreamFields, StreamFilters, get_data
import warnings


def flag_duplicates(df):
    duplicate_cols = ['_ts_group', StreamFields.MUSIC, StreamFields.ARTIST, StreamFields.ALBUM, 'reason_end']
    df = df.with_columns(pl.col('ts').dt.truncate('2m').alias('_ts_group'))
    df = df.with_columns(df[duplicate_cols].is_duplicated().alias('is_duplicate'))

    return df


def get_top_music_entries(df, groupby_cols):
    df_agg = df.filter(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM).group_by(groupby_cols).agg(
        (pl.col('ms_played')).sum(),
        pl.col('ts').count().alias('count')
    )
    df_agg = df_agg.with_columns(
        (pl.col('ms_played') / 1000 / 60).alias('min_played'),
        (pl.col('ms_played') / pl.col('ms_played').sum() * 100).alias('share_ts'),
        (pl.col('count') / pl.col('count').sum() * 100).alias('share_count'),
    )

    return df_agg.sort('min_played', descending=True)

def get_genre_mapping():
    if os.path.exists("genre_mappings.json"):
        with open("genre_mappings.json", "r") as f:
            genre_mappings = json.load(f)
    else:
        raise FileNotFoundError("genre_mappings.json was not found. (Did you run fetch_music_tags.py?)")
    
    # Since mappings are not flat, we must parse the dictionary manually instead of simply importing with pl.from_dict
    unique_tags = set()
    df_tags = None
    for a in genre_mappings:
        for t in genre_mappings[a]:
            new_rows = pl.DataFrame({'artist': a, 'track': t} | genre_mappings[a][t],
                                    schema_overrides={'status_code': pl.Int32,
                                                      'genres': pl.String, 
                                                      'genre_counts': pl.Int64, 
                                                      'error_message': pl.String})
            df_tags = new_rows if df_tags is None else df_tags.extend(new_rows)
            if genre_mappings[a][t]['genres']:
                unique_tags = unique_tags.union(set(genre_mappings[a][t]['genres']))

    df_tags = df_tags.rename({'genres': 'tag'})
    df_tags = df_tags.with_columns(pl.col('genre_counts').rank(descending=True).over([pl.col('track'), pl.col('artist')]).alias('rank'))

    top_tag_threshold = 4

    df_tag_set = df_tags.filter(pl.col('rank') < top_tag_threshold)['tag'].value_counts().rename({'tag': 'tag_raw'})
    df_tag_set = df_tag_set.with_columns(
        pl.col('tag_raw').str.to_lowercase() \
                        .str.strip_chars(' -_') \
                        .str.replace_all(' ', '_') \
                        .str.replace_all('-', '_') \
                        .alias('tag_norm')
    ).filter(~pl.col('tag_norm').is_null())

    df_tag_set = df_tag_set.with_columns(
        (df_tag_set['tag_norm'].str.split('_').list.set_intersection(EXCLUDE_TAG_WORDS).list.len() > 0).alias('has_excluded_words'),
        pl.col('tag_norm').str.contains(r"\d+").alias('has_numbers')
    )

    fuzzy_reference = df_tag_set.filter((pl.col('count') > 20) 
                                        & (~pl.col('has_excluded_words'))
                                        & (~pl.col('has_numbers')))['tag_norm'].to_list()

    # List of similar elements within fuzzy_reference
    remove_reference = ['jrock', 'synthpop', 'lofi', 'jpop', 'video_game_soundtrack']
    fuzzy_reference = list(set(fuzzy_reference).difference(set(remove_reference)))

    df_tag_set = df_tag_set.with_columns(
        df_tag_set['tag_norm'].map_elements(lambda x: next(iter(get_close_matches(x, fuzzy_reference, cutoff=0.85, n=1)), None)).alias('fuzzy_match')
    )

    main_genres = ['alternative', 'blues', 'classical', 'country', 'electronic', 'folk', 'funk', 'hip_hop', 
                   'indie', 'instrumental', 'jazz', 'metal', 'pop', 'punk', 'rnb', 'rock', 'soul',  
                   'soundtrack']

    df_tag_set = df_tag_set.with_columns(
        pl.col('tag_norm').is_in(main_genres).alias('main_genre')
    )

    df_tag_set = df_tag_set.with_columns(
        pl.when(pl.col('main_genre')).then(pl.col('tag_norm')) \
        .when(pl.col('fuzzy_match').is_not_null()).then(pl.col('fuzzy_match')) \
        .otherwise(pl.col('tag_norm')) \
        .alias('tag_final')
    )

    df_tag_set = df_tag_set.filter((~pl.col('has_numbers'))
                                    & (~pl.col('has_excluded_words'))
                                    & (pl.col('count') >= 25))

    df_tags = df_tags.filter(
        pl.col('tag').is_in(df_tag_set['tag_raw'].to_list())
    )
    df_tags = df_tags.join(df_tag_set[['tag_raw', 'tag_final']],
                           how='inner', left_on='tag', right_on='tag_raw')
    
    df_tags = df_tags.with_columns(
        pl.col('tag_final').str.replace('_', ' ').str.to_titlecase().alias('tag')
    )[['artist', 'track', 'tag']]
    df_tags = df_tags.group_by(['artist', 'track']).agg(
        pl.col('tag').implode()
    )
    
    return df_tags    


def clean_data():
    df = get_data()

    # We won't be using these
    df = df.drop(['platform', 'conn_country', 'ip_addr', 'incognito_mode', 'offline_timestamp',
                        'spotify_track_uri', 'spotify_episode_uri',
                        'audiobook_title', 'audiobook_uri', 'audiobook_chapter_uri',
                        'audiobook_chapter_title'])
    
    df = flag_duplicates(df)

    df = df.filter(~pl.col('is_duplicate')).drop(['_ts_group', 'is_duplicate'])

    try:
        df_tags = get_genre_mapping()
        df = df.join(df_tags,
                     left_on=[StreamFields.ARTIST, StreamFields.MUSIC],
                     right_on=['artist', 'track'],
                     how='left')
    except FileNotFoundError:
        warnings.warn('genre_mappings.json file was not found. Music genre trends will not be shown.')
    
    return df

df = clean_data()
print('Imported and cleaned data')
