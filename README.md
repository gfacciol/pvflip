# Running the program, no need for system-wise installation:

    > v.py image_file

Note: It will compile the pyglfw and piio modules during the first execution, 
leaving the libraries in the directory of v.py.


# Installation (optional)

    > python setup.py install 

compiles and installs the following python modules: pyglfw3, piio

# Local Installation (optional) 

    > python setup.py install  --prefix=$HOME/local

For the intallations remember to set:

    export PYTHONPATH=$PYTHONPATH:$HOME/local/lib/pythonXXX/site-packages


# OSX dependencies (known):
    PyGL (pip install PyGL)



# Linux dependencies (known):
    x11proto-xf86vidmode-dev
    xorg-dev libglu1-mesa-dev
    python-opengl cmake 

# Windows dependencies: 
    Statically linked win32 dll's for GLFW and IIO are provided, 
    so there's no need to compile under windows. Yet to run pvflip 
    the following dependencies must be met.
    * python 2.7 from https://www.python.org/downloads/
    * pip from https://pip.pypa.io/en/latest/installing.html
          run: C:\Python23\python.exe get-pip.py
    * pyopengl
          run: C:\Python27\Scripts>pip.exe pyopengl
    * GLUT32 must be installed. Make sure that the file glut32.dll 
      is in windows\system*\, otherwise download it from: 
      http://user.xmission.com/~nate/glut.html

# Optional dependency (only for some piio functions):
    numpy > 1.5
