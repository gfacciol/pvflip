import OpenGL.GL as gl


class CurrentTransform:
    def __enter__(self):
        gl.glPushMatrix()
        return self

    def __exit__(self, type, value, traceback):
        gl.glPopMatrix()


class DisplayList:
    def __init__(self):
        self.display_list_id = gl.glGenLists(1)

    def __call__(self):
        gl.glCallList(self.display_list_id)

class DisplayListGenerator:
    def __enter__(self):
        dl = DisplayList()
        gl.glNewList(dl.display_list_id, gl.GL_COMPILE)
        return dl

    def __exit__(self, type, value, traceback):
        gl.glEndList()

class ViewportAs:
    def __init__(self, x, y, w, h, viewport_w=None, viewport_h=None, invert_y=False):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.viewport_w = viewport_w if viewport_w else w
        self.viewport_h = viewport_h if viewport_h else h
        self.invert_y = False

    def __enter__(self):
        self.old_viewport = list(gl.glGetFloatv(gl.GL_VIEWPORT))

        gl.glViewport(0, 0, self.viewport_w, self.viewport_h)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        if not self.invert_y:
            gl.glOrtho(self.x, self.w, self.y, self.h, 0, 1)
        else:
            gl.glOrtho(self.x, self.w, self.h, self.y, 0, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        return self

    def __exit__(self, type, value, traceback):
        viewport = self.old_viewport
        gl.glMatrixMode(gl.GL_PROJECTION)

        gl.glPopMatrix()
        gl.glViewport(int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
        gl.glMatrixMode(gl.GL_MODELVIEW)