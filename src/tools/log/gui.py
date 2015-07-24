# vi: set expandtab ts=4 sw=4:

from chimera.core.tools import ToolInstance
from chimera.core.logger import HtmlLog


class Log(ToolInstance, HtmlLog):

    SESSION_ENDURING = True
    SIZE = (300, 500)
    STATE_VERSION = 1

    def __init__(self, session, tool_info, **kw):
        super().__init__(session, tool_info, **kw)
        from chimera.core.gui import MainToolWindow
        class LogWindow(MainToolWindow):
            close_destroys = False
        self.tool_window = LogWindow(self, size=self.SIZE)
        parent = self.tool_window.ui_area
        import wx
        wx.FileSystem.AddHandler(wx.MemoryFSHandler())
        from itertools import count
        self._image_count = count()
        from wx import html2
        self.log_window = html2.WebView.New(parent, size=self.SIZE)
        self.log_window.EnableContextMenu(False)
        self.page_source = ""
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.log_window, 1, wx.EXPAND)
        parent.SetSizerAndFit(sizer)
        self.tool_window.manage(placement="right")
        session.tools.add([self])
        session.logger.add_log(self)
        self.log_window.Bind(wx.EVT_CLOSE, self.window_close)
        self.log_window.SetPage(self.page_source, "")
        self.log_window.Bind(html2.EVT_WEBVIEW_LOADED, self.show_bottom)

    #
    # Implement logging
    #
    def log(self, level, msg, image_info, is_html):
        """Log a message

        Parameters documented in HtmlLog base class
        """

        import wx
        image, image_break = image_info
        if image:
            import io
            img_io = io.BytesIO()
            image.save(img_io, format='PNG')
            png_data = img_io.getvalue()
            import codecs
            bitmap = codecs.encode(png_data, 'base64')
            width, height = image.size
            img_src = '<img src="data:image/png;base64,%s" width=%d height=%d style="vertical-align:middle">' % (bitmap.decode('utf-8'), width, height)
            self.page_source += img_src
            if image_break:
                self.page_source += "<br>"
        else:
            if level in (self.LEVEL_ERROR, self.LEVEL_WARNING):
                if level == self.LEVEL_ERROR:
                    caption = "Chimera 2 Error"
                    icon = wx.ICON_ERROR
                else:
                    caption = "Chimera 2 Warning"
                    icon = wx.ICON_EXCLAMATION
                style = wx.OK | wx.OK_DEFAULT | icon | wx.CENTRE
                graphics = self.session.ui.main_window.graphics_window
                if is_html:
                    from chimera.core.logger import html_to_plain
                    dlg_msg = html_to_plain(msg)
                else:
                    dlg_msg = msg
                if dlg_msg.count('\n') > 30:
                    # avoid excessively high error dialogs where
                    # both the bottom buttons and top controls
                    # may be off the screen!
                    lines = dlg_msg.split('\n')
                    dlg_msg = '\n'.join(lines[:15] + ["..."] + lines[-15:])
                dlg = wx.MessageDialog(graphics, dlg_msg,
                                       caption=caption, style=style)
                dlg.ShowModal()

            if not is_html:
                from html import escape
                msg = escape(msg)
                msg = msg.replace("\n", "<br>")

            if level == self.LEVEL_ERROR:
                msg = '<font color="red">' + msg + '</font>'
            elif level == self.LEVEL_WARNING:
                msg = '<font color="red">' + msg + '</font>'

            self.page_source += msg
        self.log_window.ClearHistory()
        self.log_window.SetPage(self.page_source, "")
        return True

    def show_bottom(self, event):
        # scroll to bottom
        self.log_window.RunScript(
            "window.scrollTo(0, document.body.scrollHeight);")

    def window_close(self, event):
        self.session.logger.remove_log(self)

    #
    # Implement session.State methods if deriving from ToolInstance
    #
    def take_snapshot(self, phase, session, flags):
        if phase != self.SAVE_PHASE:
            return
        version = self.STATE_VERSION
        data = {"shown": self.tool_window.shown}
        return [version, data]

    def restore_snapshot(self, phase, session, version, data):
        from chimera.core.session import RestoreError
        if version != self.STATE_VERSION:
            raise RestoreError("unexpected version")
        if phase == self.CREATE_PHASE:
            # All the action is in phase 2 because we do not
            # want to restore until all objects have been resolved
            pass
        else:
            self.display(data["shown"])

    def reset_state(self):
        self.tool_window.shown = True

    #
    # Override ToolInstance methods
    #
    def delete(self):
        self.session.logger.remove_log(self)
        super().delete()
