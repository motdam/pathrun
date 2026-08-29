"""Distances on the surface of the Earth."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_METRES = 6_371_000

def haversine_metres(first_latitude, first_longitude, second_latitude, second_longitude):
    """Great circle distance in metres between two points given in degrees.

    No route between two points can be shorter than this, which is what makes it usable as an A*
    heuristic.
    """
    latitude_difference = radians(second_latitude - first_latitude)
    longitude_difference = radians(second_longitude - first_longitude)
    chord = (sin(latitude_difference/2)**2
             + cos(radians(first_latitude))*cos(radians(second_latitude))*sin(longitude_difference/2)**2)
    return 2*EARTH_RADIUS_METRES*asin(sqrt(chord))
