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


# Optional dependency (only for some piio functions):
    numpy > 1.5
