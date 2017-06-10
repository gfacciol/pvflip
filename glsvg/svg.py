"""GLSVG library for SVG rendering in PyOpenGL.

Example usage:
    $ import glsvg
    $ my_svg = glsvg.SVG('filename.svg')
    $ my_svg.draw(100, 200, angle=15)

"""

import OpenGL.GL as gl

try:
    import xml.etree.ElementTree
    from xml.etree.cElementTree import parse
except:
    import elementtree.ElementTree
    from elementtree.ElementTree import parse

import re
import math
import string
import traceback

from svg_constants import *

from glutils import *
from vector_math import *
from svg_parser_utils import parse_color, parse_float, parse_style, parse_list
from gradient import *

from svg_path import SVGPath, SVGGroup, SVGDefs, SVGUse, SVGMarker, SVGContainer
from svg_pattern import *
import graphics

from render_target import CanvasManager

class SVGConfig:
    """Configuration for how to render SVG objects, such as
    the amount of detail allowed for bezier curves and availability of the stencil buffer"""

    def __init__(self):

        self.use_fxaa = True

        #: The number of stencil bits available
        self.stencil_bits = gl.glGetInteger(gl.GL_STENCIL_BITS)

        #: Whether or not framebuffer objects are allowed
        self.has_framebuffer_objects = True

        #: Whether or not stencilling is allowed
        self.allow_stencil = self.stencil_bits > 0

        #: The number of line segments into which to subdivide Bezier splines.
        self.bezier_points = BEZIER_POINTS

        #: The number of line segments into which to subdivide circular and elliptic arcs.
        self.circle_points = CIRCLE_POINTS

        #: The minimum distance at which neighboring points are merged
        self.tolerance = TOLERANCE

    def super_detailed(self):
        """Returns a much more detailed copy of this config, for patterns"""

        cfg = SVGConfig()
        cfg.bezier_points *= 10
        cfg.circle_points *= 10
        cfg.tolerance /= 100
        return cfg

    def __repr__(self):
        return "<SVGConfig stencil_bits={0} fbo={1} circle_points={2} bezier_points={3}>".format(
            self.stencil_bits,
            self.has_framebuffer_objects,
            self.circle_points,
            self.bezier_points
        )


class SVGDoc(SVGContainer):
    """
    An SVG image document.

    Users should instantiate this object once for each SVG file they wish to
    render.

    """
    def __init__(self, filename_or_element, parent=None, anchor_x=0, anchor_y=0, config=None):
        """Creates an SVG document from a .svg or .svgz file.

        Args:
            `filename`: str
                The name of the file to be loaded.
            `anchor_x`: float
                The horizontal anchor position for scaling and rotations. Defaults to 0. The symbolic
                values 'left', 'center' and 'right' are also accepted.
            `anchor_y`: float
                The vertical anchor position for scaling and rotations. Defaults to 0. The symbolic
                values 'bottom', 'center' and 'top' are also accepted.
        """

        SVGContainer.__init__(self, parent)

        if not config:
            self.config = SVGConfig()
        else:
            self.config = config
        self._stencil_mask = 0

        #: Number of triangles in document
        self.n_tris = 0

        #: Number of lines in document
        self.n_lines = 0

        #: Map from id to path
        self.path_lookup = {}

        #: SVG paths
        self._paths = []

        #: Maps from pattern id to pattern
        self.patterns = {}

        #: Maps from id to marker def
        self.markers = {}

        #: Maps from id to path definition
        self.defs = {}

        #: Filename of original SVG file
        self.filename = filename_or_element if isinstance(filename_or_element, str) else None
        self._gradients = GradientContainer()

        if self.filename:
            if open(self.filename, 'rb').read(3) == '\x1f\x8b\x08':  # gzip magic numbers
                import gzip
                f = gzip.open(self.filename, 'rb')
            else:
                f = open(self.filename, 'rb')
            self.root = parse(f)._root
        else:
            self.root = filename_or_element

        self.parse_root(self.root)

        self._generate_disp_list()

        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

    def parse_root(self, root):
        self._paths = []

        wm = root.get("width", '0')
        hm = root.get("height", '0')

        self.x = 0
        self.y = 0

        self.width = parse_float(wm)
        self.height = parse_float(hm)

        self.preserve_aspect_ratio = root.get('preserveAspectRatio', 'none')

        if self.root.get("viewBox"):
            x, y, w, h = (parse_float(x) for x in parse_list(root.get("viewBox")))
            self.x = x
            self.y = y
            self.height = h
            self.width = w

        self.opacity = 1.0
        for e in root.getchildren():
            try:
                self._parse_element(e)
            except Exception as ex:
                print 'Exception while parsing element', e
                raise

    def _is_path_tag(self, e):
        return (e.tag.endswith('path')
                or e.tag.endswith('rect')
                or e.tag.endswith('polyline') or e.tag.endswith('polygon')
                or e.tag.endswith('line')
                or e.tag.endswith('circle') or e.tag.endswith('ellipse'))

    def _parse_element(self, e, parent=None):
        renderable = None
        if self._is_path_tag(e):
            renderable = SVGPath(self, e, parent)
            if not parent:
                self._paths.append(renderable)

            if renderable.id:
                self.path_lookup[renderable.id] = renderable
        elif e.tag.endswith('}g') or e.tag == 'g':
            renderable = SVGGroup(self, e, parent)
            if renderable.id:
                self.path_lookup[renderable.id] = renderable
                self.defs[renderable.id] = renderable
            if not parent and not renderable.is_def:
                self._paths.append(renderable)
        elif e.tag.endswith('svg'):
            renderable = SVGDoc(e, parent)
            self._paths.append(renderable)
        elif e.tag.endswith('marker'):
            renderable = SVGMarker(self, e, parent)
        elif e.tag.endswith("text"):
            self._warn("Text tag not supported")
        elif e.tag.endswith('linearGradient'):
            self._gradients[e.get('id')] = LinearGradient(e, self)
        elif e.tag.endswith('radialGradient'):
            self._gradients[e.get('id')] = RadialGradient(e, self)
        elif e.tag.endswith('pattern'):
            renderable = SVGPattern(self, e, parent)
            self.patterns[e.get('id')] = renderable
        elif e.tag.endswith('defs'):
            renderable = SVGDefs(self, e, parent)
        elif e.tag.endswith('marker'):
            renderable = SVGMarker(self, e, parent)
        elif e.tag.endswith('use'):
            renderable = SVGUse(self, e, parent)
            self._paths.append(renderable)
        for c in e.getchildren():
            try:
                self._parse_element(c, renderable)
            except Exception, ex:
                print 'Exception while parsing element', c
                raise


    def get_path_ids(self):
        """Returns all the path ids"""
        return self.path_lookup.keys()

    def get_path_by_id(self, id):
        """Returns a path for the given id, or key error"""
        return self.path_lookup[id]

    def _register_pattern_part(self, pattern_id, pattern_svg_path):
        print "registering pattern"
        self.patterns[pattern_id].paths.append(pattern_svg_path)

    def _set_anchor_x(self, anchor_x):
        self._anchor_x = anchor_x
        if self._anchor_x == 'left':
            self._a_x = 0
        elif self._anchor_x == 'center':
            self._a_x = self.width * .5
        elif self._anchor_x == 'right':
            self._a_x = self.width
        else:
            self._a_x = self._anchor_x

    def _get_anchor_x(self):
        return self._anchor_x

    #: Where the document is anchored. Valid values are numerical, or 'left', 'right', 'center'
    anchor_x = property(_get_anchor_x, _set_anchor_x)

    def _set_anchor_y(self, anchor_y):
        self._anchor_y = anchor_y
        if self._anchor_y == 'bottom':
            self._a_y = 0
        elif self._anchor_y == 'center':
            self._a_y = self.height * .5
        elif self._anchor_y == 'top':
            self._a_y = self.height
        else:
            self._a_y = self.anchor_y

    def _get_anchor_y(self):
        return self._anchor_y

    #: Where the document is anchored. Valid values are numerical, or 'top', 'bottom', 'center'
    anchor_y = property(_get_anchor_y, _set_anchor_y)

    def _generate_disp_list(self):

        # prepare all the patterns
        self.prerender_patterns()

        # prepare all the predefined paths
        self.prerender_defs()

        with DisplayListGenerator() as display_list:
            self.disp_list = display_list
            self.render()

    def draw(self, x, y, z=0, angle=0, scale=1):
        """Draws the SVG to screen.

        Args:
            `x` : float
                The x-coordinate at which to draw.
            `y` : float
                The y-coordinate at which to draw.
            `z` : float
                The z-coordinate at which to draw. Defaults to 0. Note that z-ordering may not
                give expected results when transparency is used.
            `angle` : float
                The angle by which the image should be rotated (in degrees). Defaults to 0.
            `scale` : float
                The amount by which the image should be scaled, either as a float, or a tuple
                of two floats (xscale, yscale).

        """
        #CanvasManager.inst().update()
        #bg = CanvasManager.inst().get('BackgroundImage')

        with CurrentTransform():
            gl.glTranslatef(x, y, z)
            if angle:
                gl.glRotatef(angle, 0, 0, 1)
            if scale != 1:
                try:
                    gl.glScalef(scale[0], scale[1], 1)
                except TypeError:
                    gl.glScalef(scale, scale, 1)
            if self._a_x or self._a_y:
                gl.glTranslatef(-self._a_x, -self._a_y, 0)

            #with bg:
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            self.disp_list()
        #bg.blit()

    def prerender_defs(self):
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        for d in self.defs.values():
            d.render()

    def prerender_patterns(self):
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        for pattern in self.patterns.values():
            pattern.render()

    def render(self):
        """Render the SVG file without any display lists or transforms. Use draw instead. """
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        graphics.clear_stats()
        #clear out stencils
        with Matrix.translation(self.x, self.y):
            for svg_path in self._paths:
                svg_path.render()

    def _warn(self, message):
        print "Warning: SVG Parser (%s) - %s" % (self.filename, message)
