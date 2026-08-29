import gpxpy
import networkx
import pytest
from shapely.geometry import LineString

from pathrun import cost, geometry, gpx

def build_curved_graph():
    """Two nodes joined by an edge whose real shape bulges well away from the straight line."""
    graph = networkx.MultiDiGraph(crs='epsg:4326')
    graph.add_node(1, y=51.4779, x=-0.0015)
    graph.add_node(2, y=51.4829, x=-0.0015)
    curve = LineString([(-0.0015, 51.4779), (0.0060, 51.4804), (-0.0015, 51.4829)])
    graph.add_edge(1, 2, length=1200.0, highway='footway', designation='public_footpath', osmid=1, geometry=curve)
    graph.add_edge(2, 1, length=1200.0, highway='footway', designation='public_footpath', osmid=1, geometry=curve)
    return cost.apply_costs(graph)

def test_route_points_follow_the_edge_geometry_rather_than_cutting_the_corner():
    """Simplification discarded the shape points, so a node-only track would cut every corner."""
    graph = build_curved_graph()
    points = gpx.route_points(graph, [1, 2])
    assert len(points) == 3
    assert max(longitude for _, longitude in points) > -0.0015

def test_edge_points_are_reversed_when_running_against_the_stored_geometry():
    """An edge's geometry does not always start at the node you are travelling from."""
    graph = build_curved_graph()
    forward = gpx.route_points(graph, [1, 2])
    backward = gpx.route_points(graph, [2, 1])
    assert forward[0] == pytest.approx(backward[-1])
    assert backward[0] == pytest.approx(forward[-1])

def test_an_edge_without_geometry_falls_back_to_its_end_nodes():
    graph = networkx.MultiDiGraph(crs='epsg:4326')
    graph.add_node(1, y=51.4779, x=-0.0015)
    graph.add_node(2, y=51.4829, x=-0.0015)
    graph.add_edge(1, 2, length=556.0, highway='footway', osmid=1)
    assert len(gpx.route_points(cost.apply_costs(graph), [1, 2])) == 2

def test_route_to_gpx_parses_back_as_a_track_of_about_the_right_length():
    graph = build_curved_graph()
    document = gpxpy.parse(gpx.route_to_gpx(graph, [1, 2, 1], name='test loop'))
    assert document.tracks[0].name == 'test loop'
    points = document.tracks[0].segments[0].points
    assert len(points) == 5
    # The track must measure the curve it actually follows, not the straight line between end nodes.
    one_leg = sum(geometry.haversine_metres(*first, *second)
                  for first, second in zip(gpx.route_points(graph, [1, 2]), gpx.route_points(graph, [1, 2])[1:]))
    assert document.length_2d() == pytest.approx(2*one_leg, rel=0.02)
    assert one_leg > geometry.haversine_metres(51.4779, -0.0015, 51.4829, -0.0015)

def test_route_points_drops_the_duplicated_point_at_each_seam():
    graph = build_curved_graph()
    assert len(gpx.route_points(graph, [1, 2, 1])) == 5
