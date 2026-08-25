import dash
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc

from utils.components import get_nav_bar

from quoi.viz import setup_chart_template

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP], use_pages=True)
setup_chart_template()


app.layout = [
    dcc.Location(id='url', refresh=False),
    dbc.Row([
        dbc.Col(html.H1('Spotify usage dashboard'), width=10),
        dbc.Col(get_nav_bar(), align='end')
        ], style={'padding': '25px 0px'}
    ),
    dash.page_container
]


if __name__ == '__main__':
    app.run(debug=True)
