# pathrun

Generates circular running routes of a target distance that stick to public footpaths and avoid roads.

![Three 10 km loops generated from one starting point near Chipping Campden](docs/example-routes.png)

Ask Strava for a 10 km loop and it will happily send you down a B road with no pavement, past a
public footpath running parallel to it through a field. pathrun loads the rights of way from
OpenStreetMap and treats them as the good option rather than an afterthought.

## Try it

```
uv sync
cp .env.example .env                        # add your postcode
uv run python scripts/fetch_network.py      # one minute, cached afterwards
```

Then open `notebooks/02_route_workbench.ipynb`, set a distance, and run it. You get candidate loops
scored on how much of each is on a right of way and how much doubles back, a map to look at them on,
and a GPX export of the one you pick.

Any app that reads GPX will follow it. OsmAnd is free, allows you to upload gpx files and works offline.

## How it works

The map is a graph: junctions are nodes and the stretch between them is an edge. A **strategy**
prices every edge as its length times a penalty, so a footpath at 0.35 means a route nearly three
times longer is still worth it. It reads `designation` for legal rights of way, then `maxspeed`,
`sidewalk`, `surface` and `foot` where present. A missing tag never counts against an edge, because
most of the network is only partly tagged.

`notebooks/01_a_map_is_a_graph.ipynb` walks through all of that against real data.


## Layout

```
pathrun/
    config.py      settings, read from .env
    geocoding.py   postcode to coordinates
    network.py     fetching and caching the graph
    strategy.py    what counts as a good route
    cost.py        applying a strategy, and scoring a route
    loops.py       circular route generation
    gpx.py         GPX export
notebooks/         01 explains the graph, 02 is the workbench
tests/
```

Everything runs through uv: `uv run pytest`, `uv run python scripts/...`.

After cloning, run `uv run pre-commit install`. That wires up the hook that strips notebook outputs
before they can be committed, which matters because those outputs contain the GPS coordinates of
wherever you run. Your `.env`, cached maps and GPX files are already ignored.

## Licence

MIT.

Map data from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, licensed under
the Open Database Licence. Routes generated from it inherit that licence.
