import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from utils.trends import (
    discoverability_ratio,
    genre_rankings,
    top_music_stats,
)
from utils.process_data import df
from utils.components import music_summary_cards

dash.register_page(__name__)

layout = html.Div([
    dbc.Stack([
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=top_music_stats(df), style={'height': '100%'}),
                            style={'height': '100%'}),
                    width=7,
                    className='h-100'
            ),
            dbc.Col(dbc.Stack([
                dbc.Row(music_summary_cards(df)),
                dbc.Card(dcc.Graph(figure=discoverability_ratio(df), style={'height': '100%'}), style={'height': '100%'}),
            ], gap=3, className='h-100'), className='h-100'),
        ], style={'height': '70vh'}),
        dbc.Row([
            dbc.Col([dbc.Card(dcc.Graph(figure=genre_rankings(df)))])
        ]),
        dbc.Row(style={'height': '5vh'})
    ], gap=3)
])
