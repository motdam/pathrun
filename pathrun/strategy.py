"""How a route is judged, expressed as swappable strategies.

A strategy turns an edge's OSM tags into a penalty, which is a multiplier on that edge's length. A
penalty below one makes an edge attractive, so a footpath at 0.55 means a route nearly twice as long
is still worth it to stay on the path. Above one makes an edge something to avoid, and an excluded
tag makes it unusable at any cost.

The weights live here rather than in the routing code, so adding a strategy means adding an instance
and changing nothing else. Only `AVOID_ROADS` exists today.
"""

from dataclasses import dataclass, field

from pathrun import network

@dataclass(frozen=True)
class Strategy:
    """A named set of weights for judging how much you want to run on a given edge."""
    name: str
    description: str
    highway_penalties: dict
    excluded_highways: frozenset = frozenset()
    unknown_highway_penalty: float = 1.2
    right_of_way_discount: float = 1.0
    surface_penalties: dict = field(default_factory=dict)
    maxspeed_penalties: dict = field(default_factory=dict)
    sidewalk_penalties: dict = field(default_factory=dict)
    foot_penalties: dict = field(default_factory=dict)
    unlit_road_penalty: float = 1.0

    def worst_of(self, values, penalties, default):
        """The highest penalty among `values`, so a merged edge is judged by its least pleasant part."""
        matched = [penalties[value] for value in values if value in penalties]
        return max(matched) if matched else default

    def excludes(self, edge_attributes):
        """Whether this edge is off limits entirely rather than merely expensive."""
        highways = network.tag_values(edge_attributes, 'highway')
        if any(highway in self.excluded_highways for highway in highways): return True
        return 'no' in network.tag_values(edge_attributes, 'foot')

    def penalty(self, edge_attributes):
        """Multiplier on an edge's length. Below one is preferred, above one is avoided."""
        highways = network.tag_values(edge_attributes, 'highway')
        penalty = self.worst_of(highways, self.highway_penalties, self.unknown_highway_penalty)
        if network.is_right_of_way(edge_attributes): penalty *= self.right_of_way_discount
        penalty *= self.worst_of(network.tag_values(edge_attributes, 'surface'), self.surface_penalties, 1.0)
        penalty *= self.worst_of(network.tag_values(edge_attributes, 'maxspeed'), self.maxspeed_penalties, 1.0)
        penalty *= self.worst_of(network.tag_values(edge_attributes, 'sidewalk'), self.sidewalk_penalties, 1.0)
        penalty *= self.worst_of(network.tag_values(edge_attributes, 'foot'), self.foot_penalties, 1.0)
        if self.is_unlit_road(edge_attributes): penalty *= self.unlit_road_penalty
        return penalty

    def is_unlit_road(self, edge_attributes):
        """A road explicitly tagged as unlit, which is where running in the dark gets dangerous."""
        if not network.tag_values(edge_attributes, 'maxspeed'): return False
        return 'no' in network.tag_values(edge_attributes, 'lit')

    @property
    def minimum_penalty(self):
        """The smallest multiplier any edge can carry, used to scale the A* heuristic.

        See `loops.straight_line_heuristic` for why that scaling is needed.
        """
        modifiers = [self.surface_penalties, self.maxspeed_penalties, self.sidewalk_penalties, self.foot_penalties]
        cheapest = min(self.highway_penalties.values())*min(self.right_of_way_discount, 1.0)
        for penalties in modifiers: cheapest *= min([*penalties.values(), 1.0])
        return cheapest*min(self.unlit_road_penalty, 1.0)

# A rural lane with no pavement and a 60 mph limit is a safety problem rather than a dull surface, so
# roads are pushed hard against anything carrying a legal right of way.
AVOID_ROADS = Strategy(
    name='avoid_roads',
    description='Countryside running. Prefers rights of way, treats pavementless roads as dangerous.',
    highway_penalties={
        'path':           0.50, 'bridleway':     0.50, 'track':         0.55, 'footway':       0.70,
        'pedestrian':     0.80, 'steps':         1.60, 'living_street': 1.00, 'residential':   1.20,
        'unclassified':   1.80, 'service':       1.50, 'tertiary':      3.00, 'tertiary_link': 3.00,
        'secondary':      6.00, 'secondary_link':6.00, 'primary':      12.00, 'primary_link': 12.00,
        'corridor':       1.20},
    excluded_highways=frozenset({'trunk', 'trunk_link', 'motorway', 'motorway_link', 'busway'}),
    unknown_highway_penalty=1.50,
    right_of_way_discount=0.70,
    surface_penalties={
        'grass':      1.10, 'mud':        1.35, 'sand':       1.25, 'dirt':       0.95,
        'ground':     0.95, 'earth':      0.95, 'unpaved':    0.95, 'compacted':  0.90,
        'fine_gravel':0.90, 'gravel':     1.00, 'pebblestone':1.10, 'cobblestone':1.20,
        'sett':       1.20, 'asphalt':    1.00, 'paved':      1.00, 'concrete':   1.00,
        'wood':       1.10, 'metal':      1.10},
    # Speed is the danger on a lane with nowhere to step aside, so it multiplies the road penalty.
    maxspeed_penalties={'60 mph': 1.60, '70 mph': 2.00, '50 mph': 1.35, '40 mph': 1.15,
                        '30 mph': 1.00, '20 mph': 0.95},
    # Only about one road in eight carries this tag, so an untagged road is left alone rather than
    # assumed pavementless. The highway class already assumes a country lane is unpleasant.
    sidewalk_penalties={'no': 1.45, 'none': 1.45, 'both': 0.70, 'left': 0.82, 'right': 0.82, 'separate': 0.70},
    foot_penalties={'designated': 0.90},
    unlit_road_penalty=1.15)

STRATEGIES = {strategy.name: strategy for strategy in [AVOID_ROADS]}
DEFAULT = AVOID_ROADS
