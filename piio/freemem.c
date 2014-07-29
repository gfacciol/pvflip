/* Primitive python wrapper for iio
* Copyright 2013, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>
*
* This file is part of pvflip.
* 
* Pvflip is free software: you can redistribute it and/or modify
* it under the terms of the GNU Affero General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
* 
* Pvflip is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
* GNU Affero General Public License for more details.
* 
* You should have received a copy of the GNU Affero General Public License
* along with pvflip.  If not, see <http://www.gnu.org/licenses/>.
* */

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

void copy_tile(float *src, int nc, int nr, int nch, float *dst, int x0, int y0, int w, int h, int dst_nch) {
   for (int j=0;j<h;j++) {
   for (int i=0;i<w;i++) {
   for (int c=0;c<dst_nch;c++) {
      float v=0;
      int ii = x0+i;
      int jj = y0+j;
      if(ii>=0 && jj>=0 && ii < nc && jj < nr && c < nch) {
         v = src[ nch*(ii + jj*nc)+c ];
      }
      dst[ dst_nch*(i + j*w)+c ] = v;
   }
   }
   }
}
