SRC = $(shell ls src/*.c | grep -vE 'cocoa|mir|wgl|win32|wl')
OBJ = $(SRC:%.c=%.o)

CFLAGS = -march=native -O2 -fPIC -D_GLFW_X11
LFLAGS = -shared
LDLIBS = -ldl -lpthread -lX11 -lXrandr -lXinerama -lXcursor -lm

libglfw.so: $(OBJ)
	$(CC) $(LFLAGS) $^ -o $@ $(LDLIBS)

clean: ; $(RM) libglfw.so $(OBJ)
