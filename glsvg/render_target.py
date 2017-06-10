__author__ = 'Ian'
import OpenGL.GL as gl
import graphics


class Texture2D:

    def __init__(self, w, h, wrap=True):

        self.width = w
        self.height = h
        self.id = gl.glGenTextures(1)
        print "texture id", self.id

        self.bind()
        gl.glTexEnvf(gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_MODULATE)

        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

        wrap_mode = gl.GL_REPEAT if wrap else gl.GL_CLAMP
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_mode)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_mode)

        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)

        print "Tex OK? ", gl.glGetError() == gl.GL_NO_ERROR
        self.unbind()

    def resize(self, w, h):
        self.width = w
        self.height = h
        self.bind()
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        self.unbind()


    def bind(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.id)

    def unbind(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()


class RenderBufferObject:
    def __init__(self, w, h):
        self.id = gl.glGenRenderbuffers(1)
        self.resize(w, h)

    def resize(self, w, h):
        self.width, self.height = w, h
        self.bind()
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, w, h)
        self.unbind()

    def bind(self):
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.id)

    def unbind(self):
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)


class RenderTarget:

    id_stack = []

    def __init__(self, w, h, depth_and_stencil=False):
        self.texture = Texture2D(w, h)
        self.id = gl.glGenFramebuffers(1)
        self.bind()
        self.depth_stencil = None
        if depth_and_stencil:
            self.depth_stencil = RenderBufferObject(w, h)

        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER,
            gl.GL_COLOR_ATTACHMENT0,
            gl.GL_TEXTURE_2D,
            self.texture.id,
            0)

        self.ok = self.check_status()

        self.unbind()

    def check_status(self):
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status == gl.GL_FRAMEBUFFER_COMPLETE:
            print "Framebuffer complete"
            return True
        else:
            print "Render target error: " + str(status)
            return False

    def blit(self):
        w,h = self.texture.width, self.texture.height
        with self.texture:
            graphics.draw_quad(0.5, 0.5, w+0.5, h+0.5)

    def resize(self, w, h):
        self.texture.resize(w, h)
        if self.depth_stencil:
            self.depth_stencil.resize(w, h)

    def bind(self):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.id)
        RenderTarget.id_stack.append(self.id)

    def unbind(self):
        if len(RenderTarget.id_stack):
            del RenderTarget.id_stack[-1]

        if len(RenderTarget.id_stack) >= 1:
            id = RenderTarget.id_stack[-1]
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, id)
        else:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()
        pass


class CanvasManager:
    instance = None

    def __init__(self):
        print "Initializing canvas manager"
        self.canvas = {}
        vp = list(gl.glGetFloatv(gl.GL_VIEWPORT))
        self.w = int(vp[2])
        self.h = int(vp[3])

    def resize(self, w, h):
        print "resizing", w, h
        self.w = w
        self.h = h

        for c in self.canvas.values():
            c.resize(w, h)

    def get(self, name):
        if not name in self.canvas:
            self.canvas[name] = RenderTarget(self.w, self.h)
        return self.canvas[name]

    def temp(self):
        return self.get('temp' + str(len(RenderTarget.id_stack)))

    def update(self):
        vp = list(gl.glGetFloatv(gl.GL_VIEWPORT))

        if self.w != int(vp[2]) and self.h != int(vp[3]):
            self.resize(int(vp[2]), int(vp[3]))

    @classmethod
    def inst(cls):
        if not cls.instance:
            cls.instance = CanvasManager()
        return cls.instance