#!/usr/bin/env python
# Copyright 2013, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
############################################################################
#
# 08/2016: change glfw to add drag-and-drop, support for retina displays
# 06/2015: add snapshot key S 
# 05/2015: organize shaders
# 04/2015: use os.stat to detect changes file changes
# v03 : faster image load with piio.read_buffer avoids passing trough numpy
#       fragment shader color manipulation (optic flow)
# v02 : use fragment shader for the contrast change, uses GL_RGBF32 as internal format
#       improved image_data_to_RGBbitmap (more efficient)
# v01 : mutex wheel events, translation with mouse drag
# v00 : stable but no translation with mouse drag
# v-1 : no event mutex

from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

# Accelerate startup by preventing importing numpy, which for some 
# reason is loaded during shader compilation but never used.
# http://stackoverflow.com/questions/1350466/preventing-python-code-from-importing-certain-modules
import sys
sys.modules['numpy']=None

from OpenGL.GL import *
from OpenGL.GL.shaders import *
# TODO REMOVE GLUT: only needed for the text
import OpenGL.GLUT as glut
from glfw import glfw

### SYSTEM SPECIFIC STUFF
import platform
if platform.system() == 'Darwin':
   GLOBAL_WHEEL_SCALING = 0.1
else:
   GLOBAL_WHEEL_SCALING = 1.0

global HELPstr
HELPstr=""

oflow_shader = """
    vec4 hsvtorgb(vec4 colo)
    {
       vec4 outp;
       float r, g, b, h, s, v; 
       r=g=b=h=s=v=0.0;
       h = colo.x; s = colo.y; v = colo.z;
       if (s == 0.0) { r = g = b = v; }
       else {
          float H = mod(floor(h/60.0) , 6.0);
          float p, q, t, f = h/60.0 - H;
          p = v * (1.0 - s);
          q = v * (1.0 - f*s);
          t = v * (1.0 - (1.0 - f)*s);
          if(H == 6.0 || H == 0.0) { r = v; g = t; b = p; }
          else if(H == -1.0 || H == 5.0) { r = v; g = p; b = q; } 
          else if(H == 1.0) { r = q; g = v; b = p; }
          else if(H == 2.0) { r = p; g = v; b = t; }
          else if(H == 3.0) { r = p; g = q; b = v; }
          else if(H == 4.0) { r = t; g = p; b = v; }
       }
       outp.x = r; outp.y = g; outp.z = b; outp.w=colo.w;
       return outp;
    }

   float M_PI = 3.1415926535897932;
   float M_PI_2 = 1.5707963267948966;
    float atan2(float x, float y)
    {
       if (x>0.0) { return atan(y/x); }
       else if(x<0.0 && y>0.0) { return atan(y/x) + M_PI; }
       else if(x<0.0 && y<=0.0 ) { return atan(y/x) - M_PI; }
       else if(x==0.0 && y>0.0 ) { return M_PI_2; }
       else if(x==0.0 && y<0.0 ) { return -M_PI_2; }
       return 0.0;
    }

  uniform sampler2D src;
  uniform float shader_a;
  uniform float shader_b;

  void main (void)
  {
       vec4 p = texture2D(src, gl_TexCoord[0].xy);
       float a = (180.0/M_PI)*(atan2(-p.x,p.w) + M_PI);
       float r = sqrt(p.x*p.x+p.w*p.w)*shader_a;
       vec4 q = vec4(a, clamp(r,0.0,1.0),clamp(r,0.0,1.0),0.0);
       p = hsvtorgb(q);

       gl_FragColor = clamp(p, 0.0, 1.0) ;

  }
   """

hsv_shader = """
    // OLD AND WRONG
    vec4 hsvtorgb(vec4 colo)
    {
       vec4 outp;
       float r, g, b, h, s, v; 
       r=g=b=h=s=v=0.0;
       h = colo.x; s = colo.y; v = colo.z;
       if (s == 0.0) { r = g = b = v; }
       else {
          float H = mod(floor(h/60.0) , 6.0);
          float p, q, t, f = h/60.0 - H;
          p = v * (1.0 - s);
          q = v * (1.0 - f*s);
          t = v * (1.0 - (1.0 - f)*s);
          if(H == 6.0 || H == 0.0) { r = v; g = t; b = p; }
          else if(H == -1.0 || H == 5.0) { r = v; g = p; b = q; } 
          else if(H == 1.0) { r = q; g = v; b = p; }
          else if(H == 2.0) { r = p; g = v; b = t; }
          else if(H == 3.0) { r = p; g = q; b = v; }
          else if(H == 4.0) { r = t; g = p; b = v; }
       }
       outp.x = r; outp.y = g; outp.z = b; outp.w=colo.w;
       return outp;
    }

    vec3 hsv2rgb(vec3 c)
    {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

  uniform sampler2D src;
  uniform float shader_a;
  uniform float shader_b;

  void main (void)
  {
       vec4 q = texture2D(src, gl_TexCoord[0].xy);
       //vec4 p = hsvtorgb(q);
       q = vec4(q.x/360.0,q.y,q.z,q.w);
       vec3 pp = hsv2rgb(q.xyz);
       vec4 p = vec4(pp.x,pp.y,pp.z,q.w);

       gl_FragColor = clamp(p * shader_a + shader_b, 0.0, 1.0);

  }
   """

bayer_shader = """
   uniform sampler2D src;
   uniform float shader_a;
   uniform float shader_b;
   uniform int   shader_c;
   uniform vec2  _tilesz;
   uniform bool  interp;  // interpolate the other channels

   void main (void)
   {
      vec4 p  = vec4(0.,0.,0.,1.0);
      vec2 uv = gl_TexCoord[0].xy;
      vec4 pp = texture2D(src, uv);
      vec2 q  = vec2(floor(uv.x * _tilesz.x), floor(uv.y * _tilesz.y));
      float i1 = mod(q.x, 2.0);
      float i2 = mod(q.y, 2.0);


      if(i1<0.5 && i2<0.5) {
         p.x = pp.x * 1.5;
         if(interp) {
         vec2 uv1 = uv + vec2(1.0/_tilesz.x, 1.0 /_tilesz.y);
         vec2 uv2 = uv + vec2(1.0/_tilesz.x, 0.0 /_tilesz.y);
         vec2 uv3 = uv + vec2(0.0/_tilesz.x, 1.0 /_tilesz.y);
         vec4 pp1       = texture2D(src, uv1);
         vec4 pp2       = texture2D(src, uv2);
         vec4 pp3       = texture2D(src, uv3);
         p.z = pp1.x * 2.0;
         p.y = (pp2.x + pp3.x)/2.0;
         }
      } else if(i1>=0.5 && i2>=0.5) {
         p.z = pp.x * 2.0;
         if(interp) {
         vec2 uv1 = uv + vec2(-1.0/_tilesz.x,-1.0 /_tilesz.y);
         vec2 uv2 = uv + vec2(-1.0/_tilesz.x, 0.0 /_tilesz.y);
         vec2 uv3 = uv + vec2(0.0/_tilesz.x, -1.0 /_tilesz.y);
         vec4 pp1       = texture2D(src, uv1);
         vec4 pp2       = texture2D(src, uv2);
         vec4 pp3       = texture2D(src, uv3);
         p.x = pp1.x * 1.5;
         p.y = (pp2.x + pp3.x)/2.0;
         }
      } else if(i1<0.5 && i2>=0.5) {
         p.y = pp.x;
         if(interp) {
         vec2 uv1 = uv + vec2(0.0/_tilesz.x, -1.0 /_tilesz.y);
         vec2 uv2 = uv + vec2(1.0/_tilesz.x,  0.0 /_tilesz.y);
         vec4 pp1       = texture2D(src, uv1);
         vec4 pp2       = texture2D(src, uv2);
         p.x = pp1.x * 1.5;
         p.z = pp2.x * 2.0;
         }
      } else {
         p.y = pp.x;
         if(interp) {
         vec2 uv1 = uv + vec2(-1.0/_tilesz.x, 0.0 /_tilesz.y);
         vec2 uv2 = uv + vec2(0.0/_tilesz.x,  1.0 /_tilesz.y);
         vec4 pp1       = texture2D(src, uv1);
         vec4 pp2       = texture2D(src, uv2);
         p.x = pp1.x * 1.5;
         p.z = pp2.x * 2.0;
         }
      }

      p = p * shader_a + shader_b;
      if (shader_c > 0)
         p = 1.0 - p;
      gl_FragColor = clamp(p , 0.0, 1.0);
      //gl_FragColor = gl_Color*shader_a; // the color of the triangle
   }
   """

rgba_shader = """
   uniform sampler2D src;
   uniform float shader_a;
   uniform float shader_b;
   uniform int   shader_c;

   void main (void)
   {
      vec4 p = texture2D(src, gl_TexCoord[0].xy);
      p = p * shader_a + shader_b;
      if (shader_c > 0)
         p = 1.0 - p;
      gl_FragColor = clamp(p , 0.0, 1.0);
      //gl_FragColor = gl_Color*shader_a; // the color of the triangle
   }
   """

rgb_shader = """
   uniform sampler2D src;
   uniform float shader_a;
   uniform int   shader_c;
   uniform float shader_B0;
   uniform float shader_B1;
   uniform float shader_B2;

   void main (void)
   {
      vec4 p = texture2D(src, gl_TexCoord[0].xy);
      vec4 B = vec4(shader_B0, shader_B1, shader_B2, 0);

      p = p * shader_a + B;
      if (shader_c > 0)
         p = 1.0 - p;
      gl_FragColor = clamp(p , 0.0, 1.0);
      //gl_FragColor = gl_Color*shader_a; // the color of the triangle
   }
   """

rb_shader = """
   uniform sampler2D src;
   uniform float shader_a;
   uniform float shader_b;

   void main (void)
   {
      vec4 p = texture2D(src, gl_TexCoord[0].xy);
      p.xyzw=vec4(p.x * shader_a + shader_b,
                  p.x * shader_a + shader_b,
                  p.x * shader_a + shader_b, 0.0);
      gl_FragColor = clamp(p, 0.0, 1.0);
   }
   """

depth_shader_hsv = """
    vec3 hsv2rgb(vec3 c)
    {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

  uniform sampler2D src;
  uniform float shader_a;
  uniform float shader_b;

  void main (void)
  {
       vec4 q = texture2D(src, gl_TexCoord[0].xy);
       q = q * shader_a + shader_b;
       vec3 pp = hsv2rgb(q.xxx);
       vec4 p = vec4(pp.x,pp.y,pp.z,q.w);

       gl_FragColor = p; //clamp(p , 0.0, 1.0);

  }
   """

depth_shader_jet = """
/*
// translate value x in [0..1] into color triplet using "jet" color map
// if out of range, use darker colors
// variation of an idea by http://www.metastine.com/?p=7
void jet(float x, int& r, int& g, int& b)
{
    if (x < 0) x = -0.05;
    if (x > 1) x =  1.05;
    x = x / 1.15 + 0.1; // use slightly asymmetric range to avoid darkest shade
 of blue.
    r = max(0, min(255, round(255 * (1.5 - 4*fabs(x - .75)))));
    g = max(0, min(255, round(255 * (1.5 - 4*fabs(x - .5 )))));
    b = max(0, min(255, round(255 * (1.5 - 4*fabs(x - .25)))));
}
*/

  uniform sampler2D src;
  uniform float shader_a;
  uniform float shader_b;
  uniform int   shader_c;

  void main (void)
  {
       vec4 q = texture2D(src, gl_TexCoord[0].xy);
       q = 1.0 - (q * shader_a + shader_b);
       if (shader_c > 0)
         q = 1.0 - q;
       if(q.x < 0.0) q.x = -0.05;
       if(q.x > 1.0) q.x =  1.05;
       q.x = q.x/1.15 + 0.1;
       vec4 p;
       p.x = 1.5 - abs(q.x - .75)*4.0;
       p.y = 1.5 - abs(q.x - .50)*4.0;
       p.z = 1.5 - abs(q.x - .25)*4.0;
       p.w = 1.0;

       gl_FragColor = clamp(p, 0.0, 1.0);

  }
   """

depth_shader_dirt = """
/*
// translate value x in [0..1] into color triplet using "dirt" color map
*/

  uniform sampler2D src;
  uniform float shader_a;
  uniform float shader_b;
  uniform int   shader_c;

  void main (void)
  {

float Rx[7], Ry[7];
Rx[0]=0.; Rx[1]=35.; Rx[2]=82.5; Rx[3]= 91.; Rx[4]=97.5; Rx[5]=100.; Rx[6]=100.;
Ry[0]=1.; Ry[1]=1.;  Ry[2]=.54;  Ry[3]= .41; Ry[4]=.25;  Ry[5]=.2;   Ry[6]=.2;
float Gx[7], Gy[7];
Gx[0]=0.; Gx[1]=4.; Gx[2]=15.; Gx[3]=25.; Gx[4]=85. ; Gx[5]=91. ; Gx[5]=100.;
Gy[0]=1.; Gy[1]=1.; Gy[2]=0.8; Gy[3]=0.7; Gy[4]=0.22; Gy[5]=0.15; Gy[5]=0.;
float Bx[7], By[7];
Bx[0]= 0.; Bx[1]= 10. ; Bx[2]= 21. ; Bx[3]=24. ; Bx[4]=100.; Bx[5]=100.; Bx[6]=100.;
By[0]= 1.; By[1]= 0.35; By[2]= 0.4 ; By[3]=0.  ; By[4]=0.;   By[5]=0.;   By[6]=0.;


       vec4 q = texture2D(src, gl_TexCoord[0].xy);
       q = 1.0 - (q * shader_a + shader_b);
       if (shader_c > 0)
         q = 1.0 - q;

       q = clamp(q, 0.0, 1.0);

       vec4 p;
       p.w = 1.0;

       for(int i=1;i<7;i++) {
        if(i<6 && q.x >= Rx[i-1]/100.0 && q.x <= Rx[i]/100.0){
               float cc = (Rx[i] - q.x*100.0) / (Rx[i] -  Rx[i-1]);
               p.x = cc * Ry[i-1] + (1.0 - cc)*Ry[i];
        }
        if(q.y >= Gx[i-1]/100.0 && q.y <= Gx[i]/100.0){
               float cc = (Gx[i] - q.y*100.0) / (Gx[i] -  Gx[i-1]);
               p.y = cc * Gy[i-1] + (1.0 - cc)*Gy[i];
        }
        if(i<5 && q.z >= Bx[i-1]/100.0 && q.z <= Bx[i]/100.0){
               float cc = (Bx[i] - q.z*100.0) / (Bx[i] -  Bx[i-1]);
               p.z = cc * By[i-1] + (1.0 - cc)*By[i];
        }
       }

       gl_FragColor = clamp(p, 0.0, 1.0);

  }
   """

SHADERS = { 
      'rgba' : rgba_shader,
      'bayer': bayer_shader,
      'hsv'  : hsv_shader,
      'oflow': oflow_shader,
      'rb'   : rb_shader, 
      'dhsv' : depth_shader_hsv,
      'djet' : depth_shader_jet,
      'ddirt': depth_shader_dirt,
      'rgb'  : rgb_shader,
      }
SHADER_PROGRAMS = {}

def use_shader_program(name):
   ##########
   ######## SETUP FRAGMENT SHADER FOR CONTRAST CHANGE
   ##########
   # http://www.cityinabottle.org/nodebox/shader/
   # http://www.seethroughskin.com/blog/?p=771
   # http://python-opengl-examples.blogspot.com.es/
   # http://www.lighthouse3d.com/tutorials/glsl-core-tutorial/fragment-shader/

   # programs, shaders, and the current program are global variables
   global program, SHADERS, SHADER_PROGRAMS
   if name not in SHADER_PROGRAMS:
      SHADER_PROGRAMS[name] = compileProgram(
            compileShader(SHADERS[name], GL_FRAGMENT_SHADER),
            );
      glLinkProgram( SHADER_PROGRAMS[name] )
   program = SHADER_PROGRAMS[name]
   # try to activate/enable shader program
   # handle errors wisely
   try:
      glUseProgram(program)   
   except OpenGL.error.GLError:
      print(glGetProgramInfoLog(program))
      raise


#### INTERFACE STATE
class ViewportState:
   winx,winy=0,0
   zoom_param  = 1
   scale_param = 1.0      ## TODO internal variables should not be here
   bias_param  = 0
   inv_param   = 0
   bias_vector = [0,0,0]

   v_center = 0.5
   v_radius = 0.5
   v_center_vector = [0.5, 0.5, 0.5]

   dx,dy=0,0
   dragdx,dragdy=0,0
   dragx0,dragy0=0,0

   # Window TODO: Needed?
   window = None

   # mouse state variables
   mx = 0
   my = 0
   x0=0; y0=0; w0=0; h0=0; b0state=''; b1state='' # NOT USED YET

   # keyboard
   shift_is_pressed=0
   alt_is_pressed=0

   # re-display
   redisp = 1
   resize = 0

   #if the window has been resized by the used then automatic resize will be disabled
   window_has_been_resized_by_the_user = 0  

   # mute and buffer fast events  
   mute_keyboard=0
   mute_sweep=0
   mute_wheel=0
   mute_wheel_buffer=[0,0] 

   # HUD info
   display_hud = 1
   txt_val='0'
   txt_pos='0,0'

   # not clear yet
   data_min = 0
   data_max = 255

   # VISUALIZE FLOW
   TOGGLE_FLOW_COLORS = 0
   TOGGLE_AUTOMATIC_RANGE = 0
   TOGGLE_FIT_TO_WINDOW_SIZE = 0



   ## contrast functions
   def update_scale_and_bias(V):
      ''' scale and bias are applied to the pixels as: scale * pixel + bias'''
      if V.v_radius:
         V.scale_param = 1/(2.0*V.v_radius)
      V.bias_param  = -(V.v_center-V.v_radius)*V.scale_param
      V.bias_vector[0] = (V.v_radius - V.v_center_vector[0])*V.scale_param
      V.bias_vector[1] = (V.v_radius - V.v_center_vector[1])*V.scale_param
      V.bias_vector[2] = (V.v_radius - V.v_center_vector[2])*V.scale_param
      V.inv_param   = 0
      V.redisp=1

   def radius_update(V, offset):
      d = V.v_radius*.1
      V.v_radius = max(V.v_radius + d*offset,0)
      V.update_scale_and_bias()

   def center_update(V, offset):
      d = V.v_radius*.1
      V.v_center = min(max(V.v_center + d*offset,V.data_min),V.data_max)
      V.v_center_vector[0] = min(max(V.v_center_vector[0] + d*offset,V.data_min),V.data_max)
      V.v_center_vector[1] = min(max(V.v_center_vector[1] + d*offset,V.data_min),V.data_max)
      V.v_center_vector[2] = min(max(V.v_center_vector[2] + d*offset,V.data_min),V.data_max)
      V.update_scale_and_bias()

   def center_update_value(V, centerval):
      V.v_center = centerval
      V.update_scale_and_bias()

   def center_update_vector(V, centervec):
      V.v_center_vector = centervec
      V.update_scale_and_bias()
   
   def reset_scale_bias(V):
      V.v_radius=(V.data_max-V.data_min)/2.0
      V.v_center=(V.data_max+V.data_min)/2.0
      V.v_center_vector[0] = V.v_center
      V.v_center_vector[1] = V.v_center
      V.v_center_vector[2] = V.v_center
      V.update_scale_and_bias()


   def reset_range_to_8bits(V): 
      V.v_center = 127.5
      V.v_radius = 127.5
      V.v_center_vector[0] = V.v_center
      V.v_center_vector[1] = V.v_center
      V.v_center_vector[2] = V.v_center
      V.update_scale_and_bias()


   def compute_image_coordinates(self,mx,my):
      x = mx/self.zoom_param + self.dx
      y = my/self.zoom_param + self.dy
      return x,y



   ## pan and zoom functions
   def zoom_update(V, offset, mx=-1, my=-1):

      if mx<0 or my<0 or mx >= V.winx or my >= V.winy:
          mx = V.winx/2
          my = V.winy/2

      tx,ty = V.compute_image_coordinates(mx, my)
      
      factor = 1.0+(1.3-1.0)*GLOBAL_WHEEL_SCALING*abs(offset);
      if (offset > 0):
          factor = 1.0/factor

      #newzoom = V.zoom_param + offset/10. ## old
      newzoom = V.zoom_param * factor
      if newzoom >= 0.001 :       # prevent image inversion
         V.zoom_param = newzoom


      V.dx = tx - mx/V.zoom_param
      V.dy = ty - my/V.zoom_param

      # disable FIT TO WINDOW
      if V.TOGGLE_FIT_TO_WINDOW_SIZE:
         V.TOGGLE_FIT_TO_WINDOW_SIZE=0
         print("DISABLE: fit image to window")

      V.redisp=1

   def reset_zoom(V):
      V.dx,V.dy=0,0
      V.zoom_param  = 1
      V.redisp=1
      V.dragdx,V.dragdy=0,0

   def translation_update(self, dx, dy): 
      ndx,ndy = V.dx+dx,V.dy+dy

      # TODO USING D HERE?
      global D

      ## check if falls out of the image
      if D.w+ndx > 0 and ndx < D.w and D.h+ndy > 0 and ndy < D.h:
         V.dx,V.dy=ndx,ndy
         V.redisp=1


   def update_zoom_position_to_fit_window(V):
      global D
      from math import floor
      V.zoom_param  = min(V.winx*1.0/D.w,V.winy*1.0/D.h)
      V.dx,V.dy= -floor((V.winx/V.zoom_param - D.w)/2.0) ,  - floor((V.winy/V.zoom_param - D.h)/2.0)
      V.dragdx,V.dragdy=0,0
      V.window_has_been_resized_by_the_user=1
      V.redisp=1


#### IMAGE STATE
class ImageState:
   # image size
   w=0
   h=0
   nch=0
   # image data
   imageBitmapTiles=0
   v_max = 0
   v_min = 0
   mtime = 0

   def get_image_point(self,x,y):
      if x>=0 and y>=0 and x<self.w and y<self.h:
         #### ACCESS THE RIGHT TILE
         for tile in self.imageBitmapTiles:
            if tile[1] <= x and tile[2] <= y and tile[1]+tile[3] > x and tile[2]+tile[4] > y:
               idx = (x-tile[1]+(y-tile[2])*tile[3])*tile[5]
               return tile[0][idx:idx+tile[5]]
         # this should never happen
         print("this should never happen")
         return None
      else:
         return None



## TODO MERGE D AND DD

class DataBackend:
   ### TODO :  load image, change image
   pass
   

V = ViewportState()
D = ImageState()
DD = {}
current_image_idx=0



def load_image(imagename):
   import piio
   try:
#      im,w,h,nch = piio.read_buffer(imagename)
      tiles,w,h,nch,vmin,vmax = piio.read_tiled_buffers(imagename)
#      (im,x0,y0,w,h,nch) = tiles[0]
#      v_min,v_max=0.0,255.0
#      v_min,v_max = piio.minmax(im)
#      print max(map(lambda x: float('nan') if math.isinf(x) else  x , im))
      return tiles,w,h,nch,vmin,vmax
   except (SystemError, IOError) as e:
      print('error reading the image: %s'%e)
      raise IOError


def insert_images(filenames):
   global current_image_idx
   import sys

   # insert the files starting from the current image
   filenames.reverse()
   for n in filenames:
      print("Adding: %s"%n)
      sys.argv.insert(current_image_idx+2,n)


def remove_current_image():
    ''' returns true if succeded removing the image'''
    global DD, V, current_image_idx
    import sys

    # don't remove the last image
    if len(sys.argv) <= 2:
       return False

    # remove the image from argv and DD
    name = sys.argv.pop(current_image_idx+1)
    print ("Dropping %s"%name)

    if current_image_idx in DD:
       print(DD[current_image_idx])
       DD.pop(current_image_idx)
    return True


def change_image(new_idx):
   '''updates D and DD: acts as a cache of the images
      returns the idx value of the next valid image
   '''
   global D,DD

   BUFF=10  # BUFFERED IMAGES
   NUM_FILES    = (len(sys.argv)-1)
   new_idx_bak  = new_idx
   new_idx      = new_idx % NUM_FILES
   new_filename = sys.argv[new_idx+1]

   from os import stat, path
   # check if the file was already read before
   if new_idx in DD:
      if new_filename != '-' and not new_filename.startswith('/dev/') and DD[new_idx].mtime != -1 and \
        (DD[new_idx].mtime < stat(new_filename).st_mtime or DD[new_idx].filename != new_filename):
         print(new_filename + ' has changed. Reloading...')
         DD.pop(new_idx)

   # the image seems to be there
   if new_idx not in DD:
      # load_image may trow an exception if the file is not readable or it doesn't exist
      try:
         T = DD[new_idx] = ImageState()

         tic()
         # read the image
         T.imageBitmapTiles,T.w,T.h,T.nch,T.v_min,T.v_max = load_image(new_filename)
         T.filename = new_filename
         try:   # if mtime cannot be read, then set it to -1
            T.mtime = (stat(new_filename).st_mtime)
         except OSError:
            T.mtime = -1
         setupTexturesFromImageTiles(T.imageBitmapTiles,T.w,T.h,T.nch)
         V.data_min, V.data_max =  T.v_min,T.v_max
         toc('loadImage+data->RGBbitmap+texture setup')

         D = T     # everything is ok, update the corrent image data
      except IOError:
         DD.pop(new_idx)
         print(new_filename + '. Skipping...')
         sys.argv.pop(new_idx+1)
         if len(sys.argv) == 1: 
            print('self destruct!\n')
            #glfw.set_window_should_close(window,1) #window not available
            exit(1)
         return new_idx_bak

      # tidy up memory 
      if NUM_FILES > BUFF*2:
         if ((new_idx-BUFF) % NUM_FILES) in DD:
           DD.pop((new_idx-BUFF) % NUM_FILES)
   
         if ((new_idx+BUFF) % NUM_FILES) in DD:
           DD.pop((new_idx+BUFF) % NUM_FILES)

   else:
      D = DD[new_idx]

      # setup texture 
      #tic()
      setupTexturesFromImageTiles(D.imageBitmapTiles,D.w,D.h,D.nch)
      V.data_min, V.data_max=  D.v_min,D.v_max 
      #toc('texture setup')

   print (new_idx,D.filename, (D.w,D.h,D.nch), (D.v_min,D.v_max))

   return new_idx


### TODO MOVE MOUSE STATE VARIABLES
# global variables for the mouse
x0=0; y0=0; w0=0; h0=0; b0state=''; b1state=''





def mouseMotion_callback(window, x,y):
    import math 
    global V,D
    global x0,y0,w0,h0,b0state,b1state

    # compute real image coordinates
    tx,ty = V.compute_image_coordinates(x,y)

    ### region selection
    if b1state=='pressed' :
       w0,h0 = tx-x0,ty-y0
       V.redisp=1
    if b0state=='pressed' :
       V.dragdx,V.dragdy = tx-V.dragx0,ty-V.dragy0
       V.redisp=1
    # adjust bias usign concrete pixel
    if V.shift_is_pressed and not V.mute_sweep:
       centerval = D.get_image_point(int(tx),int(ty))
       if not (centerval==None or math.isnan(sum(centerval)) or math.isinf(sum(centerval))):
          V.center_update_value(sum(centerval)/len(centerval))
          if len(centerval)==3:
              V.center_update_vector(centerval)
          V.mute_sweep=1


    centerval = D.get_image_point(int(tx),int(ty))
    V.txt_pos = '%s %s'%(int(tx),int(ty))
    if not centerval==None:
       if len(centerval)==1:
          V.txt_val = '%s'%(centerval[0])
       elif len(centerval)==2:
          V.txt_val = '%s %s'%(centerval[0], centerval[1])
       else:
          V.txt_val = '%s %s %s'%(centerval[0], centerval[1], centerval[2])
       glfw.set_window_title(window, '%s:[%s]'%(V.txt_pos,V.txt_val))

    # Update viewport mouse position
    V.mx, V.my = x, y

    # this seems to be needed by the non-composed window managers
    V.redisp = 1


#    title='p:%s,%s [+%s+%s %sx%s]' % (x+V.dx,y+V.dy,x0+V.dx,y0+V.dy,w0,h0)
#    glfw.set_window_title(window, title)



def mouseButtons_callback(window, button, action, mods):
    global V
    global x0,y0,w0,h0,b0state,b1state

    # select region
    if button==glfw.MOUSE_BUTTON_RIGHT and action==glfw.PRESS:
       x,y = glfw.get_cursor_pos (window)
       x0,y0 = V.compute_image_coordinates(x,y)
       w0,h0=0,0
       b1state='pressed'
       V.redisp=1
    elif button==glfw.MOUSE_BUTTON_RIGHT and action==glfw.RELEASE:
       x,y = glfw.get_cursor_pos (window)
       curr_x,curr_y = V.compute_image_coordinates(x,y)
#       print(curr_x, curr_y)
       w0,h0 = int(curr_x)-int(x0),int(curr_y)-int(y0)
       b1state='released'
       xx0,yy0 = x0,y0
       xx1,yy1 = x0+w0,y0+h0
       xx0,yy0,xx1,yy1 = int(xx0),int(yy0),int(xx1),int(yy1)
       print(xx0, yy0, abs(xx1-xx0), abs(yy1-yy0))
       V.redisp=1

    # drag
    if button==glfw.MOUSE_BUTTON_LEFT and action==glfw.PRESS:
       x,y = glfw.get_cursor_pos (window)
       V.dragx0,V.dragy0 = V.compute_image_coordinates(x,y)
       V.dragdx,V.dragdy=0,0
       b0state='pressed'
       V.redisp=1
    elif button==glfw.MOUSE_BUTTON_LEFT and action==glfw.RELEASE:
       x,y = glfw.get_cursor_pos (window)
       curr_x,curr_y = V.compute_image_coordinates(x,y)
       V.dragdx,V.dragdy = curr_x-V.dragx0,curr_y-V.dragy0
       b0state='released'
       V.dx=V.dx-V.dragdx
       V.dy=V.dy-V.dragdy
       V.dragdx=0
       V.dragdy=0
       V.redisp=1




def mouseWheel_callback(window, xoffset, yoffset):
      global V,D
      if V.mute_wheel:
         V.mute_wheel_buffer[0]=V.mute_wheel_buffer[0]+xoffset
         V.mute_wheel_buffer[1]=V.mute_wheel_buffer[1]+yoffset
         return
      else:
         xoffset=xoffset+V.mute_wheel_buffer[0]
         yoffset=yoffset+V.mute_wheel_buffer[1]
         V.mute_wheel_buffer = [0,0]
         V.mute_wheel=1

      curr_x,curr_y = glfw.get_cursor_pos (window)

      # zoom
      if V.alt_is_pressed:
         V.zoom_update(yoffset*GLOBAL_WHEEL_SCALING,curr_x,curr_y)
      # scale
      elif V.shift_is_pressed:
         V.radius_update(yoffset*GLOBAL_WHEEL_SCALING)
      # bias and scale
      else: # nothing pressed
         V.center_update(yoffset*GLOBAL_WHEEL_SCALING)
         V.radius_update(xoffset*GLOBAL_WHEEL_SCALING)




# letters and numbers
def keyboard_callback(window, key, scancode, action, mods):
    global V,D

    if V.mute_keyboard: # only mute the spacebar event
       return

    key_name = glfw.get_key_name(key, 0);
    # this the actual letter independently of the keyboard
    if type(key_name)!=type(None) and 'A' <= key_name and key_name <= 'z':
       # replace the pressed key
       key_name = key_name.upper()
       key = glfw.__dict__['KEY_%s'%key_name]

    # navigate
    winx, winy= glfw.get_framebuffer_size(window)
    if key==glfw.KEY_RIGHT and (action==glfw.PRESS or action==glfw.REPEAT):
       V.translation_update(winx/4/V.zoom_param,0)
    elif key==glfw.KEY_UP and (action==glfw.PRESS or action==glfw.REPEAT):
       V.translation_update(0,-winy/4/V.zoom_param)
    elif key==glfw.KEY_LEFT and (action==glfw.PRESS or action==glfw.REPEAT):
       V.translation_update(-winx/4/V.zoom_param,0)
    elif key==glfw.KEY_DOWN and (action==glfw.PRESS or action==glfw.REPEAT):
       V.translation_update(0,winy/4/V.zoom_param)

    #contrast change
    if key==glfw.KEY_E and (action==glfw.PRESS or action==glfw.REPEAT):
       V.radius_update(1)
    if key==glfw.KEY_D and (action==glfw.PRESS or action==glfw.REPEAT):
       V.radius_update(-1)
    if key==glfw.KEY_C and action==glfw.PRESS:
       V.reset_scale_bias()
       if V.shift_is_pressed:
         V.TOGGLE_AUTOMATIC_RANGE = (V.TOGGLE_AUTOMATIC_RANGE + 1) % 2
         if V.TOGGLE_AUTOMATIC_RANGE: 
            print("automatic range enabled")
         else: 
            print("automatic range disabled")
         

    if key==glfw.KEY_B and (action==glfw.PRESS or action==glfw.REPEAT): 
       V.reset_range_to_8bits()
       V.TOGGLE_AUTOMATIC_RANGE = 0
       print("range set to [0,255]")


    # (SAVE) write current buffer
    if key==glfw.KEY_S and (action==glfw.PRESS or action==glfw.REPEAT): 
       import piio
       from os import path

       # determine display scale
       fb_width,fb_height = glfw.get_framebuffer_size(window)
       display_scale = int(fb_width / V.winx)

       w,h=V.winx*display_scale,V.winy*display_scale
       glReadBuffer( GL_FRONT );
       data = glReadPixels (0,0,w,h, GL_RGB,  GL_UNSIGNED_BYTE)
       n=0       # determine next snapshot
       while path.exists('snap%02d.png'%n):
          n = n+1
       print('Saving ' + 'snap%02d.png'%n)
       # write the buffer
       piio.write_buffer_uint8('snap%02d.png'%n, data,w,h,3)

       # no need of numpy for the conversion
       #import numpy as np
       #iimage = np.fromstring(data, dtype=np.uint8, count=w*h*3).reshape((h,w,3))
       #piio.write('snap%02d.png'%n, iimage[::-1,:,0:3])

       ### from http://nullege.com/codes/show/src@g@l@glumpy-0.2.1@glumpy@figure.py/313/OpenGL.GL.glReadPixels
       #from PIL import Image
       #image = Image.fromstring('RGBA', (w,h), data)
       #image = image.transpose(Image.FLIP_TOP_BOTTOM)
       #image.save ('save.png')


    # zoom
    if key==glfw.KEY_P and (action==glfw.PRESS or action==glfw.REPEAT):
       V.zoom_update(+1)
    if key==glfw.KEY_M and (action==glfw.PRESS or action==glfw.REPEAT):
       V.zoom_update(-1)

    # fit image to window
    if key==glfw.KEY_F and action==glfw.PRESS:
       V.TOGGLE_FIT_TO_WINDOW_SIZE = (V.TOGGLE_FIT_TO_WINDOW_SIZE + 1) % 2
       if V.TOGGLE_FIT_TO_WINDOW_SIZE:
          print("ENABLE: fit image to window")
          V.update_zoom_position_to_fit_window()
          V.redisp = 1 
       else:
          print("DISABLE: fit image to window")
          #V.reset_zoom()
          V.redisp = 1 


    # reset visualization
    if key==glfw.KEY_R and action==glfw.PRESS:
       V.reset_zoom()
       V.reset_scale_bias()

    # reset visualization
    if key==glfw.KEY_1 and action==glfw.PRESS:
       V.TOGGLE_FLOW_COLORS = (V.TOGGLE_FLOW_COLORS + 1) % 6
       V.redisp = 1



    # modifier keys
    if key==glfw.KEY_LEFT_SHIFT and action==glfw.PRESS:
       V.shift_is_pressed=1
    if key==glfw.KEY_LEFT_SHIFT and action==glfw.RELEASE:
       V.shift_is_pressed=0
    if key==glfw.KEY_Z   and action==glfw.PRESS:
       V.alt_is_pressed=1
    if key==glfw.KEY_Z   and action==glfw.RELEASE:
       V.alt_is_pressed=0


    # CHANGE IMAGE TODO: use DataBackend DD
    global current_image_idx
    new_current_image_idx = current_image_idx
    if key==glfw.KEY_SPACE and (action==glfw.PRESS or action==glfw.REPEAT):
       new_current_image_idx = change_image(current_image_idx+1)
       if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
       V.mute_keyboard=1

    if key==glfw.KEY_BACKSPACE and (action==glfw.PRESS or action==glfw.REPEAT):
       new_current_image_idx = change_image(current_image_idx-1)
       if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
       V.mute_keyboard=1

    if key==glfw.KEY_MINUS and (action==glfw.PRESS or action==glfw.REPEAT):
       if remove_current_image():
          new_current_image_idx = change_image(current_image_idx)
          current_image_idx = -1  #FIXME forced refresh: image index hasn't changed by the image has
          if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
          V.mute_keyboard=1

    if not new_current_image_idx == current_image_idx:
       current_image_idx = new_current_image_idx
       V.redisp=1
       V.resize=1

    # display hud
    if key==glfw.KEY_U   and action==glfw.PRESS:
       V.display_hud=(V.display_hud+1)%2
       V.redisp=1

    # help
    if key==glfw.KEY_H   and action==glfw.PRESS:
       global HELPstr
       HELPstr="==============HELP==============\n" + \
               "Q     : quit\n" + \
               "U     : show/hide HUD\n" + \
               "arrows: pan image\n" + \
               "P,M   : zoom image in/out\n" + \
               "F     : fit image to window size\n" + \
               "C     : reset intensity range\n" + \
               "shiftC: automatically reset range\n" + \
               "B     : set range to [0:255]\n" + \
               "D,E   : range scale up/down\n" + \
               "R     : reset visualization: zoom,pan,range\n" + \
               "1     : cycle palette: optic flow,jet,negative...\n" + \
               "S     : capture a snap##.png of current window\n" + \
               "-     : remove current file from view list\n" + \
               "Z     : zoom modifier for the mouse wheel\n" + \
               "L     : show view list\n" + \
               "H     : this help message\n" + \
               "mouse wheel: contrast center\n" + \
               "mouse wheel+shift : contrast scale\n" + \
               "mouse motion+shift: contrast center\n" + \
               "space/backspace   : next/prev image\n" + \
               "drag&drop files   : add to view list\n" + \
               "================================\n"
       print(HELPstr)
       V.redisp=1

    # help
    if key==glfw.KEY_L   and action==glfw.PRESS:
       HELPstr="==============FILES=============\n" 
       for s in range(1,len(sys.argv)):
          if s == current_image_idx+1:
             HELPstr = HELPstr + ">   %s\n"%sys.argv[s]
          else:
             HELPstr = HELPstr + "    %s\n"%sys.argv[s]
       V.redisp=1

    # exit
    if (key==glfw.KEY_Q  or key==glfw.KEY_ESCAPE ) and action ==glfw.PRESS:
       glfw.set_window_should_close(window,1)
       global x0,y0,w0,h0
       print(x0,y0,w0,h0)

    if V.redisp == 1:
       # Call the mouseMotion callback in order to update the display info
       mouseMotion_callback(window, V.mx, V.my)




def resize_callback(window, width, height):
   global V
   glViewport(0, 0, width, height)
   V.winx,V.winy=width,height
   V.redisp=1
   # this callback is generated weather the application or the user has resized the window 
   # we set the variable either way because if it was the application we can detect it later
   V.window_has_been_resized_by_the_user = 1


def unicode_char_callback(window, codepoint):
   pass
   #print codepoint




def drop_callback(window, filenames):
    global V
    global current_image_idx

    insert_images(filenames)

    # change the image and refresh
    new_current_image_idx = current_image_idx
    new_current_image_idx = change_image(current_image_idx+1)
    if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
    V.mute_keyboard=1

    if not new_current_image_idx == current_image_idx:
       current_image_idx = new_current_image_idx
       V.redisp=1
       V.resize=1

    # regain focus after drop
    glfw.focus_window(window);



def display( window ):
    """Render scene geometry"""

    global D,V

    glClear(GL_COLOR_BUFFER_BIT);

#    glDisable( GL_LIGHTING) # context lights by default

    # this is the effective size of the current window
    # ideally winx,winy should be equal to D.w,D.h BUT if the 
    # image is larger than the screen glutReshapeWindow(D.w,D.h) 
    # will fail and winx,winy will be truncated to the size of the screen
#    winx, winy= glfw.get_framebuffer_size(window)
    winx, winy= glfw.get_window_size(window)
    V.winx,V.winy=winx,winy


    # Query the native frame buffer resolution to honor HDPI monitors
    # https://github.com/adrianbroher/freetype-gl/commit/c8474a9f1723e013219ab871d6f40cf86159fe87
    fb_width,fb_height = glfw.get_framebuffer_size(window)
    
    # minimized window in windows 10 has size 0
    if (fb_width,fb_height, winx, winy) == (0,0,0,0):
       return
    display_scale = fb_width / winx
    #print(display_scale)


    glViewport(0, 0, int(winx*display_scale), int(winy*display_scale));

    # setup camera
    glMatrixMode (GL_PROJECTION);
    glLoadIdentity ();
    glOrtho (0, winx, winy, 0, -1, 1);


    def drawImage(textureID,w,h,x0=0,y0=0):
       glPushMatrix()
       glEnable (GL_TEXTURE_2D); #/* enable texture mapping */
       glBindTexture (GL_TEXTURE_2D, textureID); #/* bind to our texture, has id of 13 */
   
       # third operation
       glScalef(V.zoom_param, V.zoom_param,1)

       # second operation
       glTranslate(-V.dx,-V.dy,0)
       # second operation
       glTranslate(V.dragdx,V.dragdy,0)

       # first operation
       glBegin( GL_QUADS );
       glColor3f(1.0, 0.0, 0.0);
       glTexCoord2d(0.0,1.0); glVertex3d(x0  ,y0+h ,0);
       glTexCoord2d(1.0,1.0); glVertex3d(x0+w,y0+h ,0);
       glTexCoord2d(1.0,0.0); glVertex3d(x0+w,y0   ,0);
       glTexCoord2d(0.0,0.0); glVertex3d(x0  ,y0   ,0);
       glEnd();
   
       glDisable (GL_TEXTURE_2D); #/* disable texture mapping */
       glPopMatrix()


    def drawHud(str,color=(0,1,0),pos=(8,13)):
       #import OpenGL.GLUT as glut
       #  A pointer to a font style..
       #  Fonts supported by GLUT are: GLUT_BITMAP_8_BY_13,
       #  GLUT_BITMAP_9_BY_15, GLUT_BITMAP_TIMES_ROMAN_10,
       #  GLUT_BITMAP_TIMES_ROMAN_24, GLUT_BITMAP_HELVETICA_10,
       #  GLUT_BITMAP_HELVETICA_12, and GLUT_BITMAP_HELVETICA_18.
       font_style = glut.GLUT_BITMAP_8_BY_13
       if display_scale>1:                  # RETINA
          font_style = glut.GLUT_BITMAP_HELVETICA_18
       glColor3f(color[0], color[1], color[2]);
       line=0;
       glRasterPos3f (pos[0], pos[1]+13*line,.5)
       for i in str:
          if  i=='\n':
             line=line+1
             glRasterPos3f (pos[0], pos[1]+13*line,.5)
          else:
             glut.glutBitmapCharacter(font_style, ord(i))
    
    
    ## USE THE SHADER FOR RENDERING THE IMAGE
    if D.nch == 2 :
       V.TOGGLE_FLOW_COLORS = V.TOGGLE_FLOW_COLORS % 2
       if V.TOGGLE_FLOW_COLORS == 1:
          use_shader_program('oflow')
       else:
          use_shader_program('rb')
    elif D.nch == 1:
       if V.TOGGLE_FLOW_COLORS == 1:
          V.inv_param=0
          use_shader_program('djet')
       elif V.TOGGLE_FLOW_COLORS == 2:
          V.inv_param=0
          use_shader_program('dhsv')
       elif V.TOGGLE_FLOW_COLORS == 3:
          V.inv_param=1
          use_shader_program('djet')
       elif V.TOGGLE_FLOW_COLORS == 4:
          V.inv_param=1
          use_shader_program('rgba')
       elif V.TOGGLE_FLOW_COLORS == 5:
          V.inv_param=0
          use_shader_program('bayer')
       else:
          V.inv_param=0
          use_shader_program('rgba')
    else:
       V.TOGGLE_FLOW_COLORS = V.TOGGLE_FLOW_COLORS % 4
       if V.TOGGLE_FLOW_COLORS == 1:
          V.inv_param=0
          use_shader_program('hsv')
       elif V.TOGGLE_FLOW_COLORS == 2:
          V.inv_param=1
          use_shader_program('rgba')
       elif V.TOGGLE_FLOW_COLORS == 3:
          V.inv_param=0
          use_shader_program('rgb')
       else:
          V.inv_param=0
          use_shader_program('rgba')

    global program
    # set the values of the shader uniform variables (global)
    shader_a= glGetUniformLocation(program, b"shader_a")
    glUniform1f(shader_a,V.scale_param)
    shader_b= glGetUniformLocation(program, b"shader_b")
    glUniform1f(shader_b,V.bias_param)
    shader_c= glGetUniformLocation(program, b"shader_c")
    glUniform1i(shader_c,V.inv_param)

    shader_B0 = glGetUniformLocation(program, b"shader_B0")
    glUniform1f(shader_B0, V.bias_vector[0])
    shader_B1 = glGetUniformLocation(program, b"shader_B1")
    glUniform1f(shader_B1, V.bias_vector[1])
    shader_B2 = glGetUniformLocation(program, b"shader_B2")
    glUniform1f(shader_B2, V.bias_vector[2])

    # DRAW THE IMAGE
    textureID=13
    for tile in D.imageBitmapTiles:
       _tilesz= glGetUniformLocation(program, b"_tilesz")
       glUniform2f(_tilesz, tile[3], tile[4]);
       drawImage(textureID,tile[3],tile[4],tile[1],tile[2])
       textureID=textureID+1


    # DONT USE THE SHADER FOR RENDERING THE HUD
    glUseProgram(0)   

    if V.display_hud:
       a=D.v_max-D.v_min
       b=D.v_min
       drawHud('%s\n%s\n%s\n%.3f %.3f\n%.3f %.3f'%(D.filename, V.txt_pos,V.txt_val,V.v_center,V.v_radius,D.v_min,D.v_max))

    global HELPstr
    if HELPstr != "":
       drawHud(HELPstr, (0,1,0), (10, 80))
       HELPstr=""


    # show RECTANGULAR region
    global x0,y0,w0,h0,b0state,b1state
    if(b1state=='pressed'):

       # real image coordinates
       xx0,yy0,xx1,yy1 = int(x0),int(y0),int(x0+w0),int(y0+h0)

       # compose transformation
       glPushMatrix()
       # first transformation
       glScalef(V.zoom_param, V.zoom_param,1)
       # second transformation
       glTranslate(-V.dx,-V.dy,0)

       # draw
       glEnable (GL_BLEND)
       glBlendFunc (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

       glBegin( GL_QUADS );
       glColor4f(1.0, 0.0, 0.0,.6);
       glVertex3d(xx0  ,yy0   ,-0.1);
       glColor4f(0.0, 1.0, 1.0,.3);
       glVertex3d(xx1,yy0   ,-0.1);
       glColor4f(0.0, 0.0, 1.0,.6);
       glVertex3d(xx1,yy1,-0.1);
       glColor4f(0.0, 1.0, 0.0,.3);
       glVertex3d(xx0  ,yy1,-0.1);
       glEnd();

       glDisable (GL_BLEND)

       glPopMatrix()

    return 0



def setupTexture(imageBitmap, ix,iy,nch, textureID=13):
    """texture environment setup"""
    glBindTexture(GL_TEXTURE_2D, textureID)
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
#    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
#    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_DECAL)

    # THE INTERNAL FORMAT GL_RGB32F ALLOWS TO PERFORM THE CONTRAST CHANGE ON THE FRAGMENT SHADER WITHOUT PRECISION LOSS
    # https://www.opengl.org/discussion_boards/showthread.php/170053-Shader-floating-point-precision
    # https://www.opengl.org/sdk/docs/man/xhtml/glTexImage2D.xml
    if nch==1:
       glTexImage2D( GL_TEXTURE_2D, 0, GL_RGB32F, ix, iy, 0,
         GL_LUMINANCE, GL_FLOAT, imageBitmap)
    elif nch==2:
       glTexImage2D( GL_TEXTURE_2D, 0, GL_RGBA32F, ix, iy, 0,
         GL_LUMINANCE_ALPHA, GL_FLOAT, imageBitmap)
    elif nch==4:
       glTexImage2D( GL_TEXTURE_2D, 0, GL_RGBA32F, ix, iy, 0,
         GL_RGBA, GL_FLOAT, imageBitmap)
    else:
       glTexImage2D( GL_TEXTURE_2D, 0, GL_RGB32F, ix, iy, 0,
         GL_RGB, GL_FLOAT, imageBitmap)



def setupTexturesFromImageTiles(imageBitmapTiles, ix,iy,nch, textureID=13):
    """texture environment setup"""
    for tile in imageBitmapTiles:
       setupTexture(tile[0], tile[3],tile[4],tile[5], textureID)
       textureID=textureID+1






##### TIC TOC 
time_start=0
def tic():
    import time
    global time_start
    time_start = time.time()

def toc(name=''):
    import time
    global time_start
    elapsed = time.time() - time_start
    if name=='':
       print('%f s'%(elapsed))
    else:
       print('%s: %f s'%(name, elapsed))
##### TIC TOC 








##### MAIN PROGRAM AND LOOP

def main():

    # verify input
    if len(sys.argv) == 1:
       # check if the standard input is a tty (not a pipe)
       if sys.stdin.isatty():
          print("Incorrect syntax, use:")
          print('  > ' + sys.argv[0] + " image.png")

          # show a default image if exists
          sys.argv.append('/Users/facciolo/uiskentuie_standing_stone.png')
          try:
             from os import stat
             stat(sys.argv[1])
          except OSError:
             sys.exit(1)
       # otherwise use stdin as input (because it should be a pipe)
       else:
          sys.argv.append('-')

    # pick the first image
    I1 = sys.argv[1]


    # globals
    global D,V,DD,current_image_idx


    tic()
    # Initialize the library
    if not glfw.init():
        sys.exit(1)

    # Create a windowed mode window (hidden) and its OpenGL context
    glfw.window_hint(glfw.FOCUSED,  GL_TRUE);
    glfw.window_hint(glfw.DECORATED,  GL_TRUE);
    glfw.window_hint(glfw.VISIBLE,  GL_FALSE);
    window = glfw.create_window(100, 100, "Vflip! (reloaded)", None, None)

    if not window:
        glfw.terminate()
        sys.exit(1)

    # Make the window's context current
    glfw.make_context_current(window)

    # event handlers
    glfw.set_key_callback(window, keyboard_callback)
    glfw.set_mouse_button_callback(window, mouseButtons_callback)
    glfw.set_scroll_callback(window, mouseWheel_callback)
    glfw.set_cursor_pos_callback(window, mouseMotion_callback)
    glfw.set_drop_callback(window, drop_callback)
    glfw.set_framebuffer_size_callback(window, resize_callback)
    glfw.set_window_refresh_callback(window,display)
#    glfw.set_char_callback (window, unicode_char_callback)

    if not glut.INITIALIZED:
        glut.glutInit([])

    toc('glfw init')
    tic()

    # read the image: this affects the global variables DD, D, and V
    current_image_idx = change_image(0)
    V.reset_scale_bias()

    # resize the window 
    glfw.set_window_size(window, D.w,D.h)

    # the maximum window size is limited to the monitor size
    monsz = glfw.get_video_mode(glfw.get_primary_monitor())[0];
    if(D.w > monsz[0] or D.h > monsz[1]):
        V.winx, V.winy = min(D.w, monsz[0]), min(D.h, monsz[1])
        glfw.set_window_size(window,V.winx,V.winy)

    # reset this variable to 0
    V.window_has_been_resized_by_the_user=0

    # show the window
    glfw.show_window (window)

    # compile and load the shader
    use_shader_program('rgba')

    global program 
    # set the values of the shader uniform variables (global)
    shader_a= glGetUniformLocation(program, b"shader_a")
    glUniform1f(shader_a,V.scale_param)
    shader_b= glGetUniformLocation(program, b"shader_b")
    glUniform1f(shader_b,V.bias_param)
    shader_c= glGetUniformLocation(program, b"shader_c")
    glUniform1i(shader_c,V.inv_param)

#    # first display
#    display(window)
#    glFlush()

    toc('loadImage+data->RGBbitmap')


    # Loop until the user closes the window
    while not glfw.window_should_close(window):
        #glfw.set_window_should_close(window,1) # only used for profiling

        # Render here
        if V.redisp:
           # Try to resize the window if needed
           # this process the window resize requests generated by the application
           # the user window resize requests requests go directly to resize_callback
           if V.resize and not (D.w,D.h) == glfw.get_framebuffer_size(window) and not V.window_has_been_resized_by_the_user:
              # maximum window size is given by the primary monitor 
              monsz = glfw.get_video_mode(glfw.get_primary_monitor())[0];
              V.winx, V.winy = min(D.w, monsz[0]), min(D.h, monsz[1])
              #if((V.winx,V.winy) == monsz):     # may leave window decoration outside screen
              #   glfw.set_window_pos(window,0,0)

              # resize the window and check the resulting size (may be smaller)
              glfw.set_window_size(window,V.winx,V.winy)
              V.winx, V.winy= glfw.get_window_size(window)

              # I know it's not been the user so I reset the variable to 0
              V.window_has_been_resized_by_the_user=0
              V.resize = 0

           if V.TOGGLE_FIT_TO_WINDOW_SIZE: V.update_zoom_position_to_fit_window()

           V.redisp = display(window)

           # Swap front and back buffers
           glfw.swap_buffers(window)
           V.mute_wheel=0
           V.mute_sweep=0
           V.mute_keyboard=0


        # Poll for and process events
        #glfw.poll_events()
        glfw.wait_events()

    glfw.terminate()


if __name__ == '__main__': main()

