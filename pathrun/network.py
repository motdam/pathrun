"""Fetching the walkable network around home, caching it, and describing what came back."""

from collections import Counter

import osmnx

from pathrun import config

# osmnx keeps `highway` by default but discards these, and they are what separate a public right of
# way from a driveway, and a firm track from a muddy field edge.
osmnx.settings.useful_tags_way += ['designation', 'surface', 'sac_scale', 'tracktype', 'lit', 'footway',
                                   'sidewalk', 'foot', 'segregated', 'width', 'smoothness']

RIGHT_OF_WAY_DESIGNATIONS = {'public_footpath', 'public_bridleway', 'restricted_byway', 'byway_open_to_all_traffic'}

def cache_path(latitude, longitude, radius_metres):
    """Where the GraphML for one `latitude`, `longitude` and `radius_metres` combination is cached."""
    return config.CACHE_DIRECTORY/f'network_{latitude:.5f}_{longitude:.5f}_{radius_metres}.graphml'

def load_network(latitude, longitude, radius_metres, refresh=False):
    """Walkable network within `radius_metres` of a point, fetched from Overpass and cached to disk.

    Overpass is slow and rate limited, so the graph is reused from `cache_path` unless `refresh` is set.
    """
    path = cache_path(latitude, longitude, radius_metres)
    if path.exists() and not refresh: return osmnx.load_graphml(path)
    graph = osmnx.graph.graph_from_point((latitude, longitude), dist=radius_metres, network_type='walk', simplify=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    osmnx.save_graphml(graph, path)
    return graph

def tag_values(edge_attributes, tag):
    """Values of `tag` on one edge, as a list, since simplification merges ways and leaves lists behind."""
    value = edge_attributes.get(tag)
    if value is None: return []
    return value if isinstance(value, list) else [value]

def is_right_of_way(edge_attributes):
    """Whether an edge carries a legally protected right of way, by its `designation` tag."""
    return any(value in RIGHT_OF_WAY_DESIGNATIONS for value in tag_values(edge_attributes, 'designation'))

def describe_network(graph):
    """Counts of nodes, edges and total length, broken down by `highway` tag and by right of way status.

    Lengths are measured on the undirected graph, since osmnx stores a two way path as two directed
    edges and summing both would double every distance.
    """
    graph = osmnx.convert.to_undirected(graph)
    highway_lengths, right_of_way_metres, total_metres = Counter(), 0.0, 0.0
    for _, _, edge_attributes in graph.edges(data=True):
        length = edge_attributes.get('length', 0.0)
        total_metres += length
        for highway in tag_values(edge_attributes, 'highway') or ['untagged']: highway_lengths[highway] += length
        if is_right_of_way(edge_attributes): right_of_way_metres += length
    return {'nodes':          graph.number_of_nodes(),
            'edges':          graph.number_of_edges(),
            'total_km':       total_metres/1000,
            'right_of_way_km': right_of_way_metres/1000,
            'highway_km':     {highway: metres/1000 for highway, metres in highway_lengths.most_common()}}

def print_description(description):
    """Print the output of `describe_network` as a readable summary."""
    print(f"{description['nodes']:,} nodes, {description['edges']:,} edges, {description['total_km']:,.0f} km of ways")
    right_of_way_share = 100*description['right_of_way_km']/description['total_km']
    print(f"{description['right_of_way_km']:,.0f} km on designated rights of way ({right_of_way_share:.1f}%)\n")
    for highway, kilometres in description['highway_km'].items():
        print(f'  {highway:<18} {kilometres:8,.1f} km  {100*kilometres/description["total_km"]:5.1f}%')
