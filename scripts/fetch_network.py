"""Fetch and cache the network around home, then print what came back.

Pass `--refresh` to ignore the cached copy and re-query Overpass.
"""

import sys

from pathrun import config, network

refresh = '--refresh' in sys.argv
path = network.cache_path(config.HOME_LATITUDE, config.HOME_LONGITUDE, config.NETWORK_RADIUS_METRES)
print(f'{"refreshing" if refresh else "loading"} {path}\n')

graph = network.load_network(config.HOME_LATITUDE, config.HOME_LONGITUDE, config.NETWORK_RADIUS_METRES, refresh=refresh)
network.print_description(network.describe_network(graph))
