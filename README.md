# Running the program. No need for system-wise installation:

    > v.py image_file

Note: It will compile the pyglfw and piio modules during the first execution, 
leaving the libraries in the directory of v.py. This works only on OSX and Linux 
when the [dependecies are met](#dependencies).

## On Windows: 

The installation on windows is [laborious](#windows-dependencies).

Luckily precompiled and standalone binaries of pvflip are available for [win32](https://github.com/gfacciol/pvflip/releases/download/v0.4/pvflip_win32.zip) and [mac64](https://github.com/gfacciol/pvflip/releases/download/v0.4/pvflip_mac64.zip)

Just unzip and launch the file **v.exe**, or **v**.


# Dependencies

### OSX dependencies (known)
    PyGL or PyOpenGL (pip install PyGL)
    A working C compiler (XCode)
    libtiff libjpeg libpng for piio


### Linux dependencies (known)
    x11proto-xf86vidmode-dev
    xorg-dev libglu1-mesa-dev
    python-opengl cmake 
    A working C compiler
    libtiff-dev libjpeg-dev libpng-dev for piio


### Windows dependencies
    Statically linked win32 dll's for GLFW and IIO are provided, 
    so there's no need to compile them under windows. Yet to run pvflip 
    the following dependencies must be met.
    * python 2.7 from https://www.python.org/downloads/
    * pip from https://pip.pypa.io/en/latest/installing.html
          run: C:\Python23\python.exe get-pip.py
    * pyopengl
          run: C:\Python27\Scripts>pip.exe pyopengl
    * GLUT32 must be installed. Make sure that the file glut32.dll 
      is in windows\system*\, otherwise download it from: 
      http://user.xmission.com/~nate/glut.html

### Optional dependency (only for accessing some piio functionalities)
    numpy > 1.5
    
    

# Optional system-wide installation

    > python setup.py install 

this compiles and installs the following python modules: pyglfw3, piio

### Local Installation 

    > python setup.py install  --prefix=$HOME/local

For the intallations remember to set:

    export PYTHONPATH=$PYTHONPATH:$HOME/local/lib/pythonXXX/site-packages

