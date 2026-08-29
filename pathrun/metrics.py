"""Splits, paces and personal records, computed from GPX traces.

A best effort is not your fastest run of a given length. It is the quickest you covered that distance
at any point inside any run, including the middle of a longer one, which is what Strava and Garmin
both mean by the term.
"""

from dataclasses import dataclass

from pathrun import geometry

# Below this a runner is standing still rather than moving slowly, so the time is not counted towards
# moving pace. Roughly 33 minutes per kilometre, which no one is running.
STOPPED_SPEED_METRES_PER_SECOND = 0.5

# Summing thousands of haversine hops leaves a run built to be exactly 5,000 m measuring 4999.9999999.
# Comparisons against a target distance therefore allow a millimetre, which is five orders of
# magnitude below GPS precision and so can never change a real result.
DISTANCE_TOLERANCE_METRES = 1e-3

STANDARD_DISTANCES = {'1 km':          1_000.0,
                      '1 mile':        1_609.34,
                      '5 km':          5_000.0,
                      '10 km':        10_000.0,
                      'half marathon': 21_097.5,
                      'marathon':      42_195.0}

@dataclass(frozen=True)
class Split:
    """One completed unit of distance within a run, usually a kilometre."""
    index: int
    distance_metres: float
    seconds: float

    @property
    def pace_seconds_per_km(self): return self.seconds/(self.distance_metres/1000)

@dataclass(frozen=True)
class Record:
    """The quickest a distance was covered, and the run it happened in."""
    name: str
    distance_metres: float
    seconds: float
    activity_id: str
    run_name: str
    started_at: str

    @property
    def pace_seconds_per_km(self): return self.seconds/(self.distance_metres/1000)

def format_duration(seconds):
    """Seconds as `h:mm:ss`, or `m:ss` when under an hour."""
    seconds = round(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes}:{seconds:02d}'

def format_pace(seconds_per_km): return f'{format_duration(seconds_per_km)}/km'

def progress(run):
    """Cumulative distance in metres and elapsed seconds at each fix in `run`, from the first fix."""
    distances, elapsed = [0.0], [0.0]
    start = run.times[0]
    for previous, current, time in zip(run.points, run.points[1:], run.times[1:]):
        distances.append(distances[-1] + geometry.haversine_metres(*previous, *current))
        elapsed.append((time - start).total_seconds())
    return distances, elapsed

def moving_seconds(run):
    """Elapsed time with stationary stretches removed, which is what pace should be measured against."""
    distances, elapsed = progress(run)
    total = 0.0
    for index in range(1, len(distances)):
        gap_seconds = elapsed[index] - elapsed[index-1]
        gap_metres = distances[index] - distances[index-1]
        if gap_seconds > 0 and gap_metres/gap_seconds >= STOPPED_SPEED_METRES_PER_SECOND: total += gap_seconds
    return total

def splits(run, split_metres=1000.0):
    """Time taken for each complete `split_metres` of `run`, with any part split at the end dropped.

    The moment a split is completed almost never lands on a GPS fix, so the crossing time is
    interpolated between the fixes either side rather than rounded to the nearest one.
    """
    distances, elapsed = progress(run)
    if len(distances) < 2: return []
    completed, index, previous_time = [], 1, 0.0
    target = split_metres
    while target <= distances[-1] + DISTANCE_TOLERANCE_METRES:
        while index < len(distances) - 1 and distances[index] < target: index += 1
        crossing = interpolate(target, distances[index-1], distances[index], elapsed[index-1], elapsed[index])
        completed.append(Split(index=len(completed) + 1, distance_metres=split_metres, seconds=crossing - previous_time))
        previous_time, target = crossing, target + split_metres
    return completed

def interpolate(distance, lower_distance, upper_distance, lower_time, upper_time):
    """The time at `distance`, assuming a constant pace between the two fixes either side of it."""
    span = upper_distance - lower_distance
    if span <= 0: return lower_time
    return lower_time + (upper_time - lower_time)*(distance - lower_distance)/span

def best_effort(run, distance_metres):
    """The quickest `distance_metres` covered anywhere inside `run`, or `None` if it never got that far.

    A window is slid over the trace, and its trailing edge is interpolated so the window measures the
    distance asked for rather than the slightly longer one that landing on a fix would give.
    """
    distances, elapsed = progress(run)
    if distances[-1] < distance_metres - DISTANCE_TOLERANCE_METRES: return None
    best, trailing = None, 0
    for leading in range(1, len(distances)):
        while distances[leading] - distances[trailing+1] >= distance_metres: trailing += 1
        if distances[leading] - distances[trailing] < distance_metres - DISTANCE_TOLERANCE_METRES: continue
        start_distance = max(distances[leading] - distance_metres, distances[trailing])
        start_time = interpolate(start_distance, distances[trailing], distances[trailing+1],
                                 elapsed[trailing], elapsed[trailing+1])
        duration = elapsed[leading] - start_time
        if best is None or duration < best: best = duration
    return best

def personal_records(runs, distances=None):
    """The quickest each standard distance was ever covered, across every run given.

    Runs without timestamps are skipped.
    """
    distances = distances or STANDARD_DISTANCES
    best = {}
    for run in runs:
        if len(run.times) != len(run.points) or len(run.points) < 2: continue
        for name, distance_metres in distances.items():
            seconds = best_effort(run, distance_metres)
            if seconds is None: continue
            if name not in best or seconds < best[name].seconds:
                best[name] = Record(name=name, distance_metres=distance_metres, seconds=seconds,
                                    activity_id=run.activity_id, run_name=run.name, started_at=run.started_at)
    return best

def summarise(run):
    """Distance, moving time and moving pace for one run."""
    distances, elapsed = progress(run)
    moving = moving_seconds(run)
    kilometres = distances[-1]/1000
    return {'activity_id':        run.activity_id,
            'name':               run.name,
            'started_at':         run.started_at,
            'distance_km':        kilometres,
            'elapsed_seconds':    elapsed[-1],
            'moving_seconds':     moving,
            'pace_seconds_per_km': moving/kilometres if kilometres else 0.0}

def print_records(records):
    """Print the output of `personal_records`, longest distance last."""
    for record in sorted(records.values(), key=lambda record: record.distance_metres):
        print(f'  {record.name:<14} {format_duration(record.seconds):>8}   {format_pace(record.pace_seconds_per_km):>9}   '
              f'{record.started_at[:10]}  {record.run_name}')
