# Installation

    > python setup.py install 


compiles and installs the following python modules: pyglfw3m, piio


# Execution
   > v.py image_file


# Local Installation

    > python setup.py install  --prefix=$HOME/local

Remember to set:

    export PYTHONPATH=$PYTHONPATH:$HOME/local/lib/python2.6/site-packages


# OSX dependency:
    numpy > 1.5
    PyGL (pip install PyGL)



# Linux dependency:
    x11proto-xf86vidmode-dev
    xorg-dev libglu1-mesa-dev
    python-opengl
    numpy > 1.5

