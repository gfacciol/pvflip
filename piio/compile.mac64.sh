#WITHOUT EXR STATICALLY LINKED
#gcc-4.8 -std=c99 -c iio.c -I/usr/local/Cellar/libpng/1.5.14/include/
#gcc-4.8 -std=c99 -c freemem.c
#gcc -dynamiclib -arch x86_64 -o MAC64/libiio.so iio.o freemem.o /usr/local/Cellar/libpng/1.5.18/lib/libpng.a /usr/local/Cellar/jpeg/8d/lib/libjpeg.a /usr/local/Cellar/libtiff/4.0.3/lib/libtiff.a  /usr/local/Cellar/zlib/1.2.8/lib/libz.a

#WITH EXR STATICALLY LINKED
gcc-4.8 -std=c99 -c iio.c -I/usr/local/Cellar/libpng/1.5.14/include/ -I/usr/local/include/OpenEXR  -DI_CAN_HAS_LIBEXR -O3 -std=c99 -funroll-loops -Wno-unused -DNDEBUG 
gcc-4.8 -std=c99 -c freemem.c -O3
gcc -dynamiclib -arch x86_64 -o MAC64/libiio.so iio.o freemem.o /usr/local/lib/libImath.a /usr/local/lib/libIlmImf.a /usr/local/lib/libIex.a /usr/local/lib/libHalf.a /usr/local/lib/libIlmThread.a /usr/local/Cellar/zlib/1.2.8/lib/libz.a /usr/local/lib/libtiff.a /usr/local/lib/libjpeg.a /usr/local/Cellar/libpng/1.5.18/lib/libpng.a /usr/local/Cellar/zlib/1.2.8/lib/libz.a /usr/local/lib/libtiff.a /usr/local/lib/libjpeg.a /usr/local/Cellar/libpng/1.5.18/lib/libpng.a /usr/lib/libstdc++-static.a


