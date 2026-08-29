"""Writing a generated route out as GPX.

A route's shape lives on its edges, not its nodes. Simplification moved the points along each way
into a `geometry` attribute, so a track built from node coordinates alone would cut every corner.
"""

import gpxpy
import gpxpy.gpx

from pathrun import cost, geometry as geo

def node_point(graph, node):
    """A node's `(latitude, longitude)`, since osmnx stores them as `y` and `x`."""
    return graph.nodes[node]['y'], graph.nodes[node]['x']

def edge_points(graph, source, target, edge_attributes):
    """Every coordinate along one edge, in the direction it is being run.

    An edge's stored geometry is not guaranteed to start at the node you are travelling from, so it
    is reversed where needed rather than trusted.
    """
    line = edge_attributes.get('geometry')
    if line is None: return [node_point(graph, source), node_point(graph, target)]
    points = [(latitude, longitude) for longitude, latitude in line.coords]
    start = node_point(graph, source)
    if geo.haversine_metres(*points[0], *start) > geo.haversine_metres(*points[-1], *start): points.reverse()
    return points

def route_points(graph, route_nodes, attribute='cost'):
    """Every coordinate along a whole route, with the duplicated point at each edge seam dropped."""
    points = []
    for source, target, edge_attributes in cost.route_edges(graph, route_nodes, attribute):
        segment = edge_points(graph, source, target, edge_attributes)
        points += segment[1:] if points else segment
    return points

def route_to_gpx(graph, route_nodes, name='pathrun route', attribute='cost'):
    """A route as a GPX document, as the XML string that Strava and Garmin Connect both accept."""
    document = gpxpy.gpx.GPX()
    document.creator = 'pathrun'
    track = gpxpy.gpx.GPXTrack(name=name)
    segment = gpxpy.gpx.GPXTrackSegment()
    segment.points = [gpxpy.gpx.GPXTrackPoint(latitude, longitude)
                      for latitude, longitude in route_points(graph, route_nodes, attribute)]
    track.segments.append(segment)
    document.tracks.append(track)
    return document.to_xml()

def write_route(graph, route_nodes, path, name='pathrun route', attribute='cost'):
    """Write a route to `path` as GPX and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(route_to_gpx(graph, route_nodes, name, attribute))
    return path
