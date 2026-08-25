import dash
from dash import dcc
import dash_bootstrap_components as dbc

from utils.trends import (
    music_podcast_breakdown,
    music_podcast_top_entries,
    weekly_heatmap,
    yearly_aggregation,
)
from utils.process_data import df
from utils.components import overall_summary_cards


dash.register_page(__name__, path='/')

layout = [
    dbc.Row(overall_summary_cards(df), style={'padding-bottom': '20px'}),
    dbc.Stack([
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=yearly_aggregation(df)))),
            dbc.Col(dbc.Card(dcc.Graph(figure=weekly_heatmap(df))))
        ]),
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(figure=music_podcast_breakdown(df))), width=3),
            dbc.Col(dbc.Card(dcc.Graph(figure=music_podcast_top_entries(df))))
        ]),
        dbc.Row(style={'height': '5vh'})
    ], gap=3)
]
