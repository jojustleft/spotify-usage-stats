# spotify-usage-stats

Analysis on Spotify Extended Streaming History data. More information on this data, including how to obtain a personal copy, can be found in [Spotify's official support page](https://support.spotify.com/uk/article/data-rights-and-privacy-settings/).

Afterwards, create an `.env` file with the path to the data itself:

```
DATA_FILEPATH="path/to/extended/streaming/history/data"
```

> <b style='color: tomato'>Note:</b> since data represents each user's music streaming history, results in the notebook are not discussed extensively as they are subjective.

## Requirements

This analysis relies extensively on [Quoi](https://github.com/jojustleft/quoi), my general toolkit for data analysis. This, as well as other dependencies can be installed locally with:

```
make venv
```
