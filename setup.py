#!/usr/bin/env python

#from distutils.core import setup
from distutils.core import setup, Extension

import sys
import os
import shutil

command = sys.argv[1] if len(sys.argv) >= 2 else ""
is_build = command.startswith("build") or command.startswith("install") or command.startswith("bdist")

if sys.platform == "win32":
    package_data = {"glfw": ["glfw.dll"]}
    
    # pre-built
    ## MISSING!
    shutil.copyfile("glfw-3.0.3/lib/win32/glfw.dll", "glfw/glfw.dll")
    
elif sys.platform == "darwin":
    package_data = {"glfw": ["libglfw.dylib"]}
    
    if not os.path.exists("glfw/libglfw.dylib") and is_build:
        # let's cross our fingers and hope the build goes smooth (without user intervention)

        if not os.path.exists('build'):
           os.mkdir('build')
        os.chdir('build')
        
        if os.system("cmake -DBUILD_SHARED_LIBS=ON -DGLFW_BUILD_EXAMPLES=OFF -DGLFW_BUILD_TESTS=OFF -DGLFW_BUILD_UNIVERSAL=ON ../glfw-3.0.3") :
            print("Error while building libglfw.dylib")
            sys.exit(1)
        if os.system("make") :
            print("Error while building libglfw.dylib")
            sys.exit(1)
            
        os.chdir("..")
            
    shutil.copyfile("build/src/libglfw.dylib", "glfw/libglfw.dylib")
        
else:
    package_data = {"glfw": ["libglfw.so"]}
    
    if not os.path.exists("glfw/libglfw.so") and is_build:

        if not os.path.exists('build'):
           os.mkdir('build')
        os.chdir('build')
        
        if os.system("cmake -DBUILD_SHARED_LIBS=ON -DGLFW_BUILD_EXAMPLES=OFF -DGLFW_BUILD_TESTS=OFF ../glfw-3.0.3") :
            print("Error while building libglfw.so")
            sys.exit(1)
        if os.system("make") :
            print("Error while building libglfw.so")
            sys.exit(1)
            
        os.chdir("..")
        
    shutil.copyfile("build/src/libglfw.so", "glfw/libglfw.so")


iiomodule = Extension('piio.libiio',  
    libraries = ['png','jpeg','tiff'],
    language=['c99'],
    extra_compile_args = ['-std=c99','-DNDEBUG','-O3'], 
    sources = ['piio/iio.c','piio/freemem.c']
   )


setup_info = {
    "name": "pyglfw3",
    "version": "1.0.0",
    "author": "Gabriele Facciolo",
    "author_email": "gfacciol@gmail.com",
    "url": "",
    "description": "GLFW3 bindings for Python",
    "license": "BSD-style attribution-only license",
    "classifiers": [
        "Environment :: MacOS X",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    
    "packages": ['glfw', 'piio'],
    "ext_modules": [iiomodule],
    "package_data": package_data,
    "scripts" : ['v.py'],

}
    
setup(**setup_info)
