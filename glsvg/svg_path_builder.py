import math
import re
import string

import OpenGL.GL as gl
import OpenGL.GLU as glu
from svg_constants import *
from svg_parser_utils import *
from vector_math import Matrix
import svg_style
import svg_constants

POINT_RE = re.compile("(-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)")
PATH_CMD_RE = re.compile("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)")


class SVGPathBuilder(object):

    def __init__(self, fill_rule='nonzero'):
        self._bezier_coefficients = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.close_index = 0
        self.ctx_path = []
        self.ctx_loop = []
        self.shape = None
        self.fill_rule = fill_rule
        self.n_bezier_points = svg_constants.BEZIER_POINTS
        self.n_circle_points = svg_constants.CIRCLE_POINTS
        self.tolerance = svg_constants.TOLERANCE
        self.fill_rule = fill_rule

    def read_xml_svg_element(self, path, element, config):
        self._bezier_coefficients = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.close_index = 0
        self.ctx_path = []
        self.ctx_loop = []
        self.shape = None
        self.n_bezier_points = config.bezier_points
        self.n_circle_points = config.circle_points
        self.tolerance = config.tolerance
        self.fill_rule = None
        if path.style.fill:
            self.fill_rule = path.style.fill_rule

        e = element
        if e.tag.endswith('path'):
            self.shape = path.shape = 'path'
            self._read_path_commands(e)
        elif e.tag.endswith('rect'):
            self.shape = path.shape = 'rect'
            x = parse_float(e.get('x', '0'))
            y = parse_float(e.get('y', '0'))
            h = parse_float(e.get('height'))
            w = parse_float(e.get('width'))

            rx = parse_float(e.get('rx', '0'))
            ry = parse_float(e.get('ry', str(rx)))
            path.x, path.y, path.w, path.h = x, y, w, h

            if rx == 0 and ry == 0:
                # no rounding, so just draw a simple rectangle
                self.set_cursor_position(x, y)
                self.line_to(x + w, y)
                self.line_to(x + w, y + h)
                self.line_to(x, y + h)
                self.line_to(x, y)
                self.end_path()
            else:
                # rounded rectangle, do some stuff with arcs
                self.set_cursor_position(x, y + ry)
                self.arc_to(rx, ry, 0, 0, 1, x + rx, y)
                self.line_to(x + (w - rx), y)
                self.arc_to(rx, ry, 0, 0, 1, x + w, y + ry)
                self.line_to(x + w, y + (h - ry))
                self.arc_to(rx, ry, 0, 0, 1, x + (w - rx), y+h)
                self.line_to(x + rx, y + h)
                self.arc_to(rx, ry, 0, 0, 1, x, y + (h - ry))
                self.line_to(x, y + ry)
                self.end_path()

        elif e.tag.endswith('polyline') or e.tag.endswith('polygon'):
            if e.tag.endswith('polyline'):
                self.shape = path.shape = 'polyline'
            else:
                self.shape = path.shape = 'polygon'
            path_data = e.get('points')
            path_data = POINT_RE.findall(path_data)

            def next_point():
                return float(path_data.pop(0)), float(path_data.pop(0))
            while path_data:
                self.line_to(*next_point())
            if e.tag.endswith('polygon'):
                self.close_path()
            self.end_path()
        elif e.tag.endswith('line'):
            self.shape = path.shape = 'line'
            x1 = float(e.get('x1'))
            y1 = float(e.get('y1'))
            x2 = float(e.get('x2'))
            y2 = float(e.get('y2'))
            path.x1, path.x1, path.x2, path.y2 = x1, y1, x2, y2
            self.set_cursor_position(x1, y1)
            self.line_to(x2, y2)
            self.end_path()
        elif e.tag.endswith('circle'):
            self.shape = path.shape = 'circle'
            cx = float(e.get('cx', 0))
            cy = float(e.get('cy', 0))
            r = float(e.get('r'))
            path.cx, path.cy, path.r = cx, cy, r
            for i in xrange(config.circle_points):
                theta = 2 * i * math.pi / config.circle_points
                self.line_to(cx + r * math.cos(theta), cy + r * math.sin(theta))
            self.close_path()
            self.end_path()
        elif e.tag.endswith('ellipse'):
            self.shape = path.shape = 'ellipse'
            cx = float(e.get('cx', 0))
            cy = float(e.get('cy', 0))
            rx = float(e.get('rx'))
            ry = float(e.get('ry'))
            path.cx, path.cy, path.rx, path.ry = cx, cy, rx, ry
            for i in xrange(config.circle_points):
                theta = 2 * i * math.pi / config.circle_points
                self.line_to(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            self.close_path()
            self.end_path()

    def close_path(self):
        self.ctx_loop.append(self.ctx_loop[0][:])
        self.ctx_path.append(self.ctx_loop)
        self.ctx_loop = []

    def set_cursor_position(self, x, y):
        self.cursor_x = x
        self.cursor_y = y
        self.ctx_loop.append([x, y])

    def _read_path_commands(self, e):
        path_data = e.get('d', '')
        path_data = PATH_CMD_RE.findall(path_data)

        def next_point():
            return float(path_data.pop(0)), float(path_data.pop(0))

        opcode = ''
        while path_data:
            prev_opcode = opcode
            if path_data[0] in string.letters:
                opcode = path_data.pop(0)
            else:
                opcode = prev_opcode

            if opcode == 'M':
                self.set_cursor_position(*next_point())
            elif opcode == 'm':
                mx, my = next_point()
                self.set_cursor_position(self.cursor_x + mx, self.cursor_y + my)
            elif opcode == 'Q':  # absolute quadratic curve
                self.quadratic_curve_to(*(next_point() + next_point()))
            elif opcode == 'q':  # relative quadratic curve
                ax, ay = next_point()
                bx, by = next_point()
                self.quadratic_curve_to(
                    ax + self.cursor_x, ay + self.cursor_y,
                    bx + self.cursor_x, by + self.cursor_y)

            elif opcode == 'T':
                # quadratic curve with control point as reflection
                mx = 2 * self.cursor_x - self.last_cx
                my = 2 * self.cursor_y - self.last_cy
                x, y = next_point()
                self.quadratic_curve_to(mx, my, x, y)

            elif opcode == 't':
                # relative quadratic curve with control point as reflection
                mx = 2 * self.cursor_x - self.last_cx
                my = 2 * self.cursor_y - self.last_cy
                x, y = next_point()
                self.quadratic_curve_to(
                    mx + self.cursor_x,
                    my + self.cursor_y,
                    x + self.cursor_x,
                    y + self.cursor_y)

            elif opcode == 'C':
                self.curve_to(*(next_point() + next_point() + next_point()))
            elif opcode == 'c':
                mx, my = self.cursor_x, self.cursor_y
                x1, y1 = next_point()
                x2, y2 = next_point()
                x, y = next_point()

                self.curve_to(mx + x1, my + y1, mx + x2, my + y2, mx + x, my + y)
            elif opcode == 'S':
                self.curve_to(2 * self.cursor_x - self.last_cx, 2 * self.cursor_y - self.last_cy,
                               *(next_point() + next_point()))
            elif opcode == 's':
                mx = self.cursor_x
                my = self.cursor_y
                x1, y1 = 2 * self.cursor_x - self.last_cx, 2 * self.cursor_y - self.last_cy
                x2, y2 = next_point()
                x, y = next_point()

                self.curve_to(x1, y1, mx + x2, my + y2, mx + x, my + y)
            elif opcode == 'A':
                rx, ry = next_point()
                phi = float(path_data.pop(0))
                large_arc = int(path_data.pop(0))
                sweep = int(path_data.pop(0))
                x, y = next_point()
                self.arc_to(rx, ry, phi, large_arc, sweep, x, y)
            elif opcode == 'a':  # relative arc
                rx, ry = next_point()
                phi = float(path_data.pop(0))
                large_arc = int(path_data.pop(0))
                sweep = int(path_data.pop(0))
                x, y = next_point()
                self.arc_to(rx, ry, phi, large_arc, sweep, self.cursor_x + x, self.cursor_y + y)
            elif opcode in 'zZ':
                self.close_path()
            elif opcode == 'L':
                self.line_to(*next_point())
            elif opcode == 'l':
                x, y = next_point()
                self.line_to(self.cursor_x + x, self.cursor_y + y)
            elif opcode == 'H':
                x = float(path_data.pop(0))
                self.line_to(x, self.cursor_y)
            elif opcode == 'h':
                x = float(path_data.pop(0))
                self.line_to(self.cursor_x + x, self.cursor_y)
            elif opcode == 'V':
                y = float(path_data.pop(0))
                self.line_to(self.cursor_x, y)
            elif opcode == 'v':
                y = float(path_data.pop(0))
                self.line_to(self.cursor_x, self.cursor_y + y)
            else:
                self._warn("Unrecognised opcode: " + opcode)
                raise Exception("Unrecognised opcode: " + opcode)
        self.end_path()

    def arc_to(self, rx, ry, phi, large_arc, sweep, x, y):
        # This function is made out of magical fairy dust
        # http://www.w3.org/TR/2003/REC-SVG11-20030114/implnote.html#ArcImplementationNotes
        x1 = self.cursor_x
        y1 = self.cursor_y
        x2 = x
        y2 = y
        cp = math.cos(phi)
        sp = math.sin(phi)
        dx = .5 * (x1 - x2)
        dy = .5 * (y1 - y2)
        x_ = cp * dx + sp * dy
        y_ = -sp * dx + cp * dy
        r2 = (((rx * ry) ** 2 - (rx * y_) ** 2 - (ry * x_) ** 2) /
              ((rx * y_) ** 2 + (ry * x_) ** 2))
        if r2 < 0: r2 = 0
        r = math.sqrt(r2)
        if large_arc == sweep:
            r = -r
        cx_ = r * rx * y_ / ry
        cy_ = -r * ry * x_ / rx
        cx = cp * cx_ - sp * cy_ + .5 * (x1 + x2)
        cy = sp * cx_ + cp * cy_ + .5 * (y1 + y2)

        def angle(u, v):
            a = math.acos((u[0] * v[0] + u[1] * v[1]) / math.sqrt((u[0] ** 2 + u[1] ** 2) * (v[0] ** 2 + v[1] ** 2)))
            sgn = 1 if u[0] * v[1] > u[1] * v[0] else -1
            return sgn * a

        psi = angle((1, 0), ((x_ - cx_) / rx, (y_ - cy_) / ry))
        delta = angle(((x_ - cx_) / rx, (y_ - cy_) / ry),
                      ((-x_ - cx_) / rx, (-y_ - cy_) / ry))
        if sweep and delta < 0:
            delta += math.pi * 2
        if not sweep and delta > 0:
            delta -= math.pi * 2
        n_points = max(int(abs(self.n_circle_points * delta / (2 * math.pi))), 1)

        for i in xrange(n_points + 1):
            theta = psi + i * delta / n_points
            ct = math.cos(theta)
            st = math.sin(theta)
            self.line_to(cp * rx * ct - sp * ry * st + cx,
                         sp * rx * ct + cp * ry * st + cy)

    def quadratic_curve_to(self, x1, y1, x2, y2):
        x0, y0 = self.cursor_x, self.cursor_y
        n_bezier_points = self.n_bezier_points
        for i in xrange(n_bezier_points + 1):
            t = float(i) / n_bezier_points
            q0x = (x1 - x0) * t + x0
            q0y = (y1 - y0) * t + y0

            q1x = (x2 - x1) * t + x1
            q1y = (y2 - y1) * t + y1

            bx = (q1x - q0x) * t + q0x
            by = (q1y - q0y) * t + q0y

            self.ctx_loop.append([bx, by])

        self.last_cx, self.last_cy = x1, y1
        self.cursor_x, self.cursor_y = x2, y2

    def curve_to(self, x1, y1, x2, y2, x, y):
        n_bezier_points = self.n_bezier_points
        if not self._bezier_coefficients:
            for i in xrange(n_bezier_points + 1):
                t = float(i) / n_bezier_points
                t0 = (1 - t) ** 3
                t1 = 3 * t * (1 - t) ** 2
                t2 = 3 * t ** 2 * (1 - t)
                t3 = t ** 3
                self._bezier_coefficients.append([t0, t1, t2, t3])
        self.last_cx = x2
        self.last_cy = y2
        for i, t in enumerate(self._bezier_coefficients):
            px = t[0] * self.cursor_x + t[1] * x1 + t[2] * x2 + t[3] * x
            py = t[0] * self.cursor_y + t[1] * y1 + t[2] * y2 + t[3] * y
            self.ctx_loop.append([px, py])

        self.cursor_x, self.cursor_y = px, py

    def line_to(self, x, y):
        self.set_cursor_position(x, y)

    def end_path(self):
        self.ctx_path.append(self.ctx_loop)
        if self.ctx_path:
            path = []
            for orig_loop in self.ctx_path:
                if not orig_loop:
                    continue
                loop = [orig_loop[0]]
                for pt in orig_loop:
                    if (pt[0] - loop[-1][0]) ** 2 + (pt[1] - loop[-1][1])**2 > self.tolerance:
                        loop.append(pt)
                path.append(loop)

            self.path = path
            self.polygon = self._triangulate(path, self.fill_rule) if self.fill_rule else None
        self.ctx_path = []

        return self.path, self.polygon

    def _triangulate(self, looplist, fill_rule):
        if self.shape in ['line']:
            return None
        t_list = []
        self.ctx_curr_shape = []
        spare_verts = []
        tess = glu.gluNewTess()
        glu.gluTessNormal(tess, 0, 0, 1)
        glu.gluTessProperty(tess, glu.GLU_TESS_WINDING_RULE, glu.GLU_TESS_WINDING_NONZERO)

        def set_tess_callback(which):
            def set_call(func):
                glu.gluTessCallback(tess, which, func)
            return set_call

        @set_tess_callback(glu.GLU_TESS_VERTEX)
        def vertex_callback(vertex):
            self.ctx_curr_shape.append(list(vertex[0:2]))

        @set_tess_callback(glu.GLU_TESS_BEGIN)
        def begin_callback(which):
            self.ctx_tess_style = which

        @set_tess_callback(glu.GLU_TESS_END)
        def end_callback():
            if self.ctx_tess_style == gl.GL_TRIANGLE_FAN:
                c = self.ctx_curr_shape.pop(0)
                p1 = self.ctx_curr_shape.pop(0)
                while self.ctx_curr_shape:
                    p2 = self.ctx_curr_shape.pop(0)
                    t_list.extend([c, p1, p2])
                    p1 = p2
            elif self.ctx_tess_style == gl.GL_TRIANGLE_STRIP:
                p1 = self.ctx_curr_shape.pop(0)
                p2 = self.ctx_curr_shape.pop(0)
                while self.ctx_curr_shape:
                    p3 = self.ctx_curr_shape.pop(0)
                    t_list.extend([p1, p2, p3])
                    p1 = p2
                    p2 = p3
            elif self.ctx_tess_style == gl.GL_TRIANGLES:
                t_list.extend(self.ctx_curr_shape)
            else:
                self._warn("Unrecognised tesselation style: %d" % (self.ctx_tess_style,))
            self.ctx_tess_style = None
            self.ctx_curr_shape = []

        @set_tess_callback(glu.GLU_TESS_ERROR)
        def error_callback(code):
            ptr = glu.gluErrorString(code)
            err = ''
            idx = 0
            while ptr[idx]:
                err += chr(ptr[idx])
                idx += 1
            self._warn("GLU Tesselation Error: " + err)

        @set_tess_callback(glu.GLU_TESS_COMBINE)
        def combine_callback(coords, vertex_data, weights):
            x, y, z = coords[0:3]
            dataOut = (x,y,z)
            spare_verts.append((x,y,z))
            return dataOut

        data_lists = []
        for vlist in looplist:
            d_list = []
            for x, y in vlist:
                v_data = (x, y, 0)
                d_list.append(v_data)
            data_lists.append(d_list)

        if fill_rule == 'nonzero':
            glu.gluTessProperty(tess, glu.GLU_TESS_WINDING_RULE, glu.GLU_TESS_WINDING_NONZERO)
        elif fill_rule == 'evenodd':
            glu.gluTessProperty(tess, glu.GLU_TESS_WINDING_RULE, glu.GLU_TESS_WINDING_ODD)

        glu.gluTessBeginPolygon(tess, None)
        for d_list in data_lists:
            glu.gluTessBeginContour(tess)
            for v_data in d_list:
                glu.gluTessVertex(tess, v_data, v_data)
            glu.gluTessEndContour(tess)
        glu.gluTessEndPolygon(tess)
        return t_list

    def _warn(self, message):
        print "Warning: SVG Parser - %s" % (message,)



