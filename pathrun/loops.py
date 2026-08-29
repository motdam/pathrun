"""Generating circular routes of a target length.

The cheapest route from a node back to itself is to stay put, and constraining a circuit to a target
length is related to the travelling salesman problem, so everything here is heuristics. Two
generators run because they fail differently, and sampling both beats either alone.
"""

import random
from math import asin, atan2, cos, degrees, radians, sin

import networkx
import osmnx

from pathrun import cost as costing, geometry

def point_at(latitude, longitude, bearing_degrees, distance_metres):
    """The point reached by travelling `distance_metres` along `bearing_degrees` from a start point."""
    angular = distance_metres/geometry.EARTH_RADIUS_METRES
    start_latitude, bearing = radians(latitude), radians(bearing_degrees)
    end_latitude = asin(sin(start_latitude)*cos(angular) + cos(start_latitude)*sin(angular)*cos(bearing))
    end_longitude = radians(longitude) + atan2(sin(bearing)*sin(angular)*cos(start_latitude),
                                               cos(angular) - sin(start_latitude)*sin(end_latitude))
    return degrees(end_latitude), (degrees(end_longitude) + 540) % 360 - 180

def node_at(graph, start_node, bearing_degrees, distance_metres):
    """The graph node nearest the point `distance_metres` away on `bearing_degrees` from `start_node`."""
    latitude, longitude = graph.nodes[start_node]['y'], graph.nodes[start_node]['x']
    target_latitude, target_longitude = point_at(latitude, longitude, bearing_degrees, distance_metres)
    return osmnx.distance.nearest_nodes(graph, X=target_longitude, Y=target_latitude)

def straight_line_heuristic(graph, scale):
    """An A* heuristic in cost units, scaled by `scale` so it never overestimates.

    Weights are lengths times a penalty that can fall below one, so a route can cost less than its
    length and raw distance would overestimate. Scaling by the smallest penalty any edge carries
    keeps the estimate a lower bound, which is what A* needs to stay correct.
    """
    def heuristic(node, goal):
        return scale*geometry.haversine_metres(graph.nodes[node]['y'], graph.nodes[node]['x'],
                                               graph.nodes[goal]['y'], graph.nodes[goal]['x'])
    return heuristic

def penalising_weight(used_edges, multiplier, attribute='cost'):
    """A weight function that inflates the cost of edges already run, to discourage retracing."""
    def weight(source, target, parallel):
        cheapest = min(attributes.get(attribute, attributes.get('length', 1.0)) for attributes in parallel.values())
        return cheapest*multiplier if frozenset((source, target)) in used_edges else cheapest
    return weight

def route_between(graph, source, target, heuristic, weight='cost'):
    """Cheapest route between two nodes, or `None` where no route exists."""
    if source == target: return [source]
    try: return networkx.astar_path(graph, source, target, heuristic=heuristic, weight=weight)
    except (networkx.NetworkXNoPath, networkx.NodeNotFound): return None

def join(*legs):
    """Join consecutive route legs into one node list, dropping the duplicated joint at each seam."""
    if any(leg is None for leg in legs): return None
    joined = list(legs[0])
    for leg in legs[1:]: joined += leg[1:]
    return joined

def waypoint_loop(graph, start_node, radius_metres, bearing_degrees, heuristic, weight='cost'):
    """A rough triangle out to two waypoints `radius_metres` away, 120 degrees apart.

    Spreads a route across the map and is fast, but nothing here prevents retracing.
    """
    first = node_at(graph, start_node, bearing_degrees, radius_metres)
    second = node_at(graph, start_node, (bearing_degrees + 120) % 360, radius_metres)
    return join(route_between(graph, start_node, first, heuristic, weight),
                route_between(graph, first, second, heuristic, weight),
                route_between(graph, second, start_node, heuristic, weight))

def penalised_return_loop(graph, start_node, radius_metres, bearing_degrees, heuristic, retrace_penalty=6.0):
    """Out to a point `radius_metres` away, then home with every edge already used made expensive.

    This attacks retracing directly. Its weakness is a place with few connections, such as a village
    with one road in, where no acceptable return exists and it gives up.
    """
    far_node = node_at(graph, start_node, bearing_degrees, radius_metres)
    outward = route_between(graph, start_node, far_node, heuristic)
    if outward is None: return None
    used = {frozenset(pair) for pair in zip(outward, outward[1:])}
    homeward = route_between(graph, far_node, start_node, heuristic, weight=penalising_weight(used, retrace_penalty))
    return join(outward, homeward)

GENERATORS = {'waypoint': waypoint_loop, 'penalised_return': penalised_return_loop}

# How far out to place waypoints on the first attempt, as a fraction of the target distance. These are
# only a starting point for `fit_loop`, which measures what comes back and corrects.
INITIAL_RADIUS_FRACTION = {'waypoint': 1/5.5, 'penalised_return': 1/3.2}

# Below this the two ends of a bracket produce the same pair of routes, so bisecting further is waste.
MINIMUM_BRACKET_METRES = 25.0

def route_length_metres(graph, route_nodes, attribute='cost'):
    """How far a route actually is on the ground, ignoring what it cost to choose it."""
    return sum(attributes.get('length', 0.0) for _, _, attributes in route_edges(graph, route_nodes, attribute))

def route_edges(graph, route_nodes, attribute='cost'):
    """The edge chosen between each consecutive pair of nodes, cheapest where several run parallel."""
    return costing.route_edges(graph, route_nodes, attribute)

def fit_loop(graph, start_node, generator_name, target_metres, bearing_degrees, heuristic, tolerance=0.1, rounds=5, observer=None):
    """Adjust the waypoint radius until the route that comes back is near `target_metres`.

    Straight line placement underestimates length badly, because avoiding roads sends a route
    wandering, so the radius is corrected from what came back rather than modelled.

    Scaling alone can cycle forever, because nudging a waypoint may snap it to a different node and
    length does not move smoothly with radius. So scaling runs only until one radius is too short and
    another too long, after which the search bisects that bracket and cannot cycle.

    `observer` is called with each attempt, so a caller can watch the search converge.
    """
    generator = GENERATORS[generator_name]
    radius = target_metres*INITIAL_RADIUS_FRACTION[generator_name]
    best, shortest_too_long, longest_too_short = None, None, None
    for attempt in range(rounds):
        route = generator(graph, start_node, radius, bearing_degrees, heuristic)
        if route is None or len(route) < 4: return best
        length = route_length_metres(graph, route)
        if not length: return best
        error = abs(length - target_metres)/target_metres
        if observer: observer({'round': attempt, 'bearing': bearing_degrees, 'generator': generator_name,
                               'radius_metres': radius, 'length_metres': length, 'error': error, 'route': route})
        if best is None or error < best[1]: best = (route, error)
        if error <= tolerance: return best
        if length < target_metres: longest_too_short = max(radius, longest_too_short or 0.0)
        else:                      shortest_too_long = min(radius, shortest_too_long or radius)
        if longest_too_short is not None and shortest_too_long is not None:
            if shortest_too_long <= longest_too_short: return best
            # A bracket this narrow means the target falls in a gap between routes the network can
            # actually produce, so further bisection just refines a radius that cannot reach it.
            if shortest_too_long - longest_too_short < MINIMUM_BRACKET_METRES: return best
            radius = (longest_too_short + shortest_too_long)/2
        else:
            # Damped so a wildly wrong first guess does not overshoot into a different part of the map.
            radius *= 1 + 0.8*(target_metres/length - 1)
    return best

def generate_loops(graph, start_node, target_km, attempts=48, tolerance=0.1, seed=None, observer=None):
    """Candidate loops from evenly spread bearings, kept if within `tolerance` of `target_km`.

    Ranked by `quality`, which favours rights of way and penalises ground covered twice.
    """
    heuristic = straight_line_heuristic(graph, costing.observed_minimum_penalty(graph))
    target_metres = target_km*1000
    bearings = [index*360/attempts for index in range(attempts)]
    random.Random(seed).shuffle(bearings)
    candidates = []
    for index, bearing in enumerate(bearings):
        generator_name = 'waypoint' if index % 2 else 'penalised_return'
        fitted = fit_loop(graph, start_node, generator_name, target_metres, bearing, heuristic, tolerance, observer=observer)
        if fitted is None: continue
        route, error = fitted
        if error > tolerance: continue
        candidates.append({'route': route, 'score': costing.score_route(graph, route),
                           'bearing': bearing, 'generator': generator_name})
    return sorted(candidates, key=quality, reverse=True)

def quality(candidate):
    """How good a candidate loop is, as its right of way share less the ground it covers twice."""
    return candidate['score']['right_of_way_share'] - candidate['score']['repeated_share']
