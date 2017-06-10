import math
import graphics
from vector_math import vec2, line_length, radian, intersection


class LineSegment(object):
    def __init__(self, startp, endp, w=0):
        self.start = startp
        self.end = endp
        self.w = w
        self.upper_v = []
        self.lower_v = []
        if w > 0:
            self.calculate_tangents()
        self.upper_join = None
        self.lower_join = None
        self.connector = []

    @property
    def angle(self):
        d = self.direction
        return math.atan2(d.y, d.x)

    @property
    def direction(self):
        return (self.end-self.start).normalized()

    @property
    def upper_edge(self):
        return LineSegment(self.start + self.up_normal,
                           self.end + self.up_normal)

    @property
    def lower_edge(self):
        return LineSegment(self.start + self.dn_normal,
                           self.end + self.dn_normal)

    def calculate_tangents(self):
        v = (self.end - self.start).normalized()
        angle = math.atan2(v.y, v.x)
        half_width = self.w * 0.5
        self.up_normal = vec2(math.cos(angle - radian(90)) * half_width,
                              math.sin(angle - radian(90)) * half_width)
        self.dn_normal = vec2(math.cos(angle + radian(90)) * half_width,
                              math.sin(angle + radian(90)) * half_width)


def _process_joint(ln, pln, miter_limit, rounded=False):
    up_intersection, ln.upper_join = ln_intersection(pln.upper_edge, ln.upper_edge)
    lo_intersection, ln.lower_join = ln_intersection(pln.lower_edge, ln.lower_edge)

    if up_intersection and lo_intersection:
        pln.upper_v.append(pln.upper_join)
        pln.lower_v.append(pln.lower_join)
        return

    if ln.upper_join == None:
        ln.upper_join = ln.upper_edge.start

    if ln.lower_join == None:
        ln.lower_join = ln.lower_edge.start

    ml1 = line_length(ln.lower_edge.start, ln.upper_join)

    if rounded:
        pass


    if rounded and not up_intersection:
        ln.upper_join = ln.upper_edge.start
        pln.upper_v.append(pln.upper_join)
        pln.upper_v.append(pln.upper_edge.end)

        #arc to next lines upper-join
        base = pln.end
        start = pln.upper_edge.end
        target = ln.upper_join

        dist = (start-base).length()
        av = (start - base).normalized()
        bv = (target - base).normalized()

        start_angle = av.angle()
        target_angle = bv.angle()
        if start_angle > target_angle:
            start_angle -= 2.0 * math.pi

        theta = start_angle
        pln.lower_v.append(pln.lower_join)
        while theta < target_angle:
            v = base + (vec2(math.cos(theta), math.sin(theta)) * dist)
            pln.upper_v.append(v)
            pln.lower_v.append(ln.lower_join)
            theta += 0.2

        pln.upper_v.append(ln.upper_join)
        return
    elif ml1 > miter_limit and not up_intersection:
        #bevel
        ln.upper_join = ln.upper_edge.start
        pln.upper_v.append(pln.upper_join)
        pln.upper_v.append(pln.upper_edge.end)
        pln.upper_v.append(ln.upper_join)
    elif not rounded:
        pln.upper_v.append(pln.upper_join)
        pln.upper_v.append(ln.upper_join)

    ml2 = line_length(ln.upper_edge.start, ln.lower_join)

    if rounded and not lo_intersection:
        ln.lower_join = ln.lower_edge.start
        pln.upper_v.append(pln.upper_join)
        pln.lower_v.append(pln.lower_join)

        #arc to next lines upper-join
        base = pln.end
        start = pln.lower_edge.end
        target = ln.lower_join

        dist = (start-base).length()
        av = (start - base).normalized()
        bv = (target - base).normalized()

        start_angle = av.angle()
        target_angle = bv.angle()
        if start_angle < target_angle:
            start_angle += 2.0 * math.pi

        theta = start_angle
        pln.upper_v.append(ln.upper_join)

        while theta > target_angle:
            v = base + (vec2(math.cos(theta), math.sin(theta)) * dist)

            pln.lower_v.append(v)
            pln.upper_v.append(ln.upper_join)
            theta -= 0.2
        pln.lower_v.append(ln.lower_join)

    elif ml2 > miter_limit and not lo_intersection:
        #bevel
        ln.lower_join = ln.lower_edge.start
        pln.lower_v.append(pln.lower_join)
        pln.lower_v.append(pln.lower_edge.end)
        pln.lower_v.append(ln.lower_join)
    else:
        pln.lower_v.append(pln.lower_join)
        pln.lower_v.append(ln.lower_join)


class DashGenerator:

    def __init__(self, pattern):
        self.pattern = [float(x) for x in pattern]
        self.index = 0

        if len(pattern) % 2 == 1:
            self.pattern *= 2

    def next(self, limit):
        start_index = int(self.index)
        pct = self.index - int(self.index)
        n = self.pattern[int(self.index)] * (1-pct)
        if n > limit:
            n = limit
        consumed = n/self.pattern[int(self.index)]
        self.index = (self.index + consumed) % len(self.pattern)

        should_flip = int(self.index) != start_index
        return n, should_flip


def split_line_by_pattern(points, pattern):

    dg = DashGenerator(pattern)
    lines = []
    is_whitespace = False
    current_line = []

    for p in xrange(1, len(points)):
        start = vec2(points[p-1])
        end = vec2(points[p])
        normal = (end - start).normalized()
        amount_to_move = (end - start).length()

        current = start
        while amount_to_move > 0:
            l, should_flip = dg.next(amount_to_move)
            a = current
            b = current + normal * l
            current = b
            if not is_whitespace:
                if len(current_line):
                    current_line.append(b)
                else:
                    current_line.append(a)
                    current_line.append(b)
            if should_flip:
                if not is_whitespace:
                    lines.append(current_line)
                    current_line = []
                is_whitespace = not is_whitespace

            amount_to_move -= l
    if len(current_line):
        lines.append(current_line)
    return lines


def calc_polyline(points, w, line_cap='butt', join_type='miter', miter_limit=4, closed=False):

    miter_length = w * miter_limit
    points = [vec2(p) for p in points]
    if closed and points[0] != points[-1]:
        points.append(vec2(points[0]))

    lines = []
    for i in range(len(points) - 1):
        lines.append(
            LineSegment(points[i], points[i+1], w))

    lines[0].upper_join = lines[0].upper_edge.start
    lines[0].lower_join = lines[0].lower_edge.start

    if line_cap == 'square' and not closed:
        ext = lines[0].direction * w * -0.5
        lines[0].upper_join = lines[0].upper_join + ext
        lines[0].lower_join = lines[0].lower_join + ext

    for i in range(1, len(lines)):
        ln, pln = lines[i], lines[i-1]
        _process_joint(ln, pln, miter_length, join_type=='round')

    ll = lines[-1]
    lf = lines[0]
    if closed:
        b_up_int, upper_join = ln_intersection(ll.upper_edge, lf.upper_edge)
        b_lo_int, lower_join = ln_intersection(ll.lower_edge, lf.lower_edge)

        if upper_join == None: upper_join = ll.upper_edge.end
        if lower_join == None: lower_join = ll.lower_edge.end

        if line_length(ll.lower_edge.end, upper_join) > miter_length and b_up_int:
            #bevel
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(ll.upper_edge.end)
            ll.upper_v.append(lf.upper_edge.start)
        else:
            lf.upper_v[0] = upper_join
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(upper_join)

        if line_length(ll.upper_edge.end, lower_join) > miter_length and b_lo_int:
            #bevel
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(ll.lower_edge.end)
            ll.lower_v.append(lf.lower_edge.start)
        else:
            lf.lower_v[0] = lower_join
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(lower_join)

    else:
        if line_cap == 'butt' or line_cap == 'round':
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(ll.upper_edge.end)
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(ll.lower_edge.end)
        elif line_cap == 'square':
            ext = ll.direction * w*0.5
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(ll.upper_edge.end + ext)
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(ll.lower_edge.end + ext)

    return lines


def draw_polyline(points, w, color, line_cap='butt', join_type='miter', miter_limit=4, closed=False, debug=False):
    if len(points) == 0:
        return

    #remove any duplicate points
    unique_points = []
    last_point = None
    for p in points:
        if p != last_point:
            unique_points.append(p)
        last_point = p
    points = unique_points

    if len(points) == 1:
        return

    if points[0] == points[-1]:
        closed = True

    lines = calc_polyline(points, w, line_cap, join_type, miter_limit, closed)
    swap = False
    vertices = []

    for line in lines:
        first = line.upper_v if not swap else line.lower_v
        second = line.lower_v if not swap else line.upper_v

        i = 0
        for i in xrange(max(len(first), len(second))):
            if i<len(first):
                vertices.extend(first[i].tolist())
            if i<len(second):
                vertices.extend(second[i].tolist())

            if len(first) != len(second):
                swap = not swap

    graphics.draw_triangle_strip(vertices, color)

    if line_cap == 'round' and not closed:
        graphics.draw_round_cap(lines[0].start, w*0.5, lines[0].angle - math.pi)
        graphics.draw_round_cap(lines[-1].end, w*0.5, lines[-1].angle)



def ln_intersection(l1, l2):
    return intersection(l1.start, l1.end, l2.start, l2.end)




