from typing import Callable, Dict, List, Tuple
import numpy as np
from shapely.geometry import Polygon, LineString
from dataclasses import dataclass, field

from kikit.intervals import Interval, IntervalList

from .common import SHP_EPSILON, listGeometries
from .typing import Box

@dataclass
class BoxPolygon:
    """
    A polygon approximation via a set of non-overlapping axis-aligned rectangles.
    """
    boxes: List[Box] = field(default_factory=list)


def line_to_stairs(start: Tuple[float, float], end: Tuple[float, float],
                   allowed_deviation: float, axis_first: int = 0) -> List[Tuple[float, float]]:
    """
    Given a segment, generate an axis-aligned staircase polyline with maximal
    deviation of-segment length `allowed_deviation`. Axis first determines if
    the staircase starts with a horizontal or vertical segment.
    """
    assert allowed_deviation > 0, "Allowed deviation must be positive"
    assert axis_first in (0, 1), "Axis first must be 0 or 1"

    if start[0] == end[0] or start[1] == end[1]:
        return [start, end]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = np.hypot(dx, dy)
    dxdy_height = np.abs(dx * dy) / length
    max_length = allowed_deviation * length / dxdy_height

    segments = max(int(np.ceil(length / max_length)), 2)
    points = [start]
    dx, dy = dx / segments, dy / segments
    for i in range(segments):
        if i % 2 == axis_first:
            points.append((start[0] + (i + 1) * dx, start[1] + i * dy))
        else:
            points.append((start[0] + i * dx, start[1] + (i + 1) * dy))

    points.append(end)
    return points


def polygon_to_staircase(polygon: Polygon, allowed_deviation: float) -> Polygon:
    """
    Given a polygon, generate an axis-aligned staircase polyline with maximal
    deviation of-segment length `allowed_deviation`.
    """
    stairs = []
    initial_axis = 0
    for start, end in zip(polygon.exterior.coords, polygon.exterior.coords[1:]):
        line_stairs = line_to_stairs(start, end, allowed_deviation, initial_axis)
        initial_axis = 1 - initial_axis
        if len(stairs) > 0 and line_stairs[0] == stairs[-1]:
            stairs.pop()
        stairs.extend(line_stairs)
    return Polygon(stairs)


def cover_polygon_with_boxes(poly: Polygon) -> BoxPolygon:
    """
    Perform a vertical sweep-line partition of an orthogonal polygon (no holes),
    returning a collection of axis-aligned rectangles that exactly cover the polygon.
    """

    exterior_coords = list(poly.exterior.coords)
    xs = sorted(set(coord[0] for coord in exterior_coords))
    if len(xs) < 2:
        # Degenerate case: polygon is vertical or empty
        return []

    result_rectangles = []
    minx, miny, maxx, maxy = poly.bounds

    for x_left, x_right in zip(xs, xs[1:]):
        x_mid = 0.5 * (x_left + x_right)
        vertical_line = LineString([(x_mid, miny), (x_mid, maxy)])
        line_intersection = poly.intersection(vertical_line)

        for segment in listGeometries(line_intersection):
            coords = list(segment.coords)
            if len(coords) < 2:
                # Degenerate segment
                continue

            y1 = coords[0][1]
            y2 = coords[-1][1]
            if y1 > y2:
                y1, y2 = y2, y1

            if abs(y2 - y1) < SHP_EPSILON:
                continue

            result_rectangles.append((x_left, y1, x_right, y2))

    return BoxPolygon(result_rectangles)

class NeighbourhoodProjection:
    """
    Given a dictionary identifier-> BoxPolygons answer the query polygon edge
    projection to neighbouring walls.
    """

    @dataclass
    class Projection:
        neighbor_id: object
        start_coord: float
        end_coord: float
        interval: IntervalList

    @staticmethod
    def _prepare_projections(get_interval: Callable[[Box], Interval],
                             get_distance: Callable[[Box], float],
                             polygons: Dict[object, BoxPolygon]) -> Dict[object, List[Projection]]:

        x = [(ident, get_interval(b), get_distance(b)) for ident, b in [(ident, box) for ident, box in polygons.items()]]

    def __init__(self, polygons: Dict[object, BoxPolygon]) -> None:
        pass

    def left_projection(self, ident: object) -> List[Projection]:
        pass

    def right_projection(self, ident: object) -> List[Projection]:
        pass

    def top_projection(self, ident: object) -> List[Projection]:
        pass

    def bottom_projection(self, ident: object) -> List[Projection]:
        pass


def plot_shapely_polygon(ax, polygon: Polygon, edgecolor="black", facecolor="none", **kwargs):
    """
    Plots a shapely Polygon on a matplotlib Axes object.
    """
    import matplotlib.patches as patches

    # Get exterior coordinates
    exterior_coords = list(polygon.exterior.coords)
    # Create a Matplotlib patch
    patch = patches.Polygon(
        exterior_coords,
        closed=True,
        edgecolor=edgecolor,
        facecolor=facecolor,
        **kwargs
    )
    ax.add_patch(patch)

    # If the polygon had interior holes, we'd also plot them similarly:
    for interior in polygon.interiors:
        interior_coords = list(interior.coords)
        hole_patch = patches.Polygon(
            interior_coords,
            closed=True,
            edgecolor=edgecolor,
            facecolor="white",  # typically 'white' for holes
            **kwargs
        )
        ax.add_patch(hole_patch)
