#!/usr/bin/env python
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
############################################################################

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

        if not os.path.exists('glfw/build'):
           os.mkdir('glfw/build')
        os.chdir('glfw/build')
        
        if os.system("cmake -DBUILD_SHARED_LIBS=ON -DGLFW_BUILD_EXAMPLES=OFF -DGLFW_BUILD_TESTS=OFF -DGLFW_BUILD_UNIVERSAL=ON ../glfw_src") :
            print("Error while building libglfw.dylib")
            sys.exit(1)
        if os.system("make") :
            print("Error while building libglfw.dylib")
            sys.exit(1)
            
        os.chdir("..")
        os.chdir("..")
            
        shutil.copyfile("glfw/build/src/libglfw.dylib", "glfw/libglfw.dylib")
        os.system("rm -fr glfw/build")
        
else:
    package_data = {"glfw": ["libglfw.so"]}
    
    if not os.path.exists("glfw/libglfw.so") and is_build:

        if not os.path.exists('glfw/build'):
           os.mkdir('glfw/build')
        os.chdir('glfw/build')
        
        if os.system("cmake -DBUILD_SHARED_LIBS=ON -DGLFW_BUILD_EXAMPLES=OFF -DGLFW_BUILD_TESTS=OFF ../glfw_src") :
            print("Error while building libglfw.so")
            sys.exit(1)
        if os.system("make") :
            print("Error while building libglfw.so")
            sys.exit(1)
            
        os.chdir("..")
        os.chdir("..")
        
        shutil.copyfile("glfw/build/src/libglfw.so", "glfw/libglfw.so")
        os.system("rm -fr glfw/build")


iiomodule = Extension('piio.libiio',  
    libraries = ['png','jpeg','tiff'],
    language=['c99'],
    extra_compile_args = ['-std=gnu99','-DNDEBUG','-O3'], 
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
