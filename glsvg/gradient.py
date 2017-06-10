from svg_parser_utils import *
from vector_math import *
import shader
import svg_shader_constants
import math


class GradientShaders:

    def __init__(self):
        self._radial_shader = None
        self._linear_shader = None

    @property
    def radial_shader(self):
        if not self._radial_shader:
            self._radial_shader = shader.make_program_from_src(
                                    "vs", "radial_ps",
                                    svg_shader_constants.vertex, svg_shader_constants.radial)
        return self._radial_shader

    @property
    def linear_shader(self):
        if not self._linear_shader:
            self._linear_shader = shader.make_program_from_src(
                                    "vs", "linear_ps",
                                    svg_shader_constants.vertex, svg_shader_constants.linear)
        return self._linear_shader

gradient_shaders = GradientShaders()


class GradientContainer(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.callback_dict = {}

    def call_me_on_add(self, callback, grad_id):
        '''
        The client wants to know when the gradient with id grad_id gets
        added.  So store this callback for when that happens.
        When the desired gradient is added, the callback will be called
        with the gradient as the first and only argument.
        '''
        cblist = self.callback_dict.get(grad_id, None)
        if cblist == None:
            cblist = [callback]
            self.callback_dict[grad_id] = cblist
            return
        cblist.append(callback)

    def update(self, *args, **kwargs):
        raise NotImplementedError('update not done for GradientContainer')

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        callbacks = self.callback_dict.get(key, [])
        for callback in callbacks:
            callback(val)
        
    
class Gradient(object):
    def __init__(self, element, svg):
        self.element = element
        self.stops = {}
        for e in element.getiterator():
            if e.tag.endswith('stop'):
                style = parse_style(e.get('style', ''))
                color = parse_color(e.get('stop-color'))
                if 'stop-color' in style:
                    color = parse_color(style['stop-color'])
                color[3] = int(float(e.get('stop-opacity', '1')) * 255)
                if 'stop-opacity' in style:
                    color[3] = int(float(style['stop-opacity']) * 255)
                offset = parse_float(e.get('offset'))
                self.stops[offset] = color
        self.stops = sorted(self.stops.items())
        self.svg = svg
        self.grad_transform = Matrix(element.get('gradientTransform'))
        self.inv_transform = Matrix(element.get('gradientTransform')).inverse()
        self.opacity = element.get('opacity', 1.0)
        self.units = element.get('gradientUnits', 'objectBoundingBox')
        inherit = self.element.get('{http://www.w3.org/1999/xlink}href')
        parent = None
        delay_params = False
        if inherit:
            parent_id = inherit[1:]
            parent = self.svg._gradients.get(parent_id, None)
            if parent == None:
                self.svg._gradients.call_me_on_add(self.tardy_gradient_parsed, parent_id)
                delay_params = True
                return
        if not delay_params:
            self.get_params(parent)

    def sample(self, pt, path):
        if not self.stops: return [255, 0, 255, 255]
        t = self.grad_value(self.inv_transform(pt), path)
        if t < self.stops[0][0]:
            return self.stops[0][1]
        for n, top in enumerate(self.stops[1:]):
            bottom = self.stops[n]
            if t <= top[0]:
                u = bottom[0]
                v = top[0]
                alpha = (t - u)/(v - u)
                return [int(x[0] * (1 - alpha) + x[1] * alpha) for x in zip(bottom[1], top[1])]
        return self.stops[-1][1]

    def get_params(self, parent):
        for param in self.params:
            v = None
            if parent:
                v = getattr(parent, param, None)
            my_v = self.element.get(param)
            if my_v:
                v = str(my_v)
            if v:
                setattr(self, param, v)

    def tardy_gradient_parsed(self, gradient):
        self.get_params(gradient)
        
    def apply_shader(self, path, transform, opacity):
        pass
    
    def unapply_shader(self):
        pass


class LinearGradient(Gradient):
    params = ['x1', 'x2', 'y1', 'y2', 'stops']

    def __init__(self, *args):
        self.x1 = '0'
        self.x2 = "100%"
        self.y1 = '0'
        self.y2 = '0'
        Gradient.__init__(self, *args)

    def grad_value(self, pt, path):
        return ((pt[0] - self.get_x1(path)) * (self.get_x2(path) - self.get_x1(path)) + (pt[1] - self.get_y1(path)) * (self.get_y2(path) - self.get_y1(path))) \
            / ((self.get_x1(path) - self.get_x2(path)) ** 2 + (self.get_y1(path) - self.get_y2(path)) ** 2)

    def get_x1(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.x1)
            return percentage * (maxx - minx) + minx
        else:
            return float(self.x1)

    def get_x2(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.x2)
            return percentage * (maxx - minx) + minx
        else:
            return float(self.x2)

    def get_y2(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.y1)
            return percentage * (maxy - miny) + miny
        else:
            return float(self.y1)

    def get_y1(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.y2)
            return percentage * (maxy - miny) + miny
        else:
            return float(self.y2)

    def apply_shader(self, path, transform, opacity):
        if not self.stops: return
        gradient_shaders.linear_shader.use()
        gradient_shaders.linear_shader.uniformf("opacity", self.opacity * opacity)
        gradient_shaders.linear_shader.uniformf("start", self.get_x1(path), self.get_y1(path))
        gradient_shaders.linear_shader.uniformf("end", self.get_x2(path), self.get_y2(path))
        gradient_shaders.linear_shader.uniform_matrixf("worldTransform", False, svg_matrix_to_gl_matrix(transform))
        gradient_shaders.linear_shader.uniform_matrixf("gradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.grad_transform))
        gradient_shaders.linear_shader.uniform_matrixf("invGradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.inv_transform))
        stop_points = []
        for stop in self.stops:
            stop_point, color = stop
            stop_points.append(stop_point)
        while len(stop_points) < 5:
            stop_points.append(0.0)

        if len(stop_points) > 5:
            stop_points = stop_points[:5]

        gradient_shaders.linear_shader.uniformf("stops", *(stop_points[1:]))
        
        def get_stop(i):
            return self.stops[i] if i < len(self.stops) else self.stops[-1]
        
        for i in xrange(5):
            stop_point, color = get_stop(i)
            color = tuple(float(x)/255.0 for x in color)
            gradient_shaders.linear_shader.uniformf("stop" + str(i), *color)
    
    def unapply_shader(self):
        if not self.stops: return
        gradient_shaders.linear_shader.stop()


class RadialGradient(Gradient):
    params = ['cx', 'cy', 'r', 'stops']

    def __init__(self, *args):
        element = args[0]
        self.cx = '50%'
        self.cy = "50%"
        self.r = "100%"
        self.fx = element.get('fx', None)
        self.fy = element.get('fy', None)
        
        
        Gradient.__init__(self, *args)

    def grad_value(self, pt, path):
        return math.sqrt((pt[0] - self.get_cx(path)) ** 2 + (pt[1] - self.get_cy(path)) ** 2) / self.get_r(path)

    def get_cx(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.cx)
            return percentage * (maxx - minx) + minx
        else: #userSpaceOnUse
            return float(self.cx)

    def get_cy(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.cy)
            return percentage * (maxy - miny) + miny
        else: #userSpaceOnUse
            return float(self.cy)

    def get_fx(self, path):
        if self.fx == None:
            return self.get_cx(path)
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.fx)
            return percentage * (maxx - minx) + minx
        else: #userSpaceOnUse
            return float(self.fx)

    def get_fy(self, path):
        if self.fy == None:
            return self.get_cy(path)
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.fy)
            return percentage * (maxy - miny) + miny
        else: #userSpaceOnUse
            return float(self.fy)

    def get_r(self, path):
        if self.units == 'objectBoundingBox':
            minx, miny, maxx, maxy = path.bounding_box()
            percentage = parse_float(self.r)
            extent = min(maxx-minx, maxy-miny)
            return percentage * extent
        else: #userSpaceOnUse
            return float(self.r)

    def apply_shader(self, path, transform, opacity):
        if not self.stops: return
        gradient_shaders.radial_shader.use()
        gradient_shaders.radial_shader.uniformf("opacity", self.opacity*opacity)
        gradient_shaders.radial_shader.uniformf("radius", self.get_r(path))
        gradient_shaders.radial_shader.uniformf("center", self.get_cx(path), self.get_cy(path))
        gradient_shaders.radial_shader.uniformf("focalPoint", self.get_fx(path), self.get_fy(path))
        gradient_shaders.radial_shader.uniform_matrixf("worldTransform", False, svg_matrix_to_gl_matrix(transform))
        gradient_shaders.radial_shader.uniform_matrixf("gradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.grad_transform))
        gradient_shaders.radial_shader.uniform_matrixf("invGradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.inv_transform))
        stop_points = []
        for stop in self.stops:
            stop_point, color = stop
            stop_points.append(stop_point)
        
        while len(stop_points) < 5:
            stop_points.append(0.0)
        
        #can't support more than 4 of these bad boys..
        if len(stop_points) > 5:
            stop_points = stop_points[:5]

        gradient_shaders.radial_shader.uniformf("stops", *(stop_points[1:]))
        
        def get_stop(i):
            return self.stops[i] if i < len(self.stops) else (1.0, [0.0, 0.0, 0.0, 0.0])
        
        for i in xrange(len(stop_points)):
            stop_point, color = get_stop(i)
            color = tuple(float(x)/255.0 for x in color)
            gradient_shaders.radial_shader.uniformf("stop" + str(i), *color)
    
    def unapply_shader(self):
        if not self.stops: return
        gradient_shaders.radial_shader.stop()
