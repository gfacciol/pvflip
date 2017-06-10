import math
import re
import string

import graphics
import lines
import traceback

import OpenGL.GL as gl

from svg_parser_utils import parse_float, parse_list, get_fns
from svg_path_builder import SVGPathBuilder

from glutils import DisplayListGenerator
import svg_style
from vector_math import Matrix, BoundingBox, vec2
from svg_constants import XMLNS
from render_target import CanvasManager


class SVGContainer(object):

    def __init__(self, parent):

        self.parent = parent

        self.children = []

        self.is_def = False

        if parent:
            parent.add_child(self)

    def add_child(self, child):
        self.children.append(child)


class SVGRenderableElement(SVGContainer):

    def __init__(self, svg, element, parent):

        #: The id of the element
        self.id = element.get('id', '')

        SVGContainer.__init__(self, parent)

        self.svg = svg

        #: Is this element a pattern?
        self.is_pattern = element.tag.endswith('pattern')

        #: Is this element a definition?
        self.is_def = False

        if parent:
            self.is_def = parent.is_def

        #: The element style (possibly with inherited traits from parent style)
        self.style = svg_style.SVGStyle(
            parent.style if isinstance(parent, SVGRenderableElement) else None)
        self.style.from_element(element)

        #: Optional element title
        self.title = element.findtext('{%s}title' % (XMLNS,))

        #: Optional element description. Useful for embedding metadata.
        self.description = element.findtext('{%s}desc' % (XMLNS,))

        #construct a matrix for each transform
        t_acc = Matrix.identity()

        transform_str = element.get('transform', None)
        if transform_str:
            transforms = get_fns(transform_str)

            for tstring in transforms:
                t_acc = t_acc * Matrix(tstring)

        #: Element transforms
        self.transform = t_acc

        #: Children elements
        self.children = []

        #: XML tag this was originally.
        self.tag_type = element.tag

    def add_child(self, child):
        """Add a child to this element class (usually children register with parent)"""
        self.children.append(child)

    @property
    def is_pattern_part(self):
        part = self
        while part:
            if isinstance(part, SVGRenderableElement) and part.is_pattern:
                return True
            part = part.parent
        return False

    @property
    def absolute_transform(self):
        """Return this transform, multiplied by chain of parents"""
        if self.parent:
            return self.parent.absolute_transform * self.transform
        return self.transform

    def on_render(self):
        pass

    def render(self):
        #with CanvasManager.inst().temp():
            with self.transform:
                self.on_render()

                for c in self.children:
                    c.render()


class SVGGroup(SVGRenderableElement):
    pass


class SVGMarker(SVGRenderableElement):

    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)

        self.units = element.get('markerUnits', 'strokeWidth')
        self.marker_width = parse_float(element.get('markerWidth', '3'))
        self.marker_height = parse_float(element.get('markerHeight', '3'))
        self.orient = element.get('orient', 'auto')
        self.ref_x = parse_float(element.get('refX', '0'))
        self.ref_y = parse_float(element.get('refY', '0'))

        vb = element.get('viewBox', None)

        if vb:
            x, y, w, h = (parse_float(x) for x in parse_list(element.get("viewBox")))
            self.vb_x, self.vb_y, self.vb_w, self.vb_h = x, y, w, h
        else:
            self.vb_x = 0
            self.vb_y = 0
            self.vb_w = 1
            self.vb_h = 1


XLINK_NS = "{http://www.w3.org/1999/xlink}"


class SVGUse(SVGRenderableElement):
    """Represents an SVG "use" directive, to reuse a predefined path"""

    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)
        self.svg = svg
        self.target = element.get(XLINK_NS + "href", None)
        self.x = parse_float(element.get('x', '0'))
        self.y = parse_float(element.get('y', '0'))

        self.transform = self.transform * Matrix.translation(self.x, self.y)

        #clip off "#"
        if self.target:
            self.target = self.target[1:]

    def render(self):
        with self.transform:
            defn = self.svg.defs[self.target]
            defn.render()


class SVGDefs(SVGRenderableElement):
    """Represents an SVG "defs" directive, to define paths without drawing them"""

    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)
        self.svg = svg
        self.is_def = True

    def add_child(self, child):
        if hasattr(child, 'id'):
            self.svg.defs[child.id] = child
        self.children.append(child)


def flatten_list(l):
    new_list = []
    for x in l:
        new_list.extend(x)
    return new_list


class SVGPath(SVGRenderableElement):
    """
    Represents a single SVG path. This is usually
    a distinct shape with a fill pattern,
    an outline, or both.
    """

    def __init__(self, svg, element, parent):

        SVGRenderableElement.__init__(self, svg, element, parent)

        #: The original SVG file
        self.svg = svg

        if not self.is_pattern_part:
            self.config = svg.config
        else:
            self.config = svg.config.super_detailed()

        #: The actual path elements, as a list of vertices
        self.outlines = None

        #: The triangles that comprise the inner fill
        self.triangles = None

        #: The base shape. Possible values: path, rect, circle, ellipse, line, polygon, polyline
        self.shape = None

        #: The bounding box
        self._bounding_box = None

        self.marker_start = element.get('marker-start', None)
        self.marker_mid = element.get('marker-mid', None)
        self.marker_end = element.get('marker-end', None)

        if self.marker_start: self.marker_start = self.marker_start[5:-1]
        if self.marker_mid: self.marker_mid = self.marker_mid[5:-1]
        if self.marker_end: self.marker_end = self.marker_end[5:-1]

        path_builder = SVGPathBuilder()

        path_builder.read_xml_svg_element(
                        self,
                        element,
                        self.config)

        self.outlines = path_builder.path

        self.triangles = path_builder.polygon

        self.display_list = None

    def _render_stroke(self):
        stroke = self.style.stroke
        stroke_width = self.style.stroke_width

        is_miter = self.style.stroke_linejoin == 'miter'

        miter_limit = self.style.stroke_miterlimit if is_miter else 0

        for loop in self.outlines:
            self.svg.n_lines += len(loop) - 1
            loop_plus = []

            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]

            if isinstance(stroke, str):
                g = self.svg._gradients[stroke]
                strokes = [g.sample(x, self) for x in loop_plus]
            else:
                strokes = [stroke for x in loop_plus]

            if len(loop_plus) == 0:
                continue

            if len(self.style.stroke_dasharray):
                ls = lines.split_line_by_pattern(loop_plus, self.style.stroke_dasharray)

                if ls[0][0] == ls[-1][-1]:
                    #if the last line end point equals the first line start point,
                    #this is a "closed" line, so combine the first and the last line
                    combined_line = ls[-1] + ls[0]
                    ls[0] = combined_line
                    del ls[-1]

                for l in ls:
                    lines.draw_polyline(
                        l,
                        stroke_width,
                        color=strokes[0],
                        line_cap=self.style.stroke_linecap,
                        join_type=self.style.stroke_linejoin,
                        miter_limit=miter_limit)

                if self.marker_start:
                    end_point = vec2(loop_plus[0])
                    almost_end_point = vec2(loop_plus[1])
                    marker = self.svg.defs[self.marker_start]
                    self._render_marker(end_point, almost_end_point, marker, True)
                if self.marker_end:
                    end_point = vec2(loop_plus[-1])
                    almost_end_point = vec2(loop_plus[-2])
                    marker = self.svg.defs[self.marker_end]
                    self._render_marker(end_point, almost_end_point, marker)

            else:
                lines.draw_polyline(
                    loop_plus,
                    stroke_width,
                    color=strokes[0],
                    line_cap=self.style.stroke_linecap,
                    join_type=self.style.stroke_linejoin,
                    miter_limit=miter_limit)

                if self.marker_start:
                    end_point = vec2(loop_plus[0])
                    almost_end_point = vec2(loop_plus[1])
                    marker = self.svg.defs[self.marker_start]
                    self._render_marker(end_point, almost_end_point, marker, True)
                if self.marker_end:
                    end_point = vec2(loop_plus[-1])
                    almost_end_point = vec2(loop_plus[-2])
                    marker = self.svg.defs[self.marker_end]
                    self._render_marker(end_point, almost_end_point, marker)

    def _render_marker(self, a, b, marker, reverse=False):
        if marker.orient == 'auto':
            angle = (a - b).angle()
        else:
            angle = marker.orient

        if reverse:
            angle += math.pi

        sx = (marker.marker_width / marker.vb_w) * self.style.stroke_width
        sy = (marker.marker_height / marker.vb_h) * self.style.stroke_width

        rx = marker.ref_x
        ry = marker.ref_y

        with Matrix.transform(a.x, a.y, theta=angle):
            with Matrix.scale(sx, sy):
                with Matrix.translation(-rx, -ry):
                    marker.render()

    def _render_gradient_fill(self):
        fill = self.style.fill
        tris = self.triangles
        self.svg.n_tris += len(tris) / 3
        g = None
        if isinstance(fill, str):
            g = self.svg._gradients[fill]
            fills = [g.sample(x, self) for x in tris]
        else:
            fills = [fill] * len(tris)  # for x in tris]

        if g:
            g.apply_shader(self, self.transform, self.style.opacity * self.style.fill_opacity)

        graphics.draw_colored_triangles(
            flatten_list(tris),
            flatten_list(fills)
        )

        if g:
            g.unapply_shader()

    def bounding_box(self):
        '''
        returns a tuple describing the bounding box:

        (min_x, min_y, max_x, max_y)
        '''
        if not self._bounding_box:
            self._bounding_box = BoundingBox()

            if self.triangles:
                self._bounding_box.expand(self.triangles)
            if self.outlines:
                for o in self.outlines:
                    self._bounding_box.expand(o)
        return self._bounding_box.extents()

    def _render_pattern_fill(self):
        fill = self.style.fill
        tris = self.triangles
        pattern = None
        if fill in self.svg.patterns:
            pattern = self.svg.patterns[fill]
            pattern.bind_texture()

        min_x, min_y, max_x, max_y = self.bounding_box()

        tex_coords = []

        for vtx in tris:
            tex_coords.append((vtx[0]-min_x)/(max_x-min_x)/pattern.width)
            tex_coords.append((vtx[1]-min_y)/(max_y-min_y)/pattern.width)

        graphics.draw_textured_triangles(
            flatten_list(tris),
            tex_coords
        )

        if pattern:
            pattern.unbind_texture()

    def on_render(self):
        """Render immediately to screen (no display list). Slow! Consider
        using SVG.draw(...) instead."""

        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)

        gl.glEnable(gl.GL_DEPTH_TEST)

        if self.style.stroke and self.outlines:
            self._render_stroke()

        gl.glPushMatrix()
        gl.glTranslatef(0, 0, -0.1)
        if self.triangles:
            try:
                if isinstance(self.style.fill, str) and self.style.fill in self.svg.patterns:
                    self._render_pattern_fill()
                else:
                    self._render_gradient_fill()
            except Exception as exception:
                traceback.print_exc(exception)
        gl.glPopMatrix()
        gl.glDisable(gl.GL_DEPTH_TEST)



    def __repr__(self):
        return "<SVGPath id=%s title='%s' description='%s' transform=%s>" % (
            self.id, self.title, self.description, self.transform
        )


class SVGViewBox:

    def __init__(self, x, y, w, h):
        pass

    def matrix(self):
        pass