"""Render the README example: generated loops over a network, somewhere that is not anyone's home.

Chipping Campden is used because the Cotswolds have dense public rights of way, which is the case
pathrun is built for. Regenerate with `uv run python scripts/make_example_image.py`.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import osmnx

from pathrun import cost, loops, network

LATITUDE, LONGITUDE, RADIUS_METRES = 52.0500, -1.7800, 8_000
TARGET_KM = 10
SERIES = ['#2a78d6', '#eb6834', '#1baf7a']
# Desaturated so the routes read as the subject and the network as context.
RIGHT_OF_WAY, ROAD, INK, MUTED = '#aec4b4', '#e4e4e0', '#0b0b0b', '#52514e'

def spread_by_bearing(candidates, wanted=3, minimum_separation=70):
    """Pick good candidates that head in different directions, so they do not overlap into one blob."""
    chosen = []
    for candidate in candidates:
        if all(min(abs(candidate['bearing'] - other['bearing']),
                   360 - abs(candidate['bearing'] - other['bearing'])) >= minimum_separation for other in chosen):
            chosen.append(candidate)
        if len(chosen) == wanted: break
    return chosen

graph = cost.apply_costs(network.load_network(LATITUDE, LONGITUDE, RADIUS_METRES))
start = osmnx.distance.nearest_nodes(graph, X=LONGITUDE, Y=LATITUDE)
chosen = spread_by_bearing(loops.generate_loops(graph, start, TARGET_KM, attempts=36, seed=3))

extent = [(graph.nodes[node]['x'], graph.nodes[node]['y']) for candidate in chosen for node in candidate['route']]
margin = 0.012
west, east = min(x for x, _ in extent) - margin, max(x for x, _ in extent) + margin
south, north = min(y for _, y in extent) - margin, max(y for _, y in extent) + margin

local = osmnx.truncate.truncate_graph_bbox(graph, (west, south, east, north))
colours = [RIGHT_OF_WAY if network.is_right_of_way(attributes) else ROAD
           for _, _, attributes in local.edges(data=True)]
figure, axis = osmnx.plot.plot_graph(local, edge_color=colours, edge_linewidth=1.0, node_size=0,
                                     bgcolor='white', figsize=(12, 8), show=False, close=False)
for candidate, colour in zip(chosen, SERIES):
    score = candidate['score']
    latitudes = [graph.nodes[node]['y'] for node in candidate['route']]
    longitudes = [graph.nodes[node]['x'] for node in candidate['route']]
    # A white casing under each line keeps crossings legible where routes share ground.
    axis.plot(longitudes, latitudes, color='white', linewidth=6.5, solid_capstyle='round', zorder=4)
    axis.plot(longitudes, latitudes, color=colour, linewidth=3.2, solid_capstyle='round', zorder=5,
              label=f"{score['total_km']:.1f} km  ·  {100*score['right_of_way_share']:.0f}% on rights of way")
axis.plot([LONGITUDE], [LATITUDE], marker='o', markersize=10, color=INK, markeredgecolor='white',
          markeredgewidth=2, zorder=6)
axis.set_xlim(west, east); axis.set_ylim(south, north)
axis.legend(loc='lower left', frameon=False, labelcolor=MUTED, fontsize=12)
axis.set_title('Three 10 km loops from one front door, near Chipping Campden.\n'
               'Green is public right of way, grey is road.',
               color=INK, loc='left', fontsize=13, pad=12)
figure.savefig('docs/example-routes.png', dpi=130, bbox_inches='tight', facecolor='white')
for candidate in chosen:
    score = candidate['score']
    print(f"  bearing {candidate['bearing']:5.0f}  {score['total_km']:5.2f} km  RoW {100*score['right_of_way_share']:3.0f}%")
print('wrote docs/example-routes.png')
