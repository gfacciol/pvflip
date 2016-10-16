# pvflip an OpenGL accelerated image viewer

## Features:
   * Smoothly inspect and zoom high dynamic range images with a simple interface using the mouse and modifier keys
   * Can visualize a large collection of image formats and bit depths (integer and float): PNG, PNM, JPG, TIFF, EXR, camera RAW, VRT, and other more obscure formats like PFM, FLO and MW
   * Drag-and-drop on a running instance to add files to the current view list and remove with (-)
   * Support for retina displays
   * Take snapshots of the current window content
   * [Precompiled binaries for Windows and MAC](https://github.com/gfacciol/pvflip/releases/tag/v0.6)

# Running the program: No need for installation

If the [dependencies are met](#dependencies) just run

    > ./v.py image_file image_file2 ...

**Note**: On Linux and MAC platforms the program will compile the glfw and piio modules during its first execution, 
leaving the libraries in the corresponding subdirectories.

**Note 2**: If the compiler complains about "declarations that are only allowed in C99 mode" then specify the dialect with 

    > CC='gcc -std=c99' ./v.py image_file

the environment variable is needed only for the first execution.

## On Windows: 

The compilation of glfw and piio on windows is not automatic and it can be [laborious](#windows-dependencies).
For this reason precompiled WIN32/64 DLLs of glfw (Release 3.2.1 from glfw.org) and iio are included in the distribution.
So with python (i.e. https://winpython.github.io/) and pyOpenGL it should work.

Alternatively use a precompiled version of pvflip.

## Precompiled pvflip:

[Standalone binaries of pvflip are available for:](https://github.com/gfacciol/pvflip/releases/tag/v0.6)

   * WIN32: exe program in a single file or with multiple files. 
   * WIN64: without openEXR support: single file or multiple files.
   * Mac OS X 64 (OSX >= 1.7): App that uses the system python.

Just unzip and launch the file **v.exe**, or **v**.




# Dependencies

### OSX dependencies (known)
    PyOpenGL (pip install PyOpenGL)
    A working C/C++ compiler envoronment, make, and cmake
    libtiff libjpeg libpng for piio (optionally: libRAW, OpenEXR)


### Linux dependencies (known)
    x11proto-xf86vidmode-dev
    xorg-dev libglu1-mesa-dev
    python-opengl cmake 
    A working C compiler
    libtiff-dev libjpeg-dev libpng-dev for piio


### Windows dependencies
    Statically linked win32 DLLs for GLFW and IIO are provided, 
    so there's no need to compile them under windows. Yet to run pvflip 
    the following dependencies must be met.
    * python >= 2.7 from https://www.python.org/downloads/
    * pip from https://pip.pypa.io/en/latest/installing.html
          run: C:\Python27\python.exe get-pip.py
    * pyopengl
          run: C:\Python27\Scripts>pip.exe pyopengl
    * GLUT32 must be installed. Make sure that the file glut32.dll 
      is in windows\system*\, otherwise download it from: 
      http://user.xmission.com/~nate/glut.html


### Optional dependency (only for accessing some piio functionalities)
    numpy > 1.5
    

<!---

# Optional installation

    > python setup.py install 

this compiles and installs the following python modules: pyglfw3, piio

### Local Installation 

    > python setup.py install  --prefix=$HOME/local

For the intallations remember to set:

    export PYTHONPATH=$PYTHONPATH:$HOME/local/lib/pythonXXX/site-packages
-->
