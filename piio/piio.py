# Primitive python wrapper for iio
# Copyright 2013, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
#
# This file is part of pvflip.
# 
# Pvflip is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Pvflip is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with pvflip.  If not, see <http://www.gnu.org/licenses/>.


import os,sys,ctypes,platform

#if sys.platform.startswith('win'):
#   lib_ext = '.dll'
#gcc  -std=c99 -static-libgcc -shared -s iio.c freemem.c -I/usr/local/include -I/usr/include -o WIN32/iio.dll  /usr/local/lib/libpng.a /usr/local/lib/libjpeg.a  /usr/local/lib/libtiff.a /usr/local/lib/libz.a 
#elif sys.platform == 'darwin':
#   lib_ext = '.dylib'
#else:
#   lib_ext = '.so'
#gcc -std=c99 iio.c -shared -o iio.dylib -lpng -ltiff -ljpeg

lib_ext = '.so'
here  = os.path.dirname(__file__)

if sys.platform.startswith('win'): 
   lib_ext = '.dll'
   if platform.architecture()[0] == '64bit':   #precompiled windows
      lib_basename = 'WIN64/iio'
   else:      
      lib_basename = 'WIN32/iio'
elif sys.platform.startswith('darwin'): # precompiled osx intel 64 bits
   lib_basename = 'MAC64/libiio'
   lib_ext = '.so'
else:      # linux 
   lib_basename = 'libiio'
   lib_ext = '.so'

libiiofile= os.path.join(here, lib_basename+lib_ext)

### fallback if precompiled libraries are not usable
try:
   os.stat(libiiofile)
except OSError:
   lib_basename = 'libiio'
   lib_ext = '.so'
   libiiofile= os.path.join(here, lib_basename+lib_ext)

### HACK TO BUILD libiio ON THE FLY
try:
   os.stat(libiiofile)
except OSError:
   print 'BUILDING PIIO...'
   os.system('cd %s; python setup.py build'%here)

libiio   = ctypes.CDLL(libiiofile)
del libiiofile, here, lib_ext


def read(filename):
   '''
   IIO: numpyarray = read(filename)
   '''
   from numpy import ctypeslib
   from ctypes import c_int, c_float, c_void_p, POINTER, cast, byref

   iioread = libiio.iio_read_image_float_vec
   
   w=c_int()
   h=c_int()
   nch=c_int()
   
   iioread.restype = c_void_p  # it's like this
   tptr = iioread(str(filename),byref(w),byref(h),byref(nch))
   c_float_p = POINTER(c_float)       # define a new type of pointer
   ptr = cast(tptr, c_float_p)
   #print w,h,nch
   
   #nasty read data into array using buffer copy
   #http://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy
   #http://docs.scipy.org/doc/numpy/reference/generated/numpy.frombuffer.html
   
   # this numpy array uses the memory provided by the c library, which will be freed
   data_tmp = ctypeslib.as_array( ptr, (h.value,w.value,nch.value) )
   # so we copy it to the definitive array before the free
   data = data_tmp.copy()
   
   # free the memory
   iiofreemem = libiio.freemem
   iiofreemem(ptr)
   return data



def read_buffer(filename):
   '''
   IIO: float_buffer, w, h, nch = read_buffer(filename)
   '''
   from ctypes import c_int, c_float, c_void_p, POINTER, cast, byref, c_char, memmove, create_string_buffer, sizeof

   iioread = libiio.iio_read_image_float_vec
   
   w=c_int()
   h=c_int()
   nch=c_int()
   
   iioread.restype = c_void_p  # it's like this
   tptr = iioread(str(filename),byref(w),byref(h),byref(nch))
   c_float_p = POINTER(c_float)       # define a new type of pointer
   ptr = cast(tptr, c_float_p)
   #print w,h,nch
   
   #nasty read data into array using buffer copy
   #http://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy
   #http://docs.scipy.org/doc/numpy/reference/generated/numpy.frombuffer.html
   N = h.value*w.value*nch.value
#   data = create_string_buffer(N * sizeof(c_float))
   data = ctypes.ARRAY(ctypes.c_float, N)()
   memmove(data,ptr,N*sizeof(c_float))

   # free the memory
   libiio.freemem(ptr)

   return data, w.value, h.value, nch.value



def read_tiled_buffers(filename):
   '''
   IIO: float_buffer, w, h, nch = read_buffer(filename)
   '''
   from ctypes import c_int, c_float, c_void_p, POINTER, cast, byref, c_char, memmove, create_string_buffer, sizeof
   
   w=c_int()
   h=c_int()
   nch=c_int()
   
   libiio.iio_read_image_float_vec.restype = c_void_p  # it's like this
   tptr = libiio.iio_read_image_float_vec(str(filename),byref(w),byref(h),byref(nch))
   c_float_p = POINTER(c_float)       # define a new type of pointer
   ptr = cast(tptr, c_float_p)
   #print w,h,nch
   w,h,nch=w.value,h.value,nch.value
   
   # compute min and max of the data
   vmin=c_float()
   vmax=c_float()
   N = w*h*nch
   libiio.minmax.restype = c_void_p  # it's like this
   libiio.minmax.argtypes = [c_float_p,c_int,c_float_p,c_float_p]
   libiio.minmax(ptr,N,byref(vmin),byref(vmax))
   vmin,vmax=vmin.value,vmax.value

   tiles   = []
   out_nch = min(nch,4)
   if(nch != out_nch):
      print "piio_read: the input image have %d channels, only the first 4 are loaded\n"%nch
   # generate several buffers, one for each tile
   for y in range(0,h, 1024):
      for x in range(0,w, 1024):
         ww = min (w - x, 1024)
         hh = min (h - y, 1024)
         N=ww*hh*out_nch
         # generate the interlan memory to copy the tile
         data = ctypes.ARRAY(ctypes.c_float, N)()
         libiio.copy_tile(ptr, w, h, nch, data, x, y, ww, hh, out_nch)  # only allow up to 4 channels
         tiles.append( [data, x, y, ww,hh, out_nch, -1] )  # -1 (the last field is a placeholder for the textureID)
         

   # free the memory
   libiio.freemem(ptr)

   return (tiles,w,h,out_nch,vmin,vmax)


################### FANCY
from ctypes import c_int, c_float, c_void_p, POINTER, cast, byref, c_char, memmove, create_string_buffer, sizeof, c_char_p, Structure
class Fimage(Structure):
   _fields_ = [("w",  c_int),
               ("h",  c_int),
               ("pd", c_int),
               ("no", c_int),
               ("pad", c_char*200000)]


open_fimage = libiio.fancy_image_open
open_fimage.argtypes = [c_char_p, c_char_p]
open_fimage.restype = Fimage

get_tile_fimage = libiio.fancy_get_tile
get_tile_fimage.argtypes = [POINTER(Fimage), c_int, c_int, c_int, c_int, c_int, POINTER(c_float)]

close_fimage = libiio.fancy_image_close
close_fimage.argtypes = [POINTER(Fimage)]

class Fimage(object):

   def __init__(self, filename):
      self._fancy = open_fimage(str(filename), str("rw"))
      self.w   = self._fancy.w
      self.h   = self._fancy.h
      self.pd  = self._fancy.pd
      print "INIT %s (%d %d %d)"%(filename,self.w,self.h,self.pd)

      nch=self.pd
      TSZ = 512
      _tiles  = []*(int(self.h/TSZ+1)*int(self.w/TSZ+1)); 
#      _tiles = []
      self.out_nch = min(nch,4)
      if(nch != self.out_nch):
         print "fancy_piio_read: the input image have %d channels, only the first 4 are loaded\n"%nch
      # generate several buffers, one for each tile
      for y in range(0,self.h, TSZ):
         for x in range(0,self.w, TSZ):
            ww = min (self.w - x, TSZ)
            hh = min (self.h - y, TSZ)
            # generate the internal memory to copy the tile
            #N=ww*hh*self.out_nch
            #data = ctypes.ARRAY(ctypes.c_float, N)()
            #libiio.copy_tile(ptr, w, h, nch, data, x, y, ww, hh, out_nch)  # only allow up to 4 channels
            data = 0
            _tiles.append( [data, x, y, ww,hh, self.out_nch, -1] )  # -1 (the last field is a placeholder for the textureID)
      self.vmin=0
      self.vmax=255

      self.TILES = (_tiles,self.w,self.h,self.out_nch,self.vmin,self.vmax)


   def get_tile(self, tile): 
      N = tile[3]*tile[4]*tile[5]
      tile[0]= ctypes.ARRAY(ctypes.c_float, N)()
      get_tile_fimage(byref(self._fancy), tile[1], tile[2], tile[3], tile[4],tile[5],tile[0])
      return

   def size(self):
      return self.TILES

   def __del___(self):
      close_fimage(self._fancy)





################### END FANCY


def minmax(data):
   '''
   IIO: write(filename,numpyarray)
   '''
   from ctypes import c_int, c_float, POINTER, cast, byref, c_void_p

   c_float_p = POINTER(c_float)       # define a new type of pointer

   vmin=c_float()
   vmax=c_float()

   N = len(data)
   dataptr = cast(data,c_float_p)

   libiio.minmax.restype = c_void_p  # it's like this
   libiio.minmax.argtypes = [c_float_p,c_int,c_float_p,c_float_p]
   libiio.minmax(dataptr,N,byref(vmin),byref(vmax))
   return vmin.value, vmax.value



def buffer_to_numpy(data,w,h,nch):
   '''
   IIO: numpyarray = buffer_to_numpy(float_buffer,w,h,nch)
   '''
   import numpy 
   dataNP = numpy.frombuffer(data,numpy.float32)
   dataNP = dataNP.reshape((h.value,w.value,nch.value))
   return dataNP



def write(filename,data):
   '''
   IIO: write(filename,numpyarray)
   '''
   from ctypes import c_char_p, c_int, c_float
   from numpy.ctypeslib import ndpointer

   iiosave = libiio.iio_save_image_float_vec

   h  =data.shape[0]
   w  =data.shape[1]
   nch=1
   if (len(data.shape)>2):
      nch=data.shape[2]

   iiosave.restype = None
   iiosave.argtypes = [c_char_p, ndpointer(c_float),c_int,c_int,c_int]
   iiosave(str(filename), data.astype('float32'), w, h, nch)


#d = piio.read('testimg.tif')
#print d.shape
#print d[:,:,0] 
#piio.write('kk2.tif',d)
