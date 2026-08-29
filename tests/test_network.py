import networkx
import pytest

from pathrun import network

def build_graph(*edges):
    """Small osmnx-shaped `MultiDiGraph` from `(source, target, attributes)` triples.

    Nodes are given `x` and `y` coordinates because `describe_network` converts to undirected, and
    osmnx compares parallel edges' geometry to decide which pairs are the same physical way.
    """
    graph = networkx.MultiDiGraph(crs='epsg:4326')
    for source, target, attributes in edges: graph.add_edge(source, target, **attributes)
    for index, node in enumerate(graph.nodes): graph.nodes[node].update(x=-0.0015 + index/1000, y=51.4779)
    return graph

def two_way(source, target, attributes):
    """The pair of directed edges osmnx uses to represent one two way path."""
    return (source, target, attributes), (target, source, dict(attributes))

@pytest.mark.parametrize('value,expected', [
    (None,                      []),
    ('footway',                 ['footway']),
    (['footway', 'path'],       ['footway', 'path'])])
def test_tag_values_handles_missing_single_and_merged_tags(value, expected):
    assert network.tag_values({'highway': value} if value is not None else {}, 'highway') == expected

def test_is_right_of_way_reads_the_designation_tag():
    assert network.is_right_of_way({'designation': 'public_footpath'})
    assert network.is_right_of_way({'designation': ['access_land', 'public_bridleway']})
    assert not network.is_right_of_way({'designation': 'permissive_footpath'})
    assert not network.is_right_of_way({'highway': 'footway'})

def test_is_right_of_way_is_independent_of_the_highway_tag():
    """A farm track that is also a public footpath is tagged as both, and both need to survive."""
    assert network.is_right_of_way({'highway': 'track', 'designation': 'public_footpath'})

def test_describe_network_totals_length_by_highway_tag():
    graph = build_graph((1, 2, {'length': 300.0, 'highway': 'footway', 'designation': 'public_footpath'}),
                        (2, 3, {'length': 700.0, 'highway': 'residential'}))
    description = network.describe_network(graph)
    assert description['nodes'] == 3
    assert description['total_km'] == pytest.approx(1.0)
    assert description['right_of_way_km'] == pytest.approx(0.3)
    assert description['highway_km'] == pytest.approx({'residential': 0.7, 'footway': 0.3})

def test_describe_network_counts_a_two_way_path_once():
    """osmnx stores a two way path as two directed edges, and summing both would double every distance."""
    graph = build_graph(*two_way(1, 2, {'length': 500.0, 'highway': 'footway'}))
    description = network.describe_network(graph)
    assert description['edges'] == 1
    assert description['total_km'] == pytest.approx(0.5)

def test_describe_network_counts_an_untagged_edge_rather_than_dropping_it():
    description = network.describe_network(build_graph((1, 2, {'length': 500.0})))
    assert description['highway_km'] == pytest.approx({'untagged': 0.5})

def test_cache_path_distinguishes_radius_and_location():
    assert network.cache_path(51.4779, -0.0015, 15000) != network.cache_path(51.4779, -0.0015, 5000)
    assert network.cache_path(51.4779, -0.0015, 15000) != network.cache_path(51.5074, -0.1278, 15000)
