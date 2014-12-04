TOP = .
TOP := $(shell (cd "$(TOP)"; pwd))
NO_SUBDIR_ALL=1
NO_SUBDIR_INSTALL=1
SUBDIRS = prereqs src

include $(TOP)/mk/config.make
include $(TOP)/mk/subdir.make

all:
	@echo "'make install' to build everything"

install:
	@echo 'Started install at' `date` on `hostname`
	$(MAKE) build-dirs
	$(MAKE) -C prereqs install.prebuilt
	$(MAKE) -C src install
	$(MAKE) -C docs html
	@echo 'Finished install at' `date`

docs.install:
	$(MAKE) -C docs html

build-dirs:
	-mkdir $(build_prefix) $(bindir) $(libdir) $(includedir) $(datadir) $(webdir)
	-cd $(build_prefix) && ln -fs lib lib64
ifneq ($(libdir), $(shlibdir))
	-mkdir $(shlibdir)
endif
ifdef USE_MAC_FRAMEWORKS
	-mkdir $(frameworkdir) $(build_prefix)/Library
	-cd $(build_prefix)/Library && ln -fs ../Frameworks .
endif

build-app-dirs:
	-mkdir -p $(app_prefix) $(app_bindir) $(app_libdir) $(app_datadir)
ifdef USE_MAC_FRAMEWORKS
	-mkdir -p $(app_frameworkdir)
endif

distclean: clean
	rm -rf $(build_prefix) $(app_prefix)
