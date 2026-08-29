"""Loading runs exported from Strava, and picking out the ones near home.

A Strava account export puts every activity in `activities/` as GPX, with `activities.csv` holding
the name and date of each. Runs recorded away from home are kept, since they become usable once the
network for that area is loaded.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

import gpxpy

from pathrun import config, geometry

@dataclass
class Run:
    """One recorded run, as the raw GPS trace plus what Strava knew about it.

    `times` runs parallel to `points`, and is empty for a trace that carries no timestamps.
    """
    activity_id: str
    name: str
    started_at: str
    points: list
    times: list = field(default_factory=list)

    @property
    def start(self): return self.points[0]

    @property
    def recorded_km(self):
        """Distance along the raw trace, which reads slightly long because GPS noise adds wobble."""
        return sum(geometry.haversine_metres(*first, *second)
                   for first, second in zip(self.points, self.points[1:]))/1000

    def distance_from_km(self, latitude, longitude):
        """How far the run started from a given point."""
        return geometry.haversine_metres(*self.start, latitude, longitude)/1000

def activity_names(activities_csv):
    """Map of activity id to name, from the `activities.csv` in a Strava export."""
    with open(activities_csv) as handle:
        return {row['Activity ID']: row['Activity Name'] for row in csv.DictReader(handle)}

def load_run(path, name=None):
    """Read one GPX file into a `Run`, taking its name from the file if none is given."""
    with open(path) as handle: gpx = gpxpy.parse(handle)
    fixes = [point for track in gpx.tracks for segment in track.segments for point in segment.points]
    points = [(point.latitude, point.longitude) for point in fixes]
    times = [point.time for point in fixes] if fixes and fixes[0].time else []
    track_name = name or (gpx.tracks[0].name if gpx.tracks else path.stem)
    started_at = str(gpx.time) if gpx.time else ''
    return Run(activity_id=path.stem, name=track_name, started_at=started_at, points=points, times=times)

def load_runs(directory=None, activities_csv=None):
    """Every GPX in `directory` as a `Run`, skipping any file that holds no track points."""
    directory = Path(directory or config.RUNS_DIRECTORY)
    names = activity_names(activities_csv) if activities_csv else {}
    for path in sorted(directory.glob('*.gpx')):
        run = load_run(path, name=names.get(path.stem))
        if run.points: yield run

def near(runs, latitude=None, longitude=None, radius_km=None):
    """The runs that started within `radius_km` of a point, defaulting to home and the network radius."""
    latitude = config.HOME_LATITUDE if latitude is None else latitude
    longitude = config.HOME_LONGITUDE if longitude is None else longitude
    radius_km = config.NETWORK_RADIUS_METRES/1000 if radius_km is None else radius_km
    return [run for run in runs if run.distance_from_km(latitude, longitude) <= radius_km]
