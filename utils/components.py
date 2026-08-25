import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.trends import overall_summary_stats, music_summary_stats, podcast_summary_stats

def get_nav_bar():
    nav_bar = dbc.Row([
        dbc.Col(dcc.Link(dash.page_registry['pages.overall']['name'], href=dash.page_registry['pages.overall']['path']),
                width='auto'),
        dbc.Col(dcc.Link(dash.page_registry['pages.music']['name'], href=dash.page_registry['pages.music']['path']),
                width='auto'),
        dbc.Col(dcc.Link(dash.page_registry['pages.podcast']['name'], href=dash.page_registry['pages.podcast']['path']),
                width='auto'),
    ], justify='end')

    return nav_bar

def build_summary_card(value, stat_desc, tooltip_id=None):
    if value is None:
        return dbc.Card([dbc.CardBody([html.P(f'{stat_desc} not found', className='error')],
                        className='align-items-center d-flex justify-content-center')], className='h-100')

    p_kwargs = {}
    if tooltip_id:
        p_kwargs = dict(
            style={'textDecoration': 'underline dotted', 'text-decoration-thickness': '2px', 'cursor': 'pointer'},
            id=tooltip_id,
        )
    summary_card = dbc.Card([
        dbc.CardBody([
            html.H3(value),
            html.P(stat_desc,
                   className='descr',
                   **p_kwargs),
        ], className='text-center'),
    ])

    return summary_card

def overall_summary_cards(df):
    stats = overall_summary_stats(df)

    unique_artist_card = build_summary_card("{:,}".format(stats['unique_artists']), 'Unique Artists')
    unique_track_card = build_summary_card("{:,}".format(stats['unique_tracks']), 'Unique Tracks')
    total_streams_card = build_summary_card("{:,}".format(stats['total_streams']), 'Total Music Streams')
    total_stream_time_card = build_summary_card(stats['total_stream_time'], 'Total Stream Time', tooltip_id='total-stream-help')
    total_days_card = build_summary_card("{:,}".format(stats['total_days']), 'Total Days')

    summary_layout = [
        dbc.Col(unique_artist_card), 
        dbc.Col(unique_track_card), 
        dbc.Col(total_streams_card),
        dbc.Col(total_stream_time_card),
        dbc.Col(total_days_card),
        dbc.Tooltip(
            'This includes all tracks played in full, as well as any podcast log.',
            target='total-stream-help'
        )
    ]

    return summary_layout

def music_summary_cards(df):
    stats = music_summary_stats(df)

    skip_ratio_card = build_summary_card("{:.2f}%".format(stats['skip_ratio']), 'Skip Likelihood')
    total_stream_time_card = build_summary_card(stats['total_stream_time'], 'Total Stream Time', tooltip_id='music-stream-help')
    shuffle_likelihood_card = build_summary_card("{:.2f}%".format(stats['shuffle_ratio']), 'Shuffle Likelihood')
    most_played_genre_card = build_summary_card(stats['most_played_genre'], 'Most Played Genre')

    summary_layout = [
        dbc.Stack([
            dbc.Row([dbc.Col(skip_ratio_card), dbc.Col(total_stream_time_card)]),
            dbc.Row([dbc.Col(shuffle_likelihood_card), dbc.Col(most_played_genre_card)], style={'height': '100%'}),
        ], gap=3),
        dbc.Tooltip(
            'This only includes tracks played in full.',
            target='music-stream-help'
        )
    ]

    return summary_layout

def podcast_summary_cards(df):
    stats = podcast_summary_stats(df)

    unique_podcasts_card = build_summary_card(stats['unique_podcasts'], 'Unique Podcast Shows')
    total_stream_time_card = build_summary_card(stats['total_stream_time'], 'Total Stream Time')

    summary_layout = [dbc.Col(unique_podcasts_card), dbc.Col(total_stream_time_card)]

    return summary_layout