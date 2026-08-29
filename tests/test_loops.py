import networkx
import pytest

from pathrun import cost, geometry, loops

GREENWICH = (51.4779, -0.0015)

def test_point_at_travels_the_distance_asked_for():
    latitude, longitude = loops.point_at(*GREENWICH, bearing_degrees=42, distance_metres=1500)
    assert geometry.haversine_metres(*GREENWICH, latitude, longitude) == pytest.approx(1500, rel=1e-3)

def test_point_at_heads_in_the_direction_asked_for():
    north = loops.point_at(*GREENWICH, bearing_degrees=0, distance_metres=1000)
    east = loops.point_at(*GREENWICH, bearing_degrees=90, distance_metres=1000)
    assert north[0] > GREENWICH[0] and north[1] == pytest.approx(GREENWICH[1])
    assert east[1] > GREENWICH[1] and east[0] == pytest.approx(GREENWICH[0], abs=1e-4)

def test_point_at_wraps_longitude_rather_than_running_off_the_end():
    _, longitude = loops.point_at(0.0, 179.99, bearing_degrees=90, distance_metres=5000)
    assert -180 <= longitude <= 180

def test_join_drops_the_duplicated_node_at_each_seam():
    assert loops.join([1, 2, 3], [3, 4, 5], [5, 6]) == [1, 2, 3, 4, 5, 6]

def test_join_gives_up_when_any_leg_is_missing():
    assert loops.join([1, 2], None, [3, 4]) is None

def test_penalising_weight_inflates_only_the_edges_already_used():
    weight = loops.penalising_weight({frozenset((1, 2))}, multiplier=6.0)
    parallel = {0: {'cost': 100.0}, 1: {'cost': 250.0}}
    assert weight(1, 2, parallel) == pytest.approx(600.0)
    assert weight(2, 3, parallel) == pytest.approx(100.0)

def build_grid(size=9, spacing_metres=200):
    """A lattice of footpaths, so there is somewhere for a loop to actually go.

    Nodes are numbered rather than keyed by coordinate because osmnx indexes them with pandas, which
    reads a tuple as a multi level index and fails.
    """
    def node_id(row, column): return row*size + column
    graph = networkx.MultiDiGraph(crs='epsg:4326')
    for row in range(size):
        for column in range(size):
            latitude, longitude = loops.point_at(*GREENWICH, 0, row*spacing_metres)
            latitude, longitude = loops.point_at(latitude, longitude, 90, column*spacing_metres)
            graph.add_node(node_id(row, column), y=latitude, x=longitude)
    for row in range(size):
        for column in range(size):
            for neighbour_row, neighbour_column in [(row + 1, column), (row, column + 1)]:
                if neighbour_row >= size or neighbour_column >= size: continue
                source, target = node_id(row, column), node_id(neighbour_row, neighbour_column)
                attributes = {'length': float(spacing_metres), 'highway': 'footway',
                              'designation': 'public_footpath', 'osmid': f'{source}-{target}'}
                graph.add_edge(source, target, **attributes)
                graph.add_edge(target, source, **dict(attributes))
    return cost.apply_costs(graph)

CENTRE = 4*9 + 4

def test_generate_loops_returns_circuits_of_about_the_right_length():
    graph = build_grid()
    candidates = loops.generate_loops(graph, CENTRE, target_km=2.0, attempts=8, tolerance=0.2, seed=0)
    assert candidates, 'expected at least one loop on a 9x9 lattice'
    for candidate in candidates:
        assert candidate['route'][0] == candidate['route'][-1] == CENTRE
        assert abs(candidate['score']['total_km'] - 2.0) <= 0.2*2.0

def test_generate_loops_is_reproducible_for_a_given_seed():
    graph = build_grid()
    first = loops.generate_loops(graph, CENTRE, target_km=2.0, attempts=8, seed=7)
    second = loops.generate_loops(graph, CENTRE, target_km=2.0, attempts=8, seed=7)
    assert [candidate['route'] for candidate in first] == [candidate['route'] for candidate in second]

def test_the_penalised_return_generator_retraces_less_than_the_waypoint_one():
    """The whole reason two generators exist: they fail differently, so both are sampled."""
    graph = build_grid()
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    retraced = {}
    for name, generator in loops.GENERATORS.items():
        shares = []
        for bearing in range(0, 360, 45):
            route = generator(graph, CENTRE, 600, bearing, heuristic)
            if route and len(route) > 3: shares.append(cost.score_route(graph, route)['repeated_share'])
        retraced[name] = sum(shares)/len(shares)
    assert retraced['penalised_return'] < retraced['waypoint']

def test_fit_loop_corrects_a_radius_that_is_wildly_wrong():
    """Straight line placement underestimates length badly, so the radius has to be measured back."""
    # A finer lattice than the default, so a 2 km target is not limited by 200 m granularity.
    size, spacing = 17, 60
    graph = build_grid(size=size, spacing_metres=spacing)
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    centre = (size//2)*size + size//2
    fitted = loops.fit_loop(graph, centre, 'penalised_return', 2000, 45, heuristic, tolerance=0.1)
    assert fitted is not None
    route, error = fitted
    assert error <= 0.1
    assert loops.route_length_metres(graph, route) == pytest.approx(2000, rel=0.1)

def test_fit_loop_returns_its_closest_attempt_when_it_cannot_hit_the_target():
    """A 9x9 lattice cannot produce a 50 km loop, and the caller filters on the error it reports."""
    graph = build_grid()
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    fitted = loops.fit_loop(graph, CENTRE, 'waypoint', 50_000, 0, heuristic, tolerance=0.1)
    assert fitted is None or fitted[1] > 0.1

def test_fit_loop_reports_every_attempt_to_an_observer():
    """The notebook watches the search converge, so each round has to be visible, not just the result."""
    graph = build_grid()
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    attempts = []
    loops.fit_loop(graph, CENTRE, 'penalised_return', 2000, 45, heuristic, tolerance=0.01, rounds=4, observer=attempts.append)
    assert attempts
    assert {'round', 'bearing', 'generator', 'radius_metres', 'length_metres', 'error'} <= set(attempts[0])
    assert [attempt['round'] for attempt in attempts] == list(range(len(attempts)))

def test_fit_loop_narrows_its_radius_rather_than_oscillating():
    """Radius and length do not move together, so proportional correction alone can cycle forever.

    The target here falls in a gap between lengths the lattice can produce, which is exactly the case
    that used to cycle. Bisection cannot: each round the radius interval must shrink.
    """
    graph = build_grid(size=17, spacing_metres=60)
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    centre = (17//2)*17 + 17//2
    attempts = []
    loops.fit_loop(graph, centre, 'waypoint', 1800, 105, heuristic, tolerance=0.001, rounds=8, observer=attempts.append)
    radii = [attempt['radius_metres'] for attempt in attempts]
    steps = [abs(second - first) for first, second in zip(radii, radii[1:])]
    assert steps, 'expected more than one attempt'
    assert steps[-1] < steps[0], f'radius is not converging: {radii}'

def test_fit_loop_gives_up_once_the_bracket_collapses():
    """A target between two achievable lengths cannot be reached, so stop rather than burn rounds."""
    graph = build_grid(size=17, spacing_metres=60)
    heuristic = loops.straight_line_heuristic(graph, cost.observed_minimum_penalty(graph))
    centre = (17//2)*17 + 17//2
    attempts = []
    loops.fit_loop(graph, centre, 'waypoint', 1800, 105, heuristic, tolerance=0.001, rounds=40, observer=attempts.append)
    assert len(attempts) < 40
