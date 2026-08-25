import numpy as np
import plotly.graph_objects as go
import polars as pl

from quoi.stats import fill_cartesian_expansion, fill_based_on, get_top
from quoi.viz import (
    plot_area,
    plot_bar,
    plot_line,
    bold_text,
    build_subtitle,
    fig_merge_as_dropdown,
    setup_chart_template,
    trim_labels,
)
from common import StreamFields, StreamFilters, ms_to_interval_str
from utils.process_data import get_top_music_entries

setup_chart_template()

def get_empty_plot(message, height=None):
    fig = go.Figure()

    annotation = {
        'text': message,
        'xref': 'paper',
        'yref': 'paper',
        'showarrow': False,
        'font': {
            'size': 28,
            'color': '#D5834F',
        }
    }

    fig.update_layout(xaxis_visible=False,
                      yaxis_visible=False,
                      annotations=[annotation],
                      height=height)

    return fig

def overall_summary_stats(df):
    unique_artists = df.filter(StreamFilters.FULL_STREAM
                               & StreamFilters.IS_MUSIC)[StreamFields.ARTIST].n_unique()
    unique_tracks = df.filter(StreamFilters.FULL_STREAM
                              & StreamFilters.IS_MUSIC)[StreamFields.MUSIC].n_unique()
    total_streams = df.filter(StreamFilters.FULL_STREAM
                              & StreamFilters.IS_MUSIC).shape[0]
    total_stream_time = df.filter((StreamFilters.FULL_STREAM & StreamFilters.IS_MUSIC) 
                                  | StreamFilters.IS_PODCAST)['ms_played'].sum()
    total_stream_time = ms_to_interval_str(total_stream_time)
    total_days = (df['ts'].max() - df['ts'].min()).days

    summary = {
        'unique_artists': unique_artists,
        'unique_tracks': unique_tracks,
        'total_streams': total_streams,
        'total_stream_time': total_stream_time,
        'total_days': total_days
    }
    return summary

def music_summary_stats(df):
    df_flt = df.filter(StreamFilters.IS_MUSIC & (StreamFilters.FULL_STREAM | StreamFilters.SKIP_STREAM)).group_by(
        pl.when(StreamFilters.FULL_STREAM).then(pl.lit('Played'))
          .when(StreamFilters.SKIP_STREAM).then(pl.lit('Skipped'))
          .otherwise(pl.lit('Other'))
          .alias('outcome')
    ).agg(
        pl.col('ms_played').sum().alias('ms_played'),
        pl.col('ts').count().alias('count')
    )
    skip_ratio = df_flt.filter(pl.col('outcome') == 'Skipped')['count'].sum() / df_flt['count'].sum() * 100
    total_stream_time = df_flt.filter(pl.col('outcome') == 'Played')['ms_played'].sum()
    total_stream_time = ms_to_interval_str(total_stream_time)
    shuffle_ratio = df.filter(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM & pl.col('shuffle')).shape[0] / \
        df.filter(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM).shape[0] * 100

    
    most_played_genre = None
    if 'tag' in df.columns:
        most_played_genre = df.filter(StreamFilters.IS_MUSIC
                                      & StreamFilters.FULL_STREAM 
                                      & (~pl.col('tag').is_null())) \
                              .explode('tag')['tag'].mode()[0]

    summary = {
        'skip_ratio': skip_ratio,
        'total_stream_time': total_stream_time,
        'shuffle_ratio': shuffle_ratio,
        'most_played_genre': most_played_genre
    }
    return summary

def podcast_summary_stats(df):
    df_podcast = df.filter(StreamFilters.IS_PODCAST)

    total_stream_time = df_podcast['ms_played'].sum()
    total_stream_time = ms_to_interval_str(total_stream_time)
    unique_podcasts = df_podcast[StreamFields.PODCAST].n_unique()

    summary = {
        'total_stream_time': total_stream_time,
        'unique_podcasts': unique_podcasts
    }

    return summary

def weekly_heatmap(df):
    df_heatmap = df.group_by(
        pl.when(StreamFilters.IS_MUSIC).then(pl.lit('Music'))
          .when(StreamFilters.IS_PODCAST).then(pl.lit('Podcast'))
          .otherwise(pl.lit('Other')).alias('stream_type'),
        pl.col('ts').dt.weekday().alias('weekday_val'),
        pl.col('ts').dt.strftime('%A').alias('weekday'),
        pl.col('ts').dt.hour().alias('hour'),
    ).agg(pl.Expr.sum(pl.col('ms_played')))

    df_heatmap = fill_cartesian_expansion(df_heatmap, entry_l=['stream_type', 'weekday_val', 'hour'])
    df_heatmap = fill_based_on(df_heatmap, base='weekday_val', target='weekday')
    df_heatmap = df_heatmap.with_columns(
        (pl.col('ms_played') / 1000 / 60).alias('min_played')
    ).sort('weekday_val', 'hour')

    fig_l = {}
    
    # Config shared across every dropdown view
    trace_kwargs = dict(
        hovertemplate='<br>'.join([
            '<b>Weekday:</b> %{x}',
            '<b>Hour:</b> %{y}',
            '<b>Minutes:</b> %{z}'
            '<extra></extra>'
        ]),
        colorscale=[[0, '#FCF6F5'], [1, '#5C825B']],
        showscale=False
    )
    subtitle = build_subtitle('Total sum of stream minutes - Includes skipped entries')
    layout_kwargs = dict(
        title=bold_text('Listening activity throughout the week') + subtitle,
        xaxis_title=bold_text('Hour'),
        xaxis_ticksuffix=':00',
        yaxis_title=bold_text('Weekday'),
        margin=dict(r=20)
    )

    # Music and podcasts
    _curr_view = df_heatmap.group_by(['weekday_val', 'weekday', 'hour']).agg(
        pl.col('min_played').sum()
    ).sort('weekday_val', 'hour')
    fig = go.Figure()
    fig.add_trace(go.Heatmap(x=_curr_view['hour'],
                             y=_curr_view['weekday'],
                             z=_curr_view['min_played'],
                             **trace_kwargs))
    fig.update_layout(**layout_kwargs)
    fig_l['Music and podcasts'] = fig

    # Standalone
    for t in ('Music', 'Podcast'):
        _curr_view = df_heatmap.filter(pl.col('stream_type') == t).group_by(['weekday_val', 'weekday', 'hour']).agg(
            pl.col('min_played').sum()
        ).sort('weekday_val', 'hour')
        fig = go.Figure()
        fig.add_trace(go.Heatmap(x=_curr_view['hour'],
                                 y=_curr_view['weekday'],
                                 z=_curr_view['min_played'],
                                 **trace_kwargs))
        fig.update_layout(**layout_kwargs)
        fig_l[f'{t} only'] = fig

    fig = fig_merge_as_dropdown(fig_l)
    fig.layout.updatemenus[0]['y'] = 1.2

    return fig

def music_podcast_breakdown(df):
    df_agg = df.group_by(
        pl.when(StreamFilters.IS_MUSIC).then(pl.lit('Music'))
          .when(StreamFilters.IS_PODCAST).then(pl.lit('Podcast'))
          .otherwise(pl.lit('Other'))
          .alias('stream_type')
    ).agg(
        pl.col('ms_played').sum()
    )
    df_agg = df_agg.with_columns((pl.col('ms_played') / pl.col('ms_played').sum() * 100).alias('share_ms'))

    fig = go.Figure()
    fig.add_trace(go.Pie(labels=df_agg['stream_type'],
                         values=df_agg['share_ms'],
                         textinfo='label+percent',
                         textposition='outside',
                         texttemplate='%{label}<br>%{value:.2f}%',
                         hole=0.5))
    fig.update_layout(showlegend=False)
    return fig

def music_podcast_top_entries(df, top_n=15):
    df_top = df.group_by(
        pl.when(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM).then(StreamFields.ARTIST)
          .when(StreamFilters.IS_PODCAST).then(StreamFields.PODCAST)
          .alias('entry'),
        pl.when(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM).then(pl.lit('Music'))
          .when(StreamFilters.IS_PODCAST).then(pl.lit('Podcast'))
          .alias('stream_type')
    ).agg(
        pl.col('ms_played').sum()
    )
    df_top = df_top.with_columns(
        (pl.col('ms_played') / 1000 / 60).alias('min_played'),
        (pl.col('ms_played') / pl.col('ms_played').sum() * 100).alias('share_ms'),
        pl.when(pl.col('stream_type') == 'Music').then(pl.lit('#5C825B'))
          .when(pl.col('stream_type') == 'Podcast').then(pl.lit('#D5834F'))
          .alias('marker_color')
    ).sort('share_ms', descending=True)

    curr_view = df_top.filter(~pl.col('entry').is_null()).head(top_n)
    fig = plot_bar(curr_view,
                   x='entry',
                   y='min_played',
                   hovertemplate='<br>'.join([
                       '<b>%{xaxis.title.text}:</b> %{x}',
                       '<b>Stream type:</b> %{customdata[0]}<br>',
                       '<b>Share of total time played:</b> %{customdata[1]:.2f}%',
                       '<b>%{yaxis.title.text}:</b> %{y:.0f}',
                       '<extra></extra>'
                   ]),
                   title='Most streamed media',
                   subtitle='Excluding skipped tracks',
                   x_title='Artist / Podcast',
                   y_title='Time played (minutes)',
                   return_fig=True)

    fig.update_traces(text=curr_view['ms_played'].map_elements(lambda x: ms_to_interval_str(x)),
                      customdata=np.stack((curr_view['stream_type'], curr_view['share_ms']), axis=-1),
                      marker_color=curr_view['marker_color'])
    fig.update_layout(xaxis_title_standoff=10,
                      xaxis_tickangle=-25,
                      margin=dict(r=20))
    fig = trim_labels(fig, x_trim=25)
    return fig

def yearly_aggregation(df):
    df_yearly = df.group_by(pl.col('ts').dt.year().alias('year')).agg(
        pl.when(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM) 
          .then(pl.col('ms_played'))
          .otherwise(0)
          .sum()
          .alias('music_ms'),
        pl.when(StreamFilters.IS_PODCAST)
          .then(pl.col('ms_played'))
          .otherwise(0)
          .sum()
          .alias('podcast_ms'),
    ).sort('year')

    df_yearly = fill_cartesian_expansion(df_yearly, entry_l=['year'])
    df_yearly = df_yearly.with_columns(
        (pl.col('music_ms') / 1000 / 60).alias('music_minutes'),
        (pl.col('podcast_ms') / 1000 / 60).alias('podcast_minutes'),
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_yearly['year'], y=df_yearly['music_minutes'], name='Music'))
    fig.add_trace(go.Bar(x=df_yearly['year'], y=df_yearly['podcast_minutes'], name='Podcasts',
                         text=df_yearly[['music_ms', 'podcast_ms']].sum_horizontal().map_elements(lambda x: ms_to_interval_str(x))))

    fig.update_layout(title=bold_text('Total stream time over the years') + build_subtitle('Excluding skipped music tracks only'),
                      xaxis_title=bold_text('Year'),
                      yaxis_title=bold_text('Time played (minutes)'),
                      barmode='stack',
                      hovermode='x unified',
                      margin=dict(r=20))

    fig.update_traces(textposition='outside',
                      hovertemplate='%{y}')
    
    return fig

def top_music_stats(df, top_n=15):
    fig_l = {}
    shared_kwargs = dict(
        subtitle='Excluding skipped tracks',
        x_title='Time played (minutes)',
        orientation='h',
        return_fig=True
    )
    layout_kwargs = dict(
        margin=dict(r=20),
        yaxis_title_standoff=10,
        yaxis_autorange='reversed',
    )

    # By music track
    curr_view = get_top_music_entries(df, [StreamFields.ARTIST, StreamFields.ALBUM, StreamFields.MUSIC]).head(top_n)
    fig = plot_bar(curr_view, x='min_played', y=StreamFields.MUSIC,
                   title='Most played music tracks by total play time',
                   y_title='Music track',
                   hovertemplate='<br>'.join([
                       '<b>%{yaxis.title.text}:</b> %{y}',
                       '<b>Album</b>: %{customdata[0]}',
                       '<b>Artist</b>: %{customdata[1]}<br>',
                       '<b>Share of total time played:</b> %{customdata[2]:.3f}%',
                       '<b>%{xaxis.title.text}:</b> %{x:.0f}',
                       '<b>Share of total plays:</b> %{customdata[3]:.3f}%',
                       '<extra></extra>'
                   ]),
                   **shared_kwargs)
    fig.update_traces(customdata=np.stack((curr_view[StreamFields.ALBUM],
                                           curr_view[StreamFields.ARTIST],
                                           curr_view['share_ts'],
                                           curr_view['share_count']), axis=-1),
                      text=curr_view['ms_played'].map_elements(lambda x: ms_to_interval_str(x)))
    fig.update_layout(**layout_kwargs)
    fig = trim_labels(fig, y_trim=25)
    fig_l['Music track'] = fig

    # By album
    curr_view = get_top_music_entries(df, [StreamFields.ARTIST, StreamFields.ALBUM]).head(top_n)
    fig = plot_bar(curr_view, x='min_played', y=StreamFields.ALBUM,
                   title='Most played albums by total play time',
                   y_title='Album',
                   hovertemplate='<br>'.join([
                       '<b>%{yaxis.title.text}:</b> %{y}',
                       '<b>Artist</b>: %{customdata[0]}<br>',
                       '<b>Share of total time played:</b> %{customdata[1]:.3f}%',
                       '<b>%{xaxis.title.text}:</b> %{x:.0f}',
                       '<b>Share of total plays:</b> %{customdata[2]:.3f}%',
                       '<extra></extra>'
                   ]),
                   **shared_kwargs)
    fig.update_traces(customdata=np.stack((curr_view[StreamFields.ARTIST],
                                           curr_view['share_ts'],
                                           curr_view['share_count']), axis=-1),
                      text=curr_view['ms_played'].map_elements(lambda x: ms_to_interval_str(x)))
    fig.update_layout(**layout_kwargs)
    fig = trim_labels(fig, y_trim=25)
    fig_l['Album'] = fig

    # By artist
    curr_view = get_top_music_entries(df, [StreamFields.ARTIST]).head(top_n)
    fig = plot_bar(curr_view, x='min_played', y=StreamFields.ARTIST,
                   title='Most played artists by total play time',
                   y_title='Artist',
                   hovertemplate='<br>'.join([
                       '<b>%{yaxis.title.text}:</b> %{y}<br>',
                       '<b>Share of total time played:</b> %{customdata[1]:.3f}%',
                       '<b>%{xaxis.title.text}:</b> %{x:.0f}',
                       '<b>Share of total plays:</b> %{customdata[2]:.3f}%',
                       '<extra></extra>'
                   ]),
                   **shared_kwargs)
    fig.update_traces(customdata=np.stack((curr_view[StreamFields.ARTIST],
                                           curr_view['share_ts'],
                                           curr_view['share_count']), axis=-1),
                      text=curr_view['ms_played'].map_elements(lambda x: ms_to_interval_str(x)))

    fig.update_layout(**layout_kwargs)
    fig = trim_labels(fig, y_trim=25)
    fig_l['Artist'] = fig

    fig = fig_merge_as_dropdown(fig_l)
    fig.layout.updatemenus[0]['y'] = 1.10
    fig.update_layout(height=700)

    return fig

def discoverability_ratio(df):
    df_discover = df.filter(StreamFilters.IS_MUSIC & StreamFilters.FULL_STREAM)
    df_discover = df_discover.with_columns(
        pl.col(StreamFields.MUSIC).is_first_distinct().alias('is_distinct'),
    )
    df_discover = df_discover.group_by([pl.col('ts').dt.truncate('1y'), 'is_distinct']).len('count').sort('ts')
    df_discover = fill_cartesian_expansion(df_discover, time_c='ts', entry_l=['is_distinct'], interval='1y')

    fig = plot_area(df_discover, x='ts', y='count', breakdown='is_distinct',
                    title='Music play counts by discovery or repeat stream',
                    subtitle='Excluding skipped tracks',
                    x_title='Year',
                    y_title='Play count',
                    legend_replace={'True': 'Discovery', 'False': 'Repeat'},
                    return_fig=True)
    fig.update_layout(hovermode='x unified',
                      margin=dict(r=20))
    fig.data = fig.data[::-1]
    
    return fig

def genre_rankings(df, top_n=20):
    try:
        df_genre_yearly = df.explode('tag').group_by([pl.col('ts').dt.truncate('1y'), 'tag']).agg(
            pl.col('ms_played').sum(),
            pl.col('ts').count().alias('count')
        ).sort('ts')

        df_genre_yearly = fill_cartesian_expansion(df_genre_yearly, time_c='ts', entry_l=['tag'], interval='1y')
        df_genre_yearly = df_genre_yearly.with_columns(
            pl.col('count').rank(descending=True, method='ordinal').over('ts').alias('rank')
        )

        df_genre_yearly = df_genre_yearly.filter(pl.col('rank') <= top_n).sort(['ts', 'rank'])
        df_genre_yearly = fill_cartesian_expansion(df_genre_yearly, time_c='ts', entry_l=['tag'], interval='1y', default=None)

        fig = plot_line(df_genre_yearly,
                        x='ts',
                        y='rank',
                        breakdown='tag',
                        title='Ranking of most common song tags',
                        subtitle='Tag information obtained from Last.fm - Excluding skipped music tracks',
                        legend_title='Song tag',
                        x_title='Year',
                        y_title='Rank (descending)',
                        vertical_legend=True,
                        return_fig=True)

        fig.update_layout(xaxis_tickformat='%Y',
                        yaxis_autorange='reversed',
                        hovermode='x unified',
                        hoversort='value ascending',
                        height=700)
        
        # Sort traces alphabetically
        fig.data = sorted(list(fig.data), key=lambda x: x.name)
    except pl.exceptions.ColumnNotFoundError:
        fig = get_empty_plot("Genre information not found in data<br>(did you run fetch_music_tags.py?)",
                             height=700)
    return fig

def get_top_podcasts(df, top_n=15):
    top_podcasts = get_top(df.filter(StreamFilters.IS_PODCAST),
                           entry_c=StreamFields.PODCAST,
                           value_c='ms_played').rename({'share': 'share_ts'})

    top_podcasts = top_podcasts.sort('share_ts', descending=True).with_columns(
        (pl.col('ms_played') / 1000 / 60).alias('min_played'),
        pl.col('share_ts').cum_sum().alias('share_ts_cumulative')
    ).with_row_index()

    curr_view = top_podcasts.head(top_n)
    fig = plot_bar(curr_view, 
                   x='min_played',
                   y=StreamFields.PODCAST,
                   hovertemplate='<br>'.join([
                       '<b>%{yaxis.title.text}:</b> %{y}<br>',
                       '<b>Share of total time played:</b> %{customdata[0]:.3f}%',
                       '<b>%{xaxis.title.text}:</b> %{x:.0f}',
                       '<extra></extra>'
                   ]),
                   title='Most played podcasts by total play time',
                   x_title='Time played (minutes)',
                   y_title='Podcast',
                   orientation='h',
                   return_fig=True)

    fig.update_traces(text=curr_view['ms_played'].map_elements(lambda x: ms_to_interval_str(x)),
                      customdata=curr_view['share_ts'])
    fig.update_layout(yaxis_autorange='reversed',
                      yaxis_title_standoff=10,
                      margin=dict(r=20))
    fig = trim_labels(fig, y_trim=25)
    return fig

def get_top_podcast_sessions(df, top_n=5):
    df_podcast_sessions = df.filter(StreamFilters.IS_PODCAST)

    df_podcast_sessions = df_podcast_sessions.with_columns(
        (pl.col('ts') + pl.duration(milliseconds='ms_played')).alias('ts_end')
    )[['ts', 'ts_end', StreamFields.PODCAST]].sort('ts')
    df_podcast_sessions = df_podcast_sessions.with_columns(
        (df_podcast_sessions['ts'] - df_podcast_sessions['ts_end'].shift(1)).alias('delta')
    )

    # A session is considered over after 30 minutes without podcast activity
    streak_flag = (pl.col('delta') < pl.duration(minutes=30))

    df_podcast_sessions = df_podcast_sessions.with_columns(
        ((~streak_flag).cum_sum()).alias('streak_id'),
        pl.when(streak_flag).then(streak_flag.cast(pl.Int32).cum_sum().over((~streak_flag).cum_sum()))
        .otherwise(1)
        .alias('session_streak')
    )

    # Aggregate into streak info per row
    # Filter out small streaks, as there could be many of them
    df_podcast_sessions_summary = df_podcast_sessions.group_by('streak_id').agg(
        pl.col('ts').min().alias('start_ts'),
        pl.col('ts_end').max().alias('end_ts'),
        pl.col('session_streak').max().alias('size'),
        pl.col(StreamFields.PODCAST).unique().alias('podcasts')
    )

    df_podcast_sessions_summary = df_podcast_sessions_summary.with_columns(
        (pl.col('end_ts') - pl.col('start_ts')).alias('delta'),
        (pl.col('end_ts') - pl.col('start_ts')).dt.total_minutes().alias('delta_min'),
    ).sort('delta', descending=True).head(top_n).with_row_index()


    fig = plot_bar(df_podcast_sessions_summary, 
                   x='delta_min',
                   y='index',
                   hovertemplate='<br>'.join([
                       '<b>Duration:</b> %{x} minutes<br>',
                       '<b>Total episodes played:</b> %{customdata[0]}',
                       '<b>Podcasts played:</b> %{customdata[1]}',
                       '<b>Start time:</b> %{customdata[2]|%Y-%m-%d %H:%M:%S}',
                       '<b>End time:</b> %{customdata[3]|%Y-%m-%d %H:%M:%S}'
                       '<extra></extra>'
                   ]),
                   title='Longest podcast sessions',
                   subtitle='A session considers podcast activity without intervals of 30 minutes or more',
                   x_title='Time played (minutes)',
                   orientation='h',
                   return_fig=True)

    fig.update_traces(text=df_podcast_sessions_summary['delta'].dt.total_milliseconds().map_elements(lambda x: ms_to_interval_str(x)),
                      customdata=np.stack((
                          df_podcast_sessions_summary['size'],
                          df_podcast_sessions_summary['podcasts'].list.join(', '),
                          df_podcast_sessions_summary['start_ts'].dt.to_string(),
                          df_podcast_sessions_summary['end_ts'].dt.truncate('1s').dt.to_string()
                      ), axis=-1))
    fig.update_layout(yaxis_autorange='reversed',
                      yaxis_showticklabels=False,
                      yaxis_ticks='',
                      margin=dict(r=20))
    return fig
