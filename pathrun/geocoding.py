"""Turning a postcode into the coordinates the rest of the app works in."""

import osmnx
from pathrun import config

def geocode_postcode(postcode):
    """Resolve a UK postcode to a `(latitude, longitude)` pair via Nominatim."""
    return osmnx.geocoder.geocode(f'{postcode}, United Kingdom')

def home_coordinates():
    """Home as `(latitude, longitude)`, from explicit coordinates if set and the postcode otherwise."""
    if config.HOME_LATITUDE is not None and config.HOME_LONGITUDE is not None:
        return config.HOME_LATITUDE, config.HOME_LONGITUDE
    if config.HOME_POSTCODE: return geocode_postcode(config.HOME_POSTCODE)
    raise ValueError('Set HOME_POSTCODE, or HOME_LATITUDE and HOME_LONGITUDE, in pathrun/config.py.')
