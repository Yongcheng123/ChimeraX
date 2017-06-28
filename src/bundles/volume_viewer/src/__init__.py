# vim: set expandtab ts=4 sw=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

from chimerax.core.toolshed import BundleAPI

class _VolumeViewerAPI(BundleAPI):

    @staticmethod
    def start_tool(session, tool_name):
        # 'start_tool' is called to start an instance of the tool
        from . import volumedialog
        return volumedialog.show_volume_dialog(session)

    @staticmethod
    def get_class(class_name):
        # 'get_class' is called by session code to get class saved in a session
        if class_name == 'VolumeViewer':
            from .volumedialog import VolumeViewer
            return VolumeViewer
        return None

bundle_api = _VolumeViewerAPI()