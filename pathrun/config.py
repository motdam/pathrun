"""Settings, read from a `.env` file that is never committed."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT/'.env')

def _float(name):
    value = os.environ.get(name, '').strip()
    return float(value) if value else None

HOME_POSTCODE = os.environ.get('PATHRUN_HOME_POSTCODE', '').strip() or None
HOME_LATITUDE = _float('PATHRUN_HOME_LATITUDE')
HOME_LONGITUDE = _float('PATHRUN_HOME_LONGITUDE')

# Loops are generated inside this circle, so it needs to exceed the radius of your longest route
# rather than its length.
NETWORK_RADIUS_METRES = int(_float('PATHRUN_NETWORK_RADIUS_METRES') or 15_000)

CACHE_DIRECTORY = ROOT/'data'
RUNS_DIRECTORY = CACHE_DIRECTORY/'runs'/'gpx'
