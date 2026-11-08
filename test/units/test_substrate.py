import pytest
from shapely.geometry import Point
from kikit.substrate import *

def test_biteBoundary():
    l1 = LineString([ (0, 0), (1, 0), (1, 1), (0, 1)])
    l2 = LineString([ (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    l3 = LinearRing([ (0, 0), (1, 0), (1, 1), (0, 1)])

    t1 = biteBoundary(l1, Point(1, 0.5), Point(0.5, 1), 0.01)
    assert t1 == LineString([(1, 0.5), (1, 1), (0.5, 1)])

    t2 = biteBoundary(l1, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t2 is None

    t3 = biteBoundary(l2, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t3 == LineString([(0, 0.5), (0, 0), (0.5, 0)])

    t4 = biteBoundary(l3, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t4 == LineString([(0, 0.5), (0, 0), (0.5, 0)])

    t5 = biteBoundary(l1, Point(1, 0.25), Point(1, 0.75), 0.1)
    assert t5 == LineString([(1, 0.25), (1, 0.75)])


def test_tabFilletAcrossShortSegments():
    # Tiny notches occur where existing tabs overlap the frame (issue #949).
    hole = [
        (0, -5), (0, -0.751), (0.005, -0.751), (-0.002, -0.744),
        (-0.002, 0.744), (0.005, 0.751), (0, 0.751), (0, 6.949),
        (0.005, 6.949), (-0.002, 6.956), (-0.002, 8.444),
        (0, 8.451), (0, 12.55), (30, 12.55), (30, -5)
    ]
    frame = Substrate([])
    frame.union(Polygon(
        [(fromMm(x), fromMm(y)) for x, y in
         [(-5, -10), (35, -10), (35, 18), (-5, 18)]],
        [[(fromMm(x), fromMm(y)) for x, y in hole]]
    ))

    tab, _ = frame.tab((fromMm(10.5), 0), (-1, 0), fromMm(1.5), fillet=fromMm(1))
    frame.union(tab)
    assert frame.substrates.is_valid
    assert frame.substrates.boundary.distance(Point(0, fromMm(4))) < 1
    assert len(frame.circles) == 2


def test_tabFilletRejectsInsufficientTabLength():
    frame = Substrate([])
    frame.union(Polygon([(-fromMm(10), -fromMm(10)), (0, -fromMm(10)),
                         (0, fromMm(10)), (-fromMm(10), fromMm(10))]))
    with pytest.raises(TabError, match="does not fit"):
        frame.tab((fromMm(0.1), 0), (-1, 0), fromMm(1.5), fillet=fromMm(1))


@pytest.mark.parametrize("angle", [0, 13, 45, 90, 137])
@pytest.mark.parametrize("hole", [False, True])
@pytest.mark.parametrize("radius", [0.25, 1, 3])
@pytest.mark.parametrize("skew", [-15, 0, 15])
def test_tabFilletPrecision(angle, hole, radius, skew):
    from shapely.affinity import rotate
    from shapely.geometry import box

    radians = np.deg2rad(angle)
    rotation = np.array([[np.cos(radians), -np.sin(radians)],
                         [np.sin(radians), np.cos(radians)]])
    geometry = box(-fromMm(10), -fromMm(10), 0, fromMm(10))
    if hole:
        geometry = box(-fromMm(10), -fromMm(10), fromMm(20), fromMm(10)).difference(
            box(0, -fromMm(8), fromMm(18), fromMm(8)))
    frame = Substrate([])
    frame.union(rotate(geometry, angle, origin=(0, 0)))
    direction = [-np.cos(np.deg2rad(skew)), np.sin(np.deg2rad(skew))]
    tab, face = frame.tab(rotation @ [fromMm(5), 0], rotation @ direction,
                          fromMm(1.5), fillet=fromMm(radius))
    frame.union(tab)
    assert frame.substrates.is_valid
    assert isinstance(face, LineString)
    # The straight wall outside the two fillets must not move.
    for y in [7, 7.5]:
        assert frame.substrates.boundary.distance(Point(rotation @ [0, fromMm(y)])) < 1

    shapes = frame.serialize(reconstructArcs=True)
    arcs = [s for s in shapes if s.GetShape() == STROKE_T.S_ARC]
    assert len(arcs) == 2
    for arc in arcs:
        assert abs(arc.GetRadius() - fromMm(radius)) <= 100  # 0.1 um, including KiCad quantization.
        for endpoint in [arc.GetStart(), arc.GetEnd()]:
            matches = [s for s in shapes if s.GetShape() == STROKE_T.S_SEGMENT
                       and tuple(endpoint) in [tuple(s.GetStart()), tuple(s.GetEnd())]]
            assert len(matches) == 1
            line = np.array(matches[0].GetEnd()) - np.array(matches[0].GetStart())
            normal = np.array(endpoint) - np.array(arc.GetCenter())
            # Tangency error measured as a distance, rather than an angle depending on radius.
            assert abs(np.dot(normal, line / np.linalg.norm(line))) <= 100


@pytest.mark.parametrize("radius", [0.01, 1, 200])
def test_arcChordErrorAndCircleSerialization(radius):
    circle = pcbnew.PCB_SHAPE()
    circle.SetShape(STROKE_T.S_CIRCLE)
    circle.SetLayer(Layer.Edge_Cuts)
    circle.SetCenter(pcbnew.VECTOR2I(fromMm(30), fromMm(40)))
    circle.SetRadius(fromMm(radius))
    points = np.array(approximateArc(circle, getEndPoint(circle)))
    assert np.max(np.abs(points.min(axis=0) - (np.array(circle.GetCenter()) - fromMm(radius)))) < 0.001
    assert np.max(np.abs(points.max(axis=0) - (np.array(circle.GetCenter()) + fromMm(radius)))) < 0.001
    middle = (points[:-1] + points[1:]) / 2
    errors = fromMm(radius) - np.linalg.norm(middle - np.array(circle.GetCenter()), axis=1)
    assert max(errors) <= ARC_CHORD_ERROR + 0.001

    substrate = Substrate([circle])
    panel = Substrate([])
    panel.union(substrate)
    panel.translate((fromMm(10), -fromMm(20)))
    shapes = panel.serialize(reconstructArcs=True)
    assert len(shapes) == 1
    assert shapes[0].GetShape() == STROKE_T.S_CIRCLE
    assert tuple(shapes[0].GetCenter()) == (fromMm(40), fromMm(20))
    assert shapes[0].GetRadius() == fromMm(radius)


@pytest.mark.parametrize("angle", [0, 13, 45, 137, 270])
@pytest.mark.parametrize("boardRadius", [3, 10])
@pytest.mark.parametrize("radius", [0.25, 1])
@pytest.mark.parametrize("splitOutline", [False, True])
@pytest.mark.parametrize("skew", [0, 15])
def test_circularBoardTabFilletPrecision(angle, boardRadius, radius, splitOutline, skew):
    center = np.array([fromMm(30), fromMm(40)], dtype=float)
    r = fromMm(boardRadius)
    if splitOutline:
        factory = Substrate([])
        angles = np.linspace(0, 2 * np.pi, 9)
        points = center + r * np.column_stack((np.cos(angles), np.sin(angles)))
        outline = [factory._constructArc(*points[i:i+3]) for i in range(0, 8, 2)]
    else:
        circle = pcbnew.PCB_SHAPE()
        circle.SetShape(STROKE_T.S_CIRCLE)
        circle.SetLayer(Layer.Edge_Cuts)
        circle.SetCenter(toKiCADPoint(center))
        circle.SetRadius(r)
        outline = [circle]
    board = Substrate(outline)
    radians = np.deg2rad(angle)
    rotation = np.array([[np.cos(radians), -np.sin(radians)],
                         [np.sin(radians), np.cos(radians)]])
    direction = rotation @ [-np.cos(np.deg2rad(skew)), np.sin(np.deg2rad(skew))]
    tab, face = board.tab(center + rotation @ [r + fromMm(5), 0], direction,
                          fromMm(1.5), fillet=fromMm(radius))
    board.union(tab)
    assert board.substrates.is_valid
    assert isinstance(face, LineString)
    shapes = board.serialize(reconstructArcs=True)
    assert len(extractRings(shapes)) == 1
    fillets = [s for s in shapes if s.GetShape() == STROKE_T.S_ARC
               and abs(s.GetRadius() - fromMm(radius)) <= 100]
    assert len(fillets) == 2
    for fillet in fillets:
        neighbours = []
        for point in [fillet.GetStart(), fillet.GetEnd()]:
            matches = [s for s in shapes if s is not fillet and
                       tuple(point) in [tuple(s.GetStart()), tuple(s.GetEnd())]]
            assert len(matches) == 1
            neighbour = matches[0]
            neighbours.append(neighbour.GetShape())
            normal = np.array(point) - np.array(fillet.GetCenter())
            if neighbour.GetShape() == STROKE_T.S_SEGMENT:
                tangent = np.array(neighbour.GetEnd()) - np.array(neighbour.GetStart())
                assert abs(np.dot(normal, tangent / np.linalg.norm(tangent))) <= 100
            else:
                assert neighbour.GetShape() == STROKE_T.S_ARC
                assert abs(neighbour.GetRadius() - r) <= 100
                sourceNormal = np.array(point) - np.array(neighbour.GetCenter())
                cross = normal[0] * sourceNormal[1] - normal[1] * sourceNormal[0]
                assert abs(cross) / np.linalg.norm(sourceNormal) <= 100
        assert set(neighbours) == {STROKE_T.S_ARC, STROKE_T.S_SEGMENT}


@pytest.mark.parametrize("angle", np.arange(0, 360, 30))
@pytest.mark.parametrize("phase,frequency,amplitude", [(0, 5, 2), (0.23, 7, 1.25)])
def test_sineModulatedBoardFillets(angle, phase, frequency, amplitude):
    from collections import Counter
    theta = np.linspace(0, 2 * np.pi, 4097)[:-1]
    radius = fromMm(10) + fromMm(amplitude) * np.sin(frequency * theta + phase)
    board = Substrate([])
    board.union(Polygon(np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))))
    direction = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
    origin = direction * fromMm(17)
    core, face = board.tab(origin, -direction, fromMm(1.5))
    original = board.substrates
    tab, _ = board.tab(origin, -direction, fromMm(1.5), fillet=fromMm(1))
    assert len(board.circles) == 2
    allowed = core.buffer(2).union(face.buffer(fromMm(4)))
    assert tab.difference(allowed).is_empty
    board.union(tab)
    assert board.substrates.is_valid
    assert board.substrates.difference(allowed).symmetric_difference(original.difference(allowed)).area <= 10
    shapes = board.serialize(reconstructArcs=True)
    assert len(extractRings(shapes)) == 1
    endpoints = Counter(tuple(p) for s in shapes for p in [s.GetStart(), s.GetEnd()])
    assert set(endpoints.values()) == {2}
    exported = Substrate(shapes).substrates
    assert shapely.hausdorff_distance(
        original.boundary.difference(allowed), exported.boundary.difference(allowed), densify=0.25
    ) <= fromMm(0.001)
    for _, _, start, end, _ in board.circles:
        endpoints = {tuple(np.rint(start)), tuple(np.rint(end))}
        matches = [s for s in shapes if s.GetShape() == STROKE_T.S_ARC and
                   {tuple(s.GetStart()), tuple(s.GetEnd())} == endpoints]
        assert len(matches) == 1
        assert abs(matches[0].GetRadius() - fromMm(1)) <= 100


def test_bezierApproximationAndFillet():
    curve = pcbnew.PCB_SHAPE()
    curve.SetShape(STROKE_T.S_CURVE)
    curve.SetStart(pcbnew.VECTOR2I(0, -fromMm(10)))
    curve.SetEnd(pcbnew.VECTOR2I(0, fromMm(10)))
    c1 = pcbnew.VECTOR2I(-fromMm(4), -fromMm(4))
    c2 = pcbnew.VECTOR2I(fromMm(4), fromMm(4))
    if hasattr(curve, "SetBezierC1"):
        curve.SetBezierC1(c1)
        curve.SetBezierC2(c2)
    else:
        curve.SetBezControl1(c1)
        curve.SetBezControl2(c2)
    points = approximateBezier(curve, curve.GetEnd())
    t = np.linspace(0, 1, 8193)[:, None]
    expected = ((1-t)**3 * np.array(curve.GetStart()) + 3*t*(1-t)**2 * np.array(c1)
                + 3*t**2*(1-t) * np.array(c2) + t**3 * np.array(curve.GetEnd()))
    errors = shapely.distance(shapely.points(expected), LineString(points))
    assert max(errors) <= ARC_CHORD_ERROR
    board = Substrate([])
    board.union(Polygon([*points, (-fromMm(10), fromMm(10)), (-fromMm(10), -fromMm(10))]))
    tab, _ = board.tab((fromMm(8), fromMm(2)), (-1, 0), fromMm(1.5), fillet=fromMm(1))
    board.union(tab)
    assert board.substrates.is_valid
    assert len(board.circles) == 2
    assert len(extractRings(board.serialize(True))) == 1


@pytest.mark.parametrize("start,end,tolerance,expected", [
    ((10, 0), (0, 10), 1, False),  # Endpoints fit; chord interior does not.
    ((8, -6), (8, 6), 2, True),   # Projection exactly on the inner tolerance.
    ((8, -6), (8, 6), np.nextafter(2., 0.), False),
    ((9, 0), (10, 0), 1, True),   # Projection is outside the segment.
    ((10, 0), (9, 0), 1, True),
    ((11, 0), (11, 0), 1, True),  # Zero length, exactly on outer tolerance.
    ((np.nextafter(11., np.inf), 0), (11, 0), 1, False),
    ((9, 0), (9, 0), 1, True),
    ((np.nextafter(9., 0.), 0), (9, 0), 1, False),
    ((12, 0), (12, 0), 1, False),
])
def test_linesFitCircleTolerance(start, end, tolerance, expected):
    fit = CircleFitCandidates(tolerance=tolerance)
    with np.errstate(all="raise"):
        for a, b in [(start, end), (end, start)]:
            assert fit._doLinesFitCircle(
                [(np.array(a), np.array(b))], np.zeros(2), 10) == expected


def test_linesFitCircleTranslatedAndDisconnected():
    # KiCad coordinates can be large integers; segments need not be connected.
    center = np.array([2_000_000_000, -2_000_000_000], dtype=np.int32)
    lines = [(center + np.array(a, dtype=np.int32),
              center + np.array(b, dtype=np.int32)) for a, b in [
                  ((9, 0), (10, 0)), ((0, -10), (0, -9))]]
    fit = CircleFitCandidates(tolerance=1)
    assert fit._doLinesFitCircle(iter(lines), center, 10)
    assert fit._doLinesFitCircle([], center, 10)
    lines.append((center + (10, 0), center + (-10, 0)))
    assert not fit._doLinesFitCircle(iter(lines), center, 10)


@pytest.mark.parametrize("span", [0.01, 0.1, 1, 4])
@pytest.mark.parametrize("radius", [0.25, 10, 1000])
@pytest.mark.parametrize("offset", [0, 1000])
def test_fitCircleShortArcsAtLargeCoordinates(span, radius, offset):
    center = np.array([fromMm(offset), -fromMm(offset)], dtype=float)
    angles = np.linspace(0.23, 0.23 + span, 33)
    points = center + fromMm(radius) * np.column_stack((np.cos(angles), np.sin(angles)))
    fit = CircleFitCandidates()
    fit._xs, fit._ys = list(points[:, 0]), list(points[:, 1])
    fit._xSum, fit._ySum = sum(fit._xs), sum(fit._ys)
    actualCenter, actualRadius = fit._fitCircle()
    assert np.max(np.abs(actualCenter - center)) < 0.1  # Nanometres.
    assert abs(actualRadius - fromMm(radius)) < 0.1


def test_circleFitRejectThenContinue():
    fit = CircleFitCandidates()
    angles = np.linspace(0, 0.1, 25)
    for angle in angles:
        assert fit.addPoint(fromMm(10) * np.array([np.cos(angle), np.sin(angle)]))
    end = fit.end.copy()
    circle = fit.foundCircle
    assert not fit.addPoint((fromMm(11), 0))
    assert len(fit) == len(angles)
    assert np.array_equal(fit.end, end)
    assert fit.foundCircle is circle
    assert fit.addPoint(fromMm(10) * np.array([np.cos(0.105), np.sin(0.105)]))


@pytest.mark.parametrize("points", [
    [(i, 0) for i in range(5)],
    [(i, 2 * i + 1) for i in range(5)],
    [(5, 5)] * 5,
])
def test_circleFitRejectsDegeneratePoints(points):
    fit = CircleFitCandidates()
    with np.errstate(all="raise"):
        for point in points[:4]:
            assert fit.addPoint(point)
        assert not fit.addPoint(points[-1])
    assert len(fit) == 4
    assert fit.foundCircle is None


def test_circleFitSymmetricCircleWithZeroRootDerivative():
    radius = fromMm(1)
    fit = CircleFitCandidates(tolerance=radius)
    with np.errstate(all="raise"):
        for point in [(radius, 0), (0, radius), (-radius, 0), (0, -radius)] * 2:
            assert fit.addPoint(point)
    center, actualRadius = fit.foundCircle
    assert np.array_equal(center, [0, 0])
    assert actualRadius == radius
