#!/usr/bin/env python
# Copyright 2013, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
############################################################################
#
# 04/2015: use os.stat to detect changes file changes
# v03 : faster image load with piio.read_buffer avoids passing trough numpy
#       fragment shader color manipulation (optic flow)
# v02 : use fragment shader for the contrast change, uses GL_RGBF32 as internal format
#       improved image_data_to_RGBbitmap (more efficient)
# v01 : mutex wheel events, translation with mouse drag
# v00 : stable but no translation with mouse drag
# v-1 : no event mutex

from OpenGL.GL import *
from OpenGL.GL.shaders import *
import glfw
import sys

### SYSTEM SPECIFIC STUFF
import platform
if platform.system() == 'Darwin':
   GLOBAL_WHEEL_SCALING = 0.1
else:
   GLOBAL_WHEEL_SCALING = 1.0


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

rgba_shader = """
   uniform sampler2D src;
   uniform float shader_a;
   uniform float shader_b;

   void main (void)
   {
      vec4 p = texture2D(src, gl_TexCoord[0].xy);
      gl_FragColor = clamp(p * shader_a + shader_b, 0.0, 1.0);
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

depth_shader = """
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

       gl_FragColor = p; //clamp(p * shader_a + shader_b, 0.0, 1.0);

  }
   """


#### INTERFACE STATE
class ViewportState:
   winx,winy=0,0
   zoom_param  = 1
   scale_param = 1.0      ## TODO internal variables should not be here
   bias_param  = 0

   v_center = 0.5
   v_radius = 0.5

   dx,dy=0,0
   dragdx,dragdy=0,0
   dragx0,dragy0=0,0

   # mouse state variables : NOT USED YET TODO 
   x0=0; y0=0; w0=0; h0=0; b0state=''; b1state=''

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
      V.redisp=1

   def radius_update(V, offset):
      d = V.v_radius*.1
      V.v_radius = max(V.v_radius + d*offset,0)
      V.update_scale_and_bias()

   def center_update(V, offset):
      d = V.v_radius*.1
      V.v_center = min(max(V.v_center + d*offset,V.data_min),V.data_max)
      V.update_scale_and_bias()

   def center_update_value(V, centerval):
      V.v_center = centerval
      V.update_scale_and_bias()
   
   def reset_scale_bias(V):
      V.v_center=(V.data_max+V.data_min)/2.0
      V.v_radius=(V.data_max-V.data_min)/2.0
      V.update_scale_and_bias()


   def reset_range_to_8bits(V): 
      V.v_center = 127.5
      V.v_radius = 127.5
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
   except SystemError:
      print('error reading the image')


def change_image(new_idx):
   '''updates D and DD: acts as a cache of the images'''
   global D,DD

   BUFF=10  # BUFFERED IMAGES
   NUM_FILES = (len(sys.argv)-1)
   new_idx = new_idx % NUM_FILES
   new_filename = sys.argv[new_idx+1]

   from os import stat 
   if new_idx in DD:
      if new_filename != '-' and DD[new_idx].mtime < stat(new_filename).st_mtime:
         print new_filename + ' has changed. Reloading...'
         DD.pop(new_idx)

   if new_idx not in DD:
      D = DD[new_idx] = ImageState()

      tic()
      # read the image
      D.filename = new_filename
      if new_filename != '-':
         D.mtime    = (stat(new_filename).st_mtime)
      D.imageBitmapTiles,D.w,D.h,D.nch,D.v_min,D.v_max = load_image(new_filename)
      V.data_min, V.data_max =  D.v_min,D.v_max 
      setupTexturesFromImageTiles(D.imageBitmapTiles,D.w,D.h,D.nch)
      toc('loadImage+data->RGBbitmap+texture setup')

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
       glfw.glfwSetWindowTitle(window, '%s:[%s]'%(V.txt_pos,V.txt_val))
    V.redisp = 1


#    title='p:%s,%s [+%s+%s %sx%s]' % (x+V.dx,y+V.dy,x0+V.dx,y0+V.dy,w0,h0)
#    glfw.glfwSetWindowTitle(window, title)



def mouseButtons_callback(window, button, action, mods):
    global V
    global x0,y0,w0,h0,b0state,b1state

    # select region
    if button==glfw.GLFW_MOUSE_BUTTON_RIGHT and action==glfw.GLFW_PRESS:
       x,y = glfw.glfwGetCursorPos (window)
       x0,y0 = V.compute_image_coordinates(x,y)
       w0,h0=0,0
       b1state='pressed'
       V.redisp=1
    elif button==glfw.GLFW_MOUSE_BUTTON_RIGHT and action==glfw.GLFW_RELEASE:
       x,y = glfw.glfwGetCursorPos (window)
       curr_x,curr_y = V.compute_image_coordinates(x,y)
#       print curr_x, curr_y
       w0,h0 = int(curr_x)-int(x0),int(curr_y)-int(y0)
       b1state='released'
       xx0,yy0 = x0,y0
       xx1,yy1 = x0+w0,y0+h0
       xx0,yy0,xx1,yy1 = int(xx0),int(yy0),int(xx1),int(yy1)
       print(xx0, yy0, abs(xx1-xx0), abs(yy1-yy0))
       V.redisp=1

    # drag
    if button==glfw.GLFW_MOUSE_BUTTON_LEFT and action==glfw.GLFW_PRESS:
       x,y = glfw.glfwGetCursorPos (window)
       V.dragx0,V.dragy0 = V.compute_image_coordinates(x,y)
       V.dragdx,V.dragdy=0,0
       b0state='pressed'
       V.redisp=1
    elif button==glfw.GLFW_MOUSE_BUTTON_LEFT and action==glfw.GLFW_RELEASE:
       x,y = glfw.glfwGetCursorPos (window)
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

      curr_x,curr_y = glfw.glfwGetCursorPos (window)

      # zoom
      if V.alt_is_pressed:
         V.zoom_update(yoffset*GLOBAL_WHEEL_SCALING,curr_x,curr_y)
      # scale
      elif V.shift_is_pressed:
         V.radius_update(yoffset*GLOBAL_WHEEL_SCALING)
      # bias
      else: # nothing pressed
         V.center_update(yoffset*GLOBAL_WHEEL_SCALING)




# letters and numbers
def keyboard_callback(window, key, scancode, action, mods):
    global V,D

    if V.mute_keyboard: # only mute the spacebar event
       return

    #print key

    # navigate
    winx, winy= glfw.glfwGetFramebufferSize(window)
    if key==glfw.GLFW_KEY_RIGHT and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.translation_update(winx/4/V.zoom_param,0)
    elif key==glfw.GLFW_KEY_UP and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.translation_update(0,-winy/4/V.zoom_param)
    elif key==glfw.GLFW_KEY_LEFT and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.translation_update(-winx/4/V.zoom_param,0)
    elif key==glfw.GLFW_KEY_DOWN and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.translation_update(0,winy/4/V.zoom_param)

    #contrast change
    if key==glfw.GLFW_KEY_E and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.radius_update(1)
    if key==glfw.GLFW_KEY_D and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.radius_update(-1)
    if key==glfw.GLFW_KEY_C and action==glfw.GLFW_PRESS:
       V.reset_scale_bias()
       if V.shift_is_pressed:
         V.TOGGLE_AUTOMATIC_RANGE = (V.TOGGLE_AUTOMATIC_RANGE + 1) % 2
         if V.TOGGLE_AUTOMATIC_RANGE: 
            print("automatic range enabled")
         else: 
            print("automatic range disabled")
         

    if key==glfw.GLFW_KEY_B and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT): 
       V.reset_range_to_8bits()
       V.TOGGLE_AUTOMATIC_RANGE = 0
       print("range set to [0,255]")



    # zoom
    if key==glfw.GLFW_KEY_P and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.zoom_update(+1)
    if key==glfw.GLFW_KEY_M and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       V.zoom_update(-1)

    # fit image to window
    if key==glfw.GLFW_KEY_F and action==glfw.GLFW_PRESS:
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
    if key==glfw.GLFW_KEY_R and action==glfw.GLFW_PRESS:
       V.reset_zoom()
       V.reset_scale_bias()

    # reset visualization
    if key==glfw.GLFW_KEY_1 and action==glfw.GLFW_PRESS:
       V.TOGGLE_FLOW_COLORS = (V.TOGGLE_FLOW_COLORS + 1) % 2
       V.redisp = 1



    # modifier keys
    if key==glfw.GLFW_KEY_LEFT_SHIFT and action==glfw.GLFW_PRESS:
       V.shift_is_pressed=1
    if key==glfw.GLFW_KEY_LEFT_SHIFT and action==glfw.GLFW_RELEASE:
       V.shift_is_pressed=0
    if key==glfw.GLFW_KEY_Z   and action==glfw.GLFW_PRESS:
       V.alt_is_pressed=1
    if key==glfw.GLFW_KEY_Z   and action==glfw.GLFW_RELEASE:
       V.alt_is_pressed=0


    # CHANGE IMAGE TODO: use DataBackend DD
    global current_image_idx
    new_current_image_idx = current_image_idx
    if key==glfw.GLFW_KEY_SPACE and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       new_current_image_idx = change_image(current_image_idx+1)
       if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
       V.mute_keyboard=1

    if key==glfw.GLFW_KEY_BACKSPACE and (action==glfw.GLFW_PRESS or action==glfw.GLFW_REPEAT):
       new_current_image_idx = change_image(current_image_idx-1)
       if V.TOGGLE_AUTOMATIC_RANGE: V.reset_scale_bias()
       V.mute_keyboard=1

    if not new_current_image_idx == current_image_idx:
       current_image_idx = new_current_image_idx
       V.redisp=1
       V.resize=1

    # display hud
    if key==glfw.GLFW_KEY_U   and action==glfw.GLFW_PRESS:
       V.display_hud=(V.display_hud+1)%2
       V.redisp=1

    # help
    if key==glfw.GLFW_KEY_H   and action==glfw.GLFW_PRESS:
       print("Q     : quit")
       print("U     : show/hide HUD")
       print("arrows: pan image")
       print("P,M   : zoom image in/out")
       print("Z     : zoom modifier for the mouse wheel")
       print("F     : fit image to window size")
       print("C     : reset intensity range")
       print("shiftC: automatically reset range")
       print("B     : set range to [0:255]")
       print("D,E   : range scale up/down")
       print("R     : reset visualization: zoom,pan,range")
       print("1     : toggle optic flow coloring")
       print("mouse wheel: contrast center")
       print("mouse wheel+shift: contrast scale")
       print("mouse motion+shift: contrast center")
       print("space/backspace : next/prev image")

    # exit
    if (key==glfw.GLFW_KEY_Q  or key==glfw.GLFW_KEY_ESCAPE ) and action ==glfw.GLFW_PRESS:
       glfw.glfwSetWindowShouldClose(window,1)
       global x0,y0,w0,h0
       print(x0,y0,w0,h0)
       exit(0)






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





def display( window ):
    """Render scene geometry"""

    global D,V

    glClear(GL_COLOR_BUFFER_BIT);

#    glDisable( GL_LIGHTING) # context lights by default

    # this is the effective size of the current window
    # ideally winx,winy should be equal to D.w,D.h BUT if the 
    # image is larger than the screen glutReshapeWindow(D.w,D.h) 
    # will fail and winx,winy will be truncated to the size of the screen
#    winx, winy= glfw.glfwGetFramebufferSize(window)
    winx, winy= glfw.glfwGetWindowSize(window)
    V.winx,V.winy=winx,winy

    glViewport(0, 0, winx, winy);

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


    def drawHud(str,color=(0,1,0)):
       import OpenGL.GLUT as glut
       #  A pointer to a font style..
       #  Fonts supported by GLUT are: GLUT_BITMAP_8_BY_13,
       #  GLUT_BITMAP_9_BY_15, GLUT_BITMAP_TIMES_ROMAN_10,
       #  GLUT_BITMAP_TIMES_ROMAN_24, GLUT_BITMAP_HELVETICA_10,
       #  GLUT_BITMAP_HELVETICA_12, and GLUT_BITMAP_HELVETICA_18.
       font_style = glut.GLUT_BITMAP_8_BY_13;
       glColor3f(color[0], color[1], color[2]);
       line=0;
       glRasterPos3f (8, 13+13*line,.5)
       for i in str:
          if  i=='\n':
             line=line+1
             glRasterPos3f (8, 13+13*line,.5)
          else:
             glut.glutBitmapCharacter(font_style, ord(i))
    
    

    ## USE THE SHADER FOR RENDERING THE IMAGE
    global program, program_rgba, program_hsv, program_rb, program_oflow, program_depth
    if D.nch == 2 :
       if V.TOGGLE_FLOW_COLORS:
          program  = program_oflow
       else:
          program  = program_rb
    elif D.nch == 1:
       if V.TOGGLE_FLOW_COLORS:
          program  = program_depth
       else:
          program  = program_rgba
    else:
       if V.TOGGLE_FLOW_COLORS:
          program  = program_hsv
       else:
          program  = program_rgba

    glUseProgram(program)   
    # set the values of the shader uniform variables (global)
    shader_a= glGetUniformLocation(program, "shader_a")
    glUniform1f(shader_a,V.scale_param)
    shader_b= glGetUniformLocation(program, "shader_b")
    glUniform1f(shader_b,V.bias_param)

    # DRAW THE IMAGE
    textureID=13
    for tile in D.imageBitmapTiles:
       drawImage(textureID,tile[3],tile[4],tile[1],tile[2])
       textureID=textureID+1


    # DONT USE THE SHADER FOR RENDERING THE HUD
    glUseProgram(0)   

    if V.display_hud:
       a=D.v_max-D.v_min
       b=D.v_min
       drawHud('%s\n%s\n%s\n%.3f %.3f\n%.3f %.3f'%(D.filename, V.txt_pos,V.txt_val,V.v_center,V.v_radius,D.v_min,D.v_max))


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
             exit(1)
       # otherwise use stdin as input (because it should be a pipe)
       else:
          sys.argv.append('-')

    # pick the first image
    I1 = sys.argv[1]


    # globals
    global D,V,DD,current_image_idx


    tic()
    # read the image
    # Usually this is done with change_image, but this is a special case
    # as we must find out the image size before creating the window 
    D.imageBitmapTiles,D.w,D.h,D.nch,D.v_min,D.v_max = load_image(I1)
    D.filename = I1
    if I1 != '-':
      from os import stat
      D.mtime    = (stat(I1).st_mtime)
    V.data_min, V.data_max=  D.v_min,D.v_max 
    V.reset_scale_bias()
    toc('loadImage+data->RGBbitmap')

    
    ## image list
    current_image_idx = 0
    DD[current_image_idx] = D




    tic()
    # Initialize the library
    # for some reason glfwInit changes the current dir, so I change it back!
    from os import getcwd,chdir
    savepath = getcwd()
    if not glfw.glfwInit():
        exit()
    chdir(savepath)


    # TODO REMOVE : needed for the text
    import OpenGL.GLUT as glut
    glut.glutInit()


    # Create a windowed mode window and its OpenGL context
    window = glfw.glfwCreateWindow(D.w, D.h, "Vflip! (reloaded)", None, None)


    if not window:
        glfw.glfwTerminate()
        exit()

    # Make the window's context current
    glfw.glfwMakeContextCurrent(window)

    # event handlers
    glfw.glfwSetKeyCallback(window, keyboard_callback)
    glfw.glfwSetMouseButtonCallback(window, mouseButtons_callback)
    glfw.glfwSetScrollCallback(window, mouseWheel_callback)
    glfw.glfwSetCursorPosCallback(window, mouseMotion_callback)
    glfw.glfwSetFramebufferSizeCallback(window, resize_callback)
    glfw.glfwSetWindowRefreshCallback(window,display)
#    glfw.glfwSetCharCallback (window, unicode_char_callback)
    toc('glfw init')


    # setup texture 
    tic()
    setupTexturesFromImageTiles(D.imageBitmapTiles,D.w,D.h,D.nch)
    glFinish()  # Flush and wait
    toc('texture setup')

    print (0,D.filename, (D.w,D.h,D.nch), (D.v_min,D.v_max))



##########
######## SETUP FRAGMENT SHADER FOR CONTRAST CHANGE
##########
# http://www.cityinabottle.org/nodebox/shader/
# http://www.seethroughskin.com/blog/?p=771
# http://python-opengl-examples.blogspot.com.es/
# http://www.lighthouse3d.com/tutorials/glsl-core-tutorial/fragment-shader/

    global program, program_rgba, program_hsv, program_rb, program_oflow, program_depth
    program_rgba = compileProgram( 
          compileShader(rgba_shader, GL_FRAGMENT_SHADER),
         );
    program_hsv = compileProgram( 
          compileShader(hsv_shader, GL_FRAGMENT_SHADER),
         );
    program_oflow = compileProgram( 
          compileShader(oflow_shader, GL_FRAGMENT_SHADER),
         );
    program_rb = compileProgram( 
          compileShader(rb_shader, GL_FRAGMENT_SHADER),
         );
    program_depth = compileProgram( 
          compileShader(depth_shader, GL_FRAGMENT_SHADER),
         );
    
    glLinkProgram(program_rgba)
    glLinkProgram(program_hsv)
    glLinkProgram(program_oflow)
    glLinkProgram(program_rb)
    glLinkProgram(program_depth)

    program = program_rgba
    

    #global program
    # try to activate/enable shader program
    # handle errors wisely
    try:
       glUseProgram(program)   
    except OpenGL.error.GLError:
       print(glGetProgramInfoLog(program))
       raise
    # set the values of the shader uniform variables (global)
    shader_a= glGetUniformLocation(program, "shader_a")
    glUniform1f(shader_a,V.scale_param)
    shader_b= glGetUniformLocation(program, "shader_b")
    glUniform1f(shader_b,V.bias_param)




#    # first display
#    display(window)
##    glFlush()

    # Loop until the user closes the window
    while not glfw.glfwWindowShouldClose(window):

        # Render here
        if V.redisp:
           # Try to resize the window if needed
           # this process the window resize requests generated by the application
           # the user window resize requests requests go directly to resize_callback
           if V.resize and not (D.w,D.h) == glfw.glfwGetFramebufferSize(window) and not V.window_has_been_resized_by_the_user:
              glfw.glfwSetWindowSize(window,D.w,D.h)
              # I know it's not been the user so I reset the variable to 0
              V.window_has_been_resized_by_the_user=0
              V.resize = 0

           if V.TOGGLE_FIT_TO_WINDOW_SIZE: V.update_zoom_position_to_fit_window()

           V.redisp = display(window)

           # Swap front and back buffers
           glfw.glfwSwapBuffers(window)
           V.mute_wheel=0
           V.mute_sweep=0
           V.mute_keyboard=0


        # Poll for and process events
        #glfw.glfwPollEvents()
        glfw.glfwWaitEvents()

    glfw.glfwTerminate()


if __name__ == '__main__': main()

