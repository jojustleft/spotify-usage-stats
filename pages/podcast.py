from common import EXCLUDE_TAG_WORDS, get_data, StreamFields, StreamFilters
import dash
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc

from utils.trends import get_top_podcasts, get_top_podcast_sessions
from utils.process_data import df
from utils.components import podcast_summary_cards

dash.register_page(__name__)

layout = html.Div([
    dbc.Stack([
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=get_top_podcasts(df), style={'height': '100%'}),
                            style={'height': '100%'}),
                    width=7,
                    className='h-100'
            ),
            dbc.Col(dbc.Stack([
                dbc.Row(podcast_summary_cards(df)),
                dbc.Card(dcc.Graph(figure=get_top_podcast_sessions(df), style={'height': '100%'}), style={'height': '100%'}),
            ], gap=3, className='h-100'), className='h-100'),
        ], style={'height': '70vh'}),
        dbc.Row(style={'height': '5vh'})
    ], gap=3)
])
