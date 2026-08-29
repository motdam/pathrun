"""Applying a strategy's penalties to a graph, and measuring a finished route."""

from collections import Counter

from pathrun import network, strategy as strategies

EXCLUDED = float('inf')

def edge_cost(edge_attributes, strategy=None):
    """What it costs to run one edge, as its length weighted by how much you want to be on it."""
    strategy = strategy or strategies.DEFAULT
    if strategy.excludes(edge_attributes): return EXCLUDED
    return edge_attributes.get('length', 0.0)*strategy.penalty(edge_attributes)

def apply_costs(graph, strategy=None, attribute='cost'):
    """Write `edge_cost` onto every edge as `attribute`, so routing reads it rather than recomputing.

    Excluded edges are removed rather than left at an infinite cost, since a shortest path search that
    never chooses them still pays to consider them.
    """
    strategy = strategy or strategies.DEFAULT
    excluded = []
    for source, target, key, edge_attributes in graph.edges(keys=True, data=True):
        cost = edge_cost(edge_attributes, strategy)
        if cost == EXCLUDED: excluded.append((source, target, key))
        else:                edge_attributes[attribute] = cost
    graph.remove_edges_from(excluded)
    return graph

def route_edges(graph, route_nodes, attribute='cost'):
    """The edge chosen between each consecutive pair in `route_nodes`, cheapest where several run parallel.

    A route is stored as a list of nodes, but a `MultiDiGraph` can join two nodes with more than one
    edge, so the edge actually run has to be recovered rather than assumed.
    """
    for source, target in zip(route_nodes, route_nodes[1:]):
        parallel = graph[source][target]
        key = min(parallel, key=lambda key: parallel[key].get(attribute, parallel[key].get('length', 0.0)))
        yield source, target, parallel[key]

def score_route(graph, route_nodes, attribute='cost'):
    """Measure a finished route: how far, how much of it off road, and how much of it covered twice.

    `repeated_km` counts a path run in both directions as repeated.
    """
    highway_metres, seen, total_metres, right_of_way_metres, repeated_metres = Counter(), set(), 0.0, 0.0, 0.0
    for source, target, edge_attributes in route_edges(graph, route_nodes, attribute):
        length = edge_attributes.get('length', 0.0)
        total_metres += length
        for highway in network.tag_values(edge_attributes, 'highway') or ['untagged']: highway_metres[highway] += length
        if network.is_right_of_way(edge_attributes): right_of_way_metres += length
        edge_identity = (frozenset((source, target)), str(edge_attributes.get('osmid')))
        if edge_identity in seen: repeated_metres += length
        seen.add(edge_identity)
    if not total_metres: return {'total_km': 0.0, 'right_of_way_km': 0.0, 'right_of_way_share': 0.0,
                                 'repeated_km': 0.0, 'repeated_share': 0.0, 'highway_km': {}}
    return {'total_km':           total_metres/1000,
            'right_of_way_km':    right_of_way_metres/1000,
            'right_of_way_share': right_of_way_metres/total_metres,
            'repeated_km':        repeated_metres/1000,
            'repeated_share':     repeated_metres/total_metres,
            'highway_km':         {highway: metres/1000 for highway, metres in highway_metres.most_common()}}

def print_score(score):
    """Print the output of `score_route` as a readable summary."""
    print(f"{score['total_km']:.2f} km, {100*score['right_of_way_share']:.0f}% on rights of way, "
          f"{100*score['repeated_share']:.0f}% covered twice")
    for highway, kilometres in score['highway_km'].items():
        print(f'  {highway:<16} {kilometres:6.2f} km  {100*kilometres/score["total_km"]:5.1f}%')

def observed_minimum_penalty(graph, attribute='cost'):
    """The lowest penalty actually present in `graph`, as a tighter scale for `straight_line_heuristic`.

    A strategy's `minimum_penalty` covers every combination of tags it can imagine, most of which
    never occur. Measuring the real graph gives a larger and still admissible scale, so A* prunes more.
    """
    penalties = [attributes[attribute]/attributes['length']
                 for _, _, attributes in graph.edges(data=True) if attributes.get('length')]
    return min(penalties) if penalties else 1.0
