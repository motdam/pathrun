import math

import pytest

from pathrun import geometry

def test_a_degree_of_latitude_is_about_111_km():
    assert geometry.haversine_metres(51.0, -0.0015, 52.0, -0.0015) == pytest.approx(111_195, rel=1e-3)

def test_a_degree_of_longitude_shrinks_towards_the_poles():
    """Meridians converge, so the same longitude step is a shorter distance further north."""
    at_equator = geometry.haversine_metres(0.0, 0.0, 0.0, 1.0)
    at_greenwich = geometry.haversine_metres(51.4779, 0.0, 51.4779, 1.0)
    assert at_greenwich < at_equator
    assert at_greenwich == pytest.approx(at_equator*math.cos(math.radians(51.4779)), rel=1e-3)

def test_a_point_is_no_distance_from_itself():
    assert geometry.haversine_metres(51.4779, -0.0015, 51.4779, -0.0015) == pytest.approx(0.0)

def test_distance_is_symmetric():
    forward = geometry.haversine_metres(51.4779, -0.0015, 55.9486, -3.1999)
    backward = geometry.haversine_metres(55.9486, -3.1999, 51.4779, -0.0015)
    assert forward == pytest.approx(backward)
