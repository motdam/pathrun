import math
from datetime import datetime, timedelta, timezone

import pytest

from pathrun import geometry, metrics, runs

START = datetime(2026, 8, 20, 7, 0, tzinfo=timezone.utc)

# Derived from the radius the haversine itself uses, so a segment built to be 5,000 m measures 5,000 m.
# A rounded 111,195 is three millimetres short over 5 km, which is enough to fail a >= check.
DEGREES_PER_METRE = 180/(math.pi*geometry.EARTH_RADIUS_METRES)

def build_run(segments, activity_id='1', name='Morning Run'):
    """A run heading due north, from `(metres, seconds)` segments run at a constant pace within each."""
    points, times, latitude, elapsed = [(51.0, -0.0015)], [START], 51.0, 0.0
    for metres, seconds in segments:
        latitude += metres*DEGREES_PER_METRE
        elapsed += seconds
        points.append((latitude, -0.0015))
        times.append(START + timedelta(seconds=elapsed))
    return runs.Run(activity_id=activity_id, name=name, started_at='2026-08-20', points=points, times=times)

def test_progress_accumulates_distance_and_time():
    distances, elapsed = metrics.progress(build_run([(1000, 300), (1000, 300)]))
    assert distances[-1] == pytest.approx(2000, rel=1e-3)
    assert elapsed == [0.0, 300.0, 600.0]

def test_splits_are_timed_at_the_kilometre_not_at_the_nearest_fix():
    """A kilometre almost never falls on a GPS fix, so the crossing time has to be interpolated."""
    run = build_run([(1500, 450), (1500, 450)])
    split = metrics.splits(run)
    assert len(split) == 3
    for completed in split: assert completed.seconds == pytest.approx(300, rel=1e-3)

def test_splits_drop_an_incomplete_final_split():
    assert len(metrics.splits(build_run([(2500, 750)]))) == 2

def test_best_effort_finds_a_fast_stretch_inside_a_slower_run():
    """The point of a best effort: your fastest 5 km can sit in the middle of a 10 km run."""
    run = build_run([(2000, 800), (5000, 1500), (3000, 1200)])
    assert metrics.best_effort(run, 5000) == pytest.approx(1500, rel=0.02)

def test_best_effort_returns_nothing_when_the_run_is_too_short():
    assert metrics.best_effort(build_run([(3000, 900)]), 5000) is None

def test_best_effort_measures_the_distance_asked_for_not_a_longer_one():
    """Snapping the window to fixes would measure more than the distance and flatter the pace."""
    run = build_run([(900, 270)]*5)
    assert metrics.best_effort(run, 1000) == pytest.approx(300, rel=1e-3)

def test_moving_seconds_excludes_standing_still():
    run = build_run([(1000, 300), (1, 600), (1000, 300)])
    assert run.times[-1].timestamp() - run.times[0].timestamp() == pytest.approx(1200)
    assert metrics.moving_seconds(run) == pytest.approx(600, rel=1e-3)

def test_personal_records_pick_the_quickest_across_runs():
    slow = build_run([(5000, 1800)], activity_id='slow', name='Slow')
    fast = build_run([(5000, 1500)], activity_id='fast', name='Fast')
    records = metrics.personal_records([slow, fast], {'5 km': 5000.0})
    assert records['5 km'].activity_id == 'fast'
    assert records['5 km'].seconds == pytest.approx(1500, rel=0.02)

def test_personal_records_skip_a_run_with_no_timestamps():
    timeless = runs.Run(activity_id='1', name='no clock', started_at='', points=[(51.0, -0.0015), (51.1, -0.0015)])
    assert metrics.personal_records([timeless], {'1 km': 1000.0}) == {}

def test_summarise_reports_pace_against_moving_time_not_elapsed():
    run = build_run([(1000, 300), (1, 600), (1000, 300)])
    summary = metrics.summarise(run)
    assert summary['moving_seconds'] < summary['elapsed_seconds']
    assert summary['pace_seconds_per_km'] == pytest.approx(300, rel=0.02)

@pytest.mark.parametrize('seconds,expected', [(59, '0:59'), (300, '5:00'), (3600, '1:00:00'), (5461, '1:31:01')])
def test_format_duration_switches_to_hours_only_when_needed(seconds, expected):
    assert metrics.format_duration(seconds) == expected

def test_a_run_of_exactly_the_target_distance_still_counts():
    """Summing haversine hops leaves an exact 5 km measuring 4999.9999999, which must not be rejected."""
    run = build_run([(5000, 1500)])
    distances, _ = metrics.progress(run)
    assert distances[-1] < 5000, 'fixture no longer exercises the floating point boundary'
    assert metrics.best_effort(run, 5000) == pytest.approx(1500, rel=1e-6)
