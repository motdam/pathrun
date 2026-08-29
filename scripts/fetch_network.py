"""Fetch and cache the network around home, then print what came back.

Pass `--refresh` to ignore the cached copy and re-query Overpass.
"""

import sys

from pathrun import config, geocoding, network

refresh = '--refresh' in sys.argv
latitude, longitude = geocoding.home_coordinates()
path = network.cache_path(latitude, longitude, config.NETWORK_RADIUS_METRES)
print(f'{"refreshing" if refresh else "loading"} {path}\n')

graph = network.load_network(latitude, longitude, config.NETWORK_RADIUS_METRES, refresh=refresh)
network.print_description(network.describe_network(graph))
