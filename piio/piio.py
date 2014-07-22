# Primitie python wrapper for iio
# Copyright 2013, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>


import os,sys,ctypes

#if sys.platform.startswith('win'):
#   lib_ext = '.dll'
#elif sys.platform == 'darwin':
#   lib_ext = '.dylib'
#else:
#   lib_ext = '.so'
#gcc -std=c99 iio.c -shared -o iio.dylib -lpng -ltiff -ljpeg


lib_ext = '.so'
here  = os.path.dirname(__file__)

if sys.platform.startswith('win'): 
   lib_ext = '.dll'
   if sys.platform == 'win64':   #precompiled windows
      lib_basename = 'WIN64/iio'
   else:      
      lib_basename = 'WIN32/iio'
else:      # linux and osx
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
         tiles.append( (data, x, y, ww,hh, out_nch) ) 
         

   # free the memory
   libiio.freemem(ptr)

   return (tiles,w,h,out_nch,vmin,vmax)


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
