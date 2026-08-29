import pytest

from pathrun.strategy import AVOID_ROADS, Strategy

def test_a_right_of_way_is_cheaper_than_the_same_path_without_one():
    assert AVOID_ROADS.penalty({'highway': 'footway', 'designation': 'public_footpath'}) < AVOID_ROADS.penalty({'highway': 'footway'})

def test_busier_roads_cost_more():
    penalties = [AVOID_ROADS.penalty({'highway': highway})
                 for highway in ['path', 'footway', 'residential', 'unclassified', 'tertiary', 'secondary', 'primary']]
    assert penalties == sorted(penalties)

def test_a_pavementless_road_costs_more_than_one_with_a_pavement():
    """The safety concern this strategy exists to answer: a country lane with nowhere to step aside."""
    lane = {'highway': 'unclassified', 'sidewalk': 'no', 'maxspeed': '60 mph'}
    village = {'highway': 'unclassified', 'sidewalk': 'both', 'maxspeed': '30 mph'}
    assert AVOID_ROADS.penalty(lane) > 2*AVOID_ROADS.penalty(village)

def test_an_untagged_road_is_not_assumed_pavementless():
    """Seven roads in eight carry no sidewalk tag, so its absence cannot count against them."""
    assert AVOID_ROADS.penalty({'highway': 'unclassified'}) == AVOID_ROADS.penalty({'highway': 'unclassified', 'surface': 'asphalt'})

def test_trunk_roads_are_excluded_rather_than_expensive():
    assert AVOID_ROADS.excludes({'highway': 'trunk'})
    assert not AVOID_ROADS.excludes({'highway': 'primary'})

def test_a_way_that_forbids_walking_is_excluded():
    assert AVOID_ROADS.excludes({'highway': 'footway', 'foot': 'no'})

def test_a_merged_edge_is_judged_by_its_least_pleasant_part():
    """Simplification merges ways, so an edge part of which is a main road cannot score as a footway."""
    assert AVOID_ROADS.penalty({'highway': ['footway', 'primary']}) == AVOID_ROADS.penalty({'highway': 'primary'})

def test_an_unknown_highway_tag_falls_back_rather_than_raising():
    assert AVOID_ROADS.penalty({'highway': 'via_ferrata'}) == AVOID_ROADS.unknown_highway_penalty

def test_lit_only_matters_on_roads():
    """A footpath is never lit and should not be punished for it, unlike a fast unlit lane."""
    assert not AVOID_ROADS.is_unlit_road({'highway': 'path', 'lit': 'no'})
    assert AVOID_ROADS.is_unlit_road({'highway': 'tertiary', 'maxspeed': '60 mph', 'lit': 'no'})

def test_minimum_penalty_is_a_floor_on_every_combination():
    """A* admissibility depends on this, and an edge below the floor would break it silently."""
    combinations = [{'highway': highway, 'designation': designation, 'surface': surface,
                     'maxspeed': maxspeed, 'sidewalk': sidewalk, 'foot': foot, 'lit': 'no'}
                    for highway in AVOID_ROADS.highway_penalties
                    for surface in [*AVOID_ROADS.surface_penalties, None]
                    for maxspeed in [*AVOID_ROADS.maxspeed_penalties, None]
                    for sidewalk in [*AVOID_ROADS.sidewalk_penalties, None]
                    for foot in ['designated', None]
                    for designation in ['public_footpath', None]]
    assert min(AVOID_ROADS.penalty(tags) for tags in combinations) >= AVOID_ROADS.minimum_penalty

def test_a_strategy_needs_only_highway_penalties():
    """Adding a second strategy should not mean filling in every optional table."""
    minimal = Strategy(name='flat', description='anything goes', highway_penalties={'footway': 1.0})
    assert minimal.penalty({'highway': 'footway'}) == 1.0
    assert not minimal.excludes({'highway': 'trunk'})
