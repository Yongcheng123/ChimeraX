TOP	= ../../..
include $(TOP)/mk/config.make

# TODO: remove this when everywhere
CXX += -fvisibility-ms-compat

ifdef WIN32
INCS = -I'$(shell cygpath -m '$(includedir)')'
else
INCS = -I$(includedir)
endif

ifeq ($(WIN32),msvc)
DEFS += -DLLGR_EXPORT
LIBS = /link /LIBPATH:'$(shell cygpath -m '$(libdir)')' glew32.lib opengl32.lib msvcrt.lib
else
LIBS = $(OPENGL_LIBS)
endif

SRCS = ShaderProgram.cpp programs.cpp buffers.cpp matrices.cpp objects.cpp \
       optimize.cpp render.cpp spiral.cpp primitives.cpp vsphere.cpp \
       init.cpp groups.cpp
OBJS = $(SRCS:.cpp=.$(OBJ_EXT))
LIBNAME = llgr

#all: $(LIBRARY)
all: $(SHLIB)

install: all
	cp llgr.h llgr_int.h llgr_impl.h llgr_ui.h ShaderProgram.h $(includedir)
	cp $(SHLIB) $(shlibdir)
ifdef WIN32
	cp lib$(LIBNAME).lib $(libdir)
endif

$(LIBRARY): $(OBJS)
	$(LIB_LINK)

$(SHLIB): $(OBJS)
	$(SHLIB_LINK)

clean:
	rm -f $(LIBRARY) $(SHLIB) $(OBJS)
ifeq ($(WIN32),msvc)
	rm -f $(SHLIB).manifest lib$(LIBNAME).{exp,pdb,ilk} vc*.pdb
endif
