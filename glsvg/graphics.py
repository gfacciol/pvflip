import OpenGL.GL as gl
import math

triangles_drawn = 0


def clear_stats():
    global triangles_drawn
    triangles_drawn = 0


def add_triangle_stats(tris):
    global triangles_drawn
    triangles_drawn += tris


def draw_triangle_strip(vertices, color):
    if color:
        gl.glColor4ub(*color)
    n_vertices = len(vertices)/2
    add_triangle_stats(n_vertices-2)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, vertices)
    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, len(vertices) // 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)


def draw_round_cap(center, radius, angle):
    n_vertices = 1
    v = [center.x, center.y]

    for theta in range(-90, 91, 10):
        at = theta*(math.pi/180) + angle
        x = math.cos(at) * radius + center.x
        y = math.sin(at) * radius + center.y
        n_vertices += 1
        v.append(x)
        v.append(y)

    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, v)
    gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, len(v) // 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)

    add_triangle_stats(n_vertices-1)


def draw_colored_triangles(tris, colors):
    add_triangle_stats(len(tris)/6)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_COLOR_ARRAY)
    gl.glColorPointer(4, gl.GL_UNSIGNED_BYTE, 0, colors)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, tris)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(tris) // 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_COLOR_ARRAY)


def draw_textured_triangles(tris, tex_coords):
    add_triangle_stats(len(tris)/6)
    gl.glColor4f(1, 1, 1, 1)
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)

    gl.glVertexPointer(2, gl.GL_FLOAT, 0, tris)
    gl.glTexCoordPointer(2, gl.GL_FLOAT, 0, tex_coords)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(tris) // 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
    gl.glDisable(gl.GL_TEXTURE_2D)


def draw_quad(x, y, w, h):

    points = [x, y,
              x + w, y,
              x + w, y + h,
              x, y + h]

    tex_coords = [0, 1,
                  1, 1,
                  1, 0,
                  0, 0]
    add_triangle_stats(2)
    gl.glColor4f(1, 1, 1, 1)
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)

    gl.glVertexPointer(2, gl.GL_FLOAT, 0, points)
    gl.glTexCoordPointer(2, gl.GL_FLOAT, 0, tex_coords)
    gl.glDrawArrays(gl.GL_QUADS, 0, len(points) // 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
    gl.glDisable(gl.GL_TEXTURE_2D)