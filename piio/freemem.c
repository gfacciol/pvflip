#include <stdio.h>
#include <stdlib.h>
#include <math.h>

void freemem(void *ptr){
   free(ptr);
}

void minmax(float *p, int N, float *vmin, float *vmax) {
   float imin = +INFINITY;
   float imax = -INFINITY;
   for ( int i=0;i<N;i++ ) {
      float pp = p[i];
      if ( isfinite(pp) ) {
         imin = fmin(imin, pp); 
         imax = fmax(imax, pp); 
      }
   }
   *vmin = imin;
   *vmax = imax;
}
