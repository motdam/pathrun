import pytest

from pathrun import runs

GREENWICH = (51.4779, -0.0015)
EDINBURGH = (55.9486, -3.1999)

def build_run(activity_id, points, name='Morning Run'):
    return runs.Run(activity_id=activity_id, name=name, started_at='2026-08-20', points=points)

def test_recorded_km_follows_the_trace_rather_than_the_straight_line():
    """A trace out and back covers twice the distance while ending where it started."""
    out_and_back = build_run('1', [GREENWICH, (51.4879, -0.0015), GREENWICH])
    assert out_and_back.recorded_km == pytest.approx(2*1.112, rel=1e-2)

def test_distance_from_measures_the_start_not_the_whole_run():
    run = build_run('1', [EDINBURGH, GREENWICH])
    assert run.distance_from_km(*GREENWICH) > 250

def test_near_keeps_local_runs_and_drops_distant_ones():
    local, away = build_run('1', [GREENWICH]), build_run('2', [EDINBURGH])
    assert runs.near([local, away], *GREENWICH, radius_km=15) == [local]

def test_near_uses_an_inclusive_radius():
    """A run starting exactly at the edge of the loaded network is still inside it."""
    edge = build_run('1', [(51.4779 + 15/111.195, -0.0015)])
    assert runs.near([edge], *GREENWICH, radius_km=15) == [edge]
