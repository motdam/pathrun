import networkx
import pytest

from pathrun import cost
from pathrun.strategy import AVOID_ROADS

def build_route_graph():
    """A square of four 100 m edges, one a public footpath and one a trunk road, walkable either way."""
    graph = networkx.MultiDiGraph(crs='epsg:4326')
    corners = [(1, 2, 'residential'), (2, 3, 'footway'), (3, 4, 'residential'), (4, 1, 'trunk')]
    for index, (source, target, highway) in enumerate(corners):
        attributes = {'length': 100.0, 'highway': highway, 'osmid': index}
        if highway == 'footway': attributes['designation'] = 'public_footpath'
        graph.add_edge(source, target, **attributes)
        graph.add_edge(target, source, **dict(attributes))
    for index, node in enumerate(graph.nodes): graph.nodes[node].update(x=-0.0015 + index/1000, y=51.4779)
    return graph

def test_edge_cost_is_length_times_penalty():
    attributes = {'length': 200.0, 'highway': 'residential'}
    assert cost.edge_cost(attributes) == pytest.approx(200.0*AVOID_ROADS.penalty(attributes))

def test_an_excluded_edge_costs_infinity():
    assert cost.edge_cost({'length': 200.0, 'highway': 'trunk'}) == cost.EXCLUDED

def test_apply_costs_removes_excluded_edges_rather_than_pricing_them():
    """A search that never picks an edge still pays to consider it, so drop it from the graph."""
    graph = cost.apply_costs(build_route_graph())
    assert graph.number_of_edges() == 6
    assert all('cost' in attributes for _, _, attributes in graph.edges(data=True))
    assert not graph.has_edge(4, 1)

def test_score_route_measures_distance_and_right_of_way_share():
    score = cost.score_route(cost.apply_costs(build_route_graph()), [1, 2, 3, 4])
    assert score['total_km'] == pytest.approx(0.3)
    assert score['right_of_way_share'] == pytest.approx(1/3)
    assert score['repeated_share'] == pytest.approx(0.0)

def test_score_route_counts_an_out_and_back_as_repeated_ground():
    score = cost.score_route(cost.apply_costs(build_route_graph()), [1, 2, 3, 2, 1])
    assert score['total_km'] == pytest.approx(0.4)
    assert score['repeated_share'] == pytest.approx(0.5)

def test_score_route_handles_an_empty_route():
    assert cost.score_route(cost.apply_costs(build_route_graph()), [])['total_km'] == 0.0

def test_observed_minimum_penalty_is_tighter_than_the_declared_floor_but_still_admissible():
    """A tighter scale prunes more of the A* search, so long as no real edge falls below it."""
    graph = cost.apply_costs(build_route_graph())
    observed = cost.observed_minimum_penalty(graph)
    assert observed >= AVOID_ROADS.minimum_penalty
    assert all(observed <= attributes['cost']/attributes['length'] for _, _, attributes in graph.edges(data=True))
