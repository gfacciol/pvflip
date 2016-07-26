PIIO is an iio (https://github.com/mnhrdt/iio/) wrapper that allows to 
read and write a wide variety of image formats directly from numpy arrays.

  # Let's read a JPEG image
> import piio
> x = piio.read('picture.jpg')

  # x is a float-valued numpy array of dimensions: (Height, Width, Channels)
  # we can manipulate it at will and write the result with piio 
  # piio supports JPG, PNG, and TIF 
> z = 255 - x
> piio.write('testnegat.png', z)

  # piio can also store and retrieve floating point pixels from TIF files
  # To look at these float-valued TIF images you may need to use a 
  # special viewer:  https://github.com/gfacciol/pvflip
> x = (x - 127.0) / 10.0
> piio.write('testfloat.tif', x)


# Compilation installation 

The key for piio is to have library file in piio/libiio.so.

At import time piio checks if one of the following libraries is available: 
    * A precompiled library in WIN32 or MAC64 (depending on the platform)
    * A file piio/libiio.so
If none is found, piio.py automatically attempts to build libiio.so by calling 
    > python setup.py build 
which would create piio/libiio.so. This allows (in most cases) to use piio as 
a module without worrying about a system installation.

The distutil setup scripts have limited capailities when it comes to detecting 
the system libraries. A library with more functionalities (ie OpenEXR) can be 
built using the CMakeList.txt located in the piio directory:
    > cmake .; make

The above scripts are only tested to Unix systems. For Windows installations a
only the precompiled WIN32 library is available.


# Dependencies

The following libraries are assumed to be present on the system:
    * libpng-dev
    * libtiff-dev
    * libjpeg-dev
    * libraw-dev (optional)
    * OpenEXR-dev (optional)

# Known issues

* If the compiler complains about "declarations that are only allowed in C99 mode" then use the following call to force the c99 dialect

    CC='gcc -std=c99' python setup.py build
