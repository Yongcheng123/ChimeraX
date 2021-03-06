from .qt import QtWidgets, QtCore, QtGui

class Model_Panel:

    def __init__(self, session):

        self.session = session
        self.image_size = (128,128)

        self.dock_widget = dw = QtWidgets.QDockWidget('Scenes', session.main_window)
        dw.setTitleBarWidget(QtWidgets.QWidget(dw))   # No title bar
        dw.setFeatures(dw.NoDockWidgetFeatures)       # No close button

        class Thumbnail_Viewer(QtWidgets.QTextBrowser):
            height = 165
            close_button = None
            def sizeHint(self):
                return QtCore.QSize(600,self.height)
            def resizeEvent(self, e):
                QtWidgets.QTextBrowser.resizeEvent(self, e)
                c = self.close_button
                if c:
                    c.move(e.size().width()-c.width()-5,5)
        self.text = e = Thumbnail_Viewer(dw)
        e.setOpenLinks(False)

        e.close_button = ct = QtWidgets.QPushButton('X', e)
        ct.setStyleSheet("padding: 1px; min-width: 1em")
        ct.adjustSize()
        ct.clicked.connect(lambda e: self.hide())

        dw.setWidget(e)
        dw.setVisible(False)

        e.setReadOnly(True)
        e.anchorClicked.connect(self.anchor_callback)          # Handle clicks on anchors

        session.add_model_callbacks.append(self.models_changed)
        session.close_model_callbacks.append(self.models_changed)

    def show(self):
        d = self.text.document()
        lines = ['<html>', '<head>', '<style>',
                 'body { background-color: black; }',
                 'a { text-decoration: none; }',      # No underlining of links
                 'a:link { color: white; }',          # Link text color
                 'table { float:left; }',             # Multiple image/caption tables per row.
                 '</style>', '</head>', '<body>']
        mlist = list(self.session.top_level_models())
        mlist.sort(key = lambda m: m.id)
        from os.path import splitext
        for m in mlist:
            i = self.model_image(m)
            if i is None:
                continue
            uri = "file://image%d" % m.id
            from . import qt
            qt.register_html_image_identifier(d, uri, i)

            n = splitext(m.name)[0]
            lines.extend(['',
                          '<a href="%d">' % m.id,
                          '<table>',
                          '<tr><td height=%d><img src="%s">' % (self.image_size[1], uri),
                          '<tr><td><center>#%d %s</center>' % (m.id, n),
                          '</table>',
                          '</a>'])
        lines.extend(['</body>', '</html>'])

        self.html = html = '\n'.join(lines)
        self.text.setHtml(html)

        dw = self.dock_widget
        mw = self.session.main_window
        mw.addDockWidget(QtCore.Qt.TopDockWidgetArea, dw)
        dw.setVisible(True)

    def model_image(self, model):

        if hasattr(model, 'thumbnail_image'):
            return model.thumbnail_image
        v = self.session.view
        w,h = self.image_size
        i = v.image(w, h, drawings = [model])
        if not i is None:
            model.thumbnail_image = i
        return i

    def shown(self):
        return self.dock_widget.isVisible()

    def hide(self):
        mw = self.session.main_window
        mw.removeDockWidget(self.dock_widget)

    def anchor_callback(self, qurl):
        url = qurl.toString()
        id = int(url)
        for m in self.session.top_level_models():
            if m.id == id:
                m.display = not m.display

    # Models were added or closed.
    def models_changed(self, models):
        if self.shown():
            self.show()

def show_model_panel(session):
    if not hasattr(session, 'model_panel'):
        session.model_panel = Model_Panel(session)
    mp = session.model_panel
    if mp.shown():
        mp.hide()
    else:
        mp.show()
