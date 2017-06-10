import OpenGL.GL as gl

from glutils import ViewportAs

import render_target

from svg_parser_utils import *
from svg_constants import *
from svg_path import SVGRenderableElement


class SVGPattern(SVGRenderableElement):
    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)

        self.svg = svg
        self.units = element.get('patternContentUnits', 'objectBoundingBox')
        self.x = parse_float(element.get('x', '0.0'))
        self.y = parse_float(element.get('y', '0.0'))
        self.width = parse_float(element.get('width', '1.0'))
        self.height = parse_float(element.get('height', '1.0'))
        self.render_texture = None
        self.render_texture = render_target.RenderTarget(PATTERN_TEX_SIZE, PATTERN_TEX_SIZE)

    def bind_texture(self):
        if not self.render_texture:
            return
        self.render_texture.texture.bind()

    def unbind_texture(self):
        if not self.render_texture:
            return
        self.render_texture.texture.unbind()

    def extents(self):
        min_x, min_y, max_x, max_y = 0, 0, 1, 1

        for p in self.children:
            x0, y0, x1, y1 = p.bounding_box()
            if x0 < min_x: min_x = x0
            if y0 < min_y: min_y = y0
            if x1 > max_x: max_x = x1
            if y1 > max_y: max_y = y1

        return min_x, min_y, max_x, max_y

    def render(self):
        #setup projection matrix..
        min_x, min_y, max_x, max_y = self.extents()

        print "extents"
        print self.extents()

        with self.render_texture:
            with ViewportAs(min_x * self.x, min_y * self.y, max_x * self.width, max_y * self.height, PATTERN_TEX_SIZE,
                            PATTERN_TEX_SIZE):
                gl.glClearColor(0.0, 0.5, 1.0, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                for c in self.children:
                    c.render()

