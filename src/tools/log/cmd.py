# vim: set expandtab ts=4 sw=4:

def get_singleton(session, create=False):
    if not session.ui.is_gui:
        return None
    from chimerax.core import tools
    from .gui import Log
    return tools.get_singleton(session, Log, 'log', create=create)

def log(session, show = False, hide = False, clear = False, save_path = None,
        thumbnail = False, width = 100, height = 100,
        warning_dialog = None, error_dialog = None):
    '''Operations on the Log window.

    Parameters
    ----------
    show : bool
      Show the log panel.
    hide : bool
      Hide the log panel.
    clear : bool
      Erase the log contents.
    save_path : string
      Save log contents as html to a file.
    thumbnail : bool
      Place a thumbnail image of the current graphics in the log.
    height : int
      Height in pixels of thumbnail image.
    width : int
      Width in pixels of thumbnail image.
    warning_dialog : bool
      If true, warnings popup a separate dialog, if false no warning dialog is shown.
      In either case the warning appears in the log text.
    error_dialog : bool
      If true, errors popup a separate dialog, if false no error dialog is shown.
      In either case the errors appears in the log text.
    '''
    create = show
    log = get_singleton(session, create = create)
    if log is not None:
        if hide:
            log.display(False)
        if show:
            log.display(True)
        if clear:
            log.clear()
        if not save_path is None:
            log.save(save_path)
        if thumbnail:
            im = session.main_view.image(width, height)
            log.log(log.LEVEL_INFO, 'graphics image', (im, True), True)
        if not warning_dialog is None:
            log.warning_shows_dialog = warning_dialog
        if not error_dialog is None:
            log.error_shows_dialog = error_dialog

from chimerax.core.commands import CmdDesc, NoArg, BoolArg, IntArg, SaveFileNameArg
log_desc = CmdDesc(keyword = [('show', NoArg),
                              ('hide', NoArg),
                              ('clear', NoArg),
                              ('thumbnail', NoArg),
                              ('width', IntArg),
                              ('height', IntArg),
                              ('save_path', SaveFileNameArg),
                              ('warning_dialog', BoolArg),
                              ('error_dialog', BoolArg)])
