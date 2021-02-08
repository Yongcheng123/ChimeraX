# vim: set expandtab shiftwidth=4 softtabstop=4:

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

_model = None
def get_model(session, *, create=True, add_created=True):
    if not _model and create:
        # constructor sets _model, which makes session restore easier
        ColorKeyModel(session)
        if add_created:
            session.models.add([_model], root_model = True)
    return _model

from chimerax.core.models import Model

class ColorKeyModel(Model):

    pickable = False
    casts_shadows = False

    CT_BLENDED = "blended"
    CT_DISTINCT = "distinct"
    color_treatments = (CT_BLENDED, CT_DISTINCT)

    JUST_LEFT = "left"
    JUST_DECIMAL = "decimal point"
    JUST_RIGHT = "right"
    justifications = (JUST_LEFT, JUST_DECIMAL, JUST_RIGHT)

    LS_LEFT_TOP = "left/top"
    LS_RIGHT_BOTTOM = "right/bottom"
    label_sides = (LS_LEFT_TOP, LS_RIGHT_BOTTOM)

    NLS_EQUAL = "equal"
    NLS_PROPORTIONAL = "proportional to value"
    numeric_label_spacings = (NLS_EQUAL, NLS_PROPORTIONAL)


    def __init__(self, session):
        super().__init__("Color key", session)
        global _model
        _model = self

        self._window_size = None
        self._texture_pixel_scale = 1
        self._aspect = 1
        self.needs_update = True

        from chimerax.core.triggerset import TriggerSet
        self.key_triggers = TriggerSet()
        #TODO: actually fire these appropriately
        self.key_triggers.add_trigger("changed")
        self.key_triggers.add_trigger("closed")

        self._position = None
        self._size = (0.25, 0.05)
        self._rgbas_and_labels = [((0,0,1,1), "min"), ((1,1,1,1), ""), ((1,0,0,1), "max")]
        self._numeric_label_spacing = self.NLS_PROPORTIONAL
        self._color_treatment = self.CT_BLENDED
        self._justification = self.JUST_DECIMAL
        self._label_offset = 0
        self._label_side = self.LS_RIGHT_BOTTOM
        self._label_rgba = None
        self._bold = False
        self._italic = False
        self._font_size = 24
        self._font = 'Arial'

        self._background_handler = None
        self._update_background_handler()

        session.main_view.add_overlay(self)

    def delete(self):
        if self._background_handler:
            from chimerax.core.core_settings import settings
            settings.triggers.remove_handler(self._background_handler)
        self.session.main_view.remove_overlays([self], delete = False)
        self.key_triggers.activate_trigger("closed", None)
        super().delete()
        global _model
        _model = None

    def draw(self, renderer, draw_pass):
        if self._position is None:
            return
        self._update_graphics(renderer)
        super().draw(renderer, draw_pass)

    @property
    def bold(self):
        return self._bold

    @bold.setter
    def bold(self, bold):
        if bold == self._bold:
            return
        self._bold = bold
        self.needs_update = True
        self.redraw_needed()

    @property
    def color_treatment(self):
        return self._color_treatment

    @color_treatment.setter
    def color_treatment(self, ct):
        if ct == self._color_treatment:
            return
        self._color_treatment = ct
        self.needs_update = True
        self.redraw_needed()

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, font):
        if font == self._font:
            return
        self._font = font
        self.needs_update = True
        self.redraw_needed()

    @property
    def font_size(self):
        return self._font_size

    @font_size.setter
    def font_size(self, font_size):
        if font_size == self._font_size:
            return
        self._font_size = font_size
        self.needs_update = True
        self.redraw_needed()

    @property
    def italic(self):
        return self._italic

    @italic.setter
    def italic(self, italic):
        if italic == self._italic:
            return
        self._italic = italic
        self.needs_update = True
        self.redraw_needed()

    @property
    def justification(self):
        return self._justification

    @justification.setter
    def justification(self, just):
        if just == self.JUST_DECIMAL.split()[0]:
            just = self.JUST_DECIMAL
        if just == self._justification:
            return
        self._justification = just
        self.needs_update = True
        self.redraw_needed()

    @property
    def label_offset(self):
        # None means contrast with background
        return self._label_offset

    @label_offset.setter
    def label_offset(self, offset):
        if offset == self._label_offset:
            return
        self._label_offset = offset
        self.needs_update = True
        self.redraw_needed()

    @property
    def label_rgba(self):
        # None means contrast with background
        return self._label_rgba

    @label_rgba.setter
    def label_rgba(self, rgba):
        from numpy import array_equal
        if array_equal(rgba, self._label_rgba):
            return
        self._label_rgba = rgba
        self.needs_update = True
        self.redraw_needed()
        self._update_background_handler()

    @property
    def label_side(self):
        return self._label_side

    @label_side.setter
    def label_side(self, side):
        if side == self._label_side:
            return
        self._label_side = side
        self.needs_update = True
        self.redraw_needed()

    @property
    def numeric_label_spacing(self):
        return self._numeric_label_spacing

    @numeric_label_spacing.setter
    def numeric_label_spacing(self, spacing):
        if spacing == self.NLS_PROPORTIONAL.split()[0]:
            spacing = self.NLS_PROPORTIONAL
        if spacing == self._numeric_label_spacing:
            return
        self._numeric_label_spacing = spacing
        self.needs_update = True
        self.redraw_needed()

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, llxy):
        if llxy == self._position:
            return
        self._position = llxy
        self.needs_update = True
        self.redraw_needed()

    @property
    def rgbas_and_labels(self):
        return self._rgbas_and_labels

    @rgbas_and_labels.setter
    def rgbas_and_labels(self, r_l):
        # skip the equality test since there are numpy arrays involved, sigh...
        self._rgbas_and_labels = r_l
        self.needs_update = True
        self.redraw_needed()

    @property
    def single_color(self):
        return None

    @single_color.setter
    def single_color(self, val):
        pass

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, wh):
        if wh == self._size:
            return
        self._size = wh
        self.needs_update = True
        self.redraw_needed()

    session_attrs = [
            "_bold",
            "_color_treatment",
            "_font",
            "_font_size",
            "_italic",
            "_justification",
            "_label_offset",
            "_label_rgba",
            "_label_side",
            "_numeric_label_spacing",
            "_position",
            "_rgbas_and_labels",
            "_size",
    ]

    def take_snapshot(self, session, flags):
        return { attr: getattr(self, attr) for attr in self.session_attrs }

    @staticmethod
    def restore_snapshot(session, data):
        key = get_model(session, add_created=False)
        for attr, val in data.items():
            setattr(key, attr, val)
        key.needs_update = True
        key.redraw_needed()
        key._update_background_handler()
        return key

    def _update_background_handler(self):
        need_handler = self._label_rgba is None
        from chimerax.core.core_settings import settings
        if need_handler and not self._background_handler:
            def check_setting(trig_name, data, key=self):
                if data[0] == 'background_color':
                    key.needs_update = True
                    key.redraw_needed()
            self._background_handler = settings.triggers.add_handler('setting changed', check_setting)
        elif not need_handler and self._background_handler:
            settings.triggers.remove_handler(self._background_handler)
            self._background_handler = None

    def _update_graphics(self, renderer):
        """
        Recompute the key's texture image or update its texture coordinates that position it in the window
        based on the rendered window size.  When saving an image file, the rendered size may differ from the
        on-screen window size.  In that case, make the label size match its relative size seen on the screen.
        """
        window_size = renderer.render_size()

        # Remember the on-screen size if rendering off screen
        if getattr(renderer, 'image_save', False):
            # When saving an image, match the key's on-screen fractional size, even though the image size
            # in pixels may be different from on screen
            sw, sh = self.session.main_view.window_size
            w, h = window_size
            pixel_scale = (w / sw) if sw > 0 else 1
            aspect = (w*sh) / (h*sw) if h*sw > 0 else 1
        else:
            pixel_scale = renderer.pixel_scale()
            aspect = 1
        if pixel_scale != self._texture_pixel_scale or aspect != self._aspect:
            self._texture_pixel_scale = pixel_scale
            self._aspect = aspect
            self.needs_update = True

        # Need to reposition key if window size changes
        win_size_changed = (window_size != self._window_size)
        if win_size_changed:
            self._window_size = window_size
            self.needs_update = True

        if self.needs_update:
            self.needs_update = False
            self._update_key_image()

    def _update_key_image(self):
        rgba = self._key_image_rgba()
        if rgba is None:
            self.session.logger.info("Can't find font for color key labels")
        else:
            self._set_key_image(rgba)

    def _key_image_rgba(self):
        key_w, key_h = self._size
        win_w, win_h = self._window_size
        rect_pixels = [int(win_w * key_w + 0.5), int(win_h * key_h + 0.5)]
        pixels = rect_pixels[:]
        self.start_offset = start_offset = [0, 0]
        self.end_offset = end_offset = [0, 0]
        label_offset = self._label_offset + 5
        if pixels[0] > pixels[1]:
            layout = "horizontal"
            long_index = 0
        else:
            layout = "vertical"
            long_index = 1
        rect_positions = self._rect_positions(pixels[long_index])

        if self._color_treatment == self.CT_BLENDED:
            label_positions = rect_positions
        else:
            label_positions = [(rect_positions[i] + rect_positions[i+1])/2
                for i in range(len(rect_positions)-1)]

        rgbas, labels = zip(*self._rgbas_and_labels)
        rgbas = [(int(255*r + 0.5), int(255*g + 0.5), int(255*b + 0.5), int(255*a + 0.5))
            for r,g,b,a in rgbas]

        from Qt.QtGui import QImage, QPainter, QColor, QBrush, QPen, QLinearGradient, QFontMetrics, QFont
        from Qt.QtCore import Qt, QRect, QPoint

        font = QFont(self.font, self.font_size * self._texture_pixel_scale,
            (QFont.Bold if self.bold else QFont.Normal), self.italic)
        fm = QFontMetrics(font)
        font_height = fm.ascent()
        font_descender = fm.descent()
        # text is centered vertically from 0 to height (i.e. ignore descender) whereas it is centered
        # horizontally across the full width
        #
        # fm.boundingRect(label) basically returns a fixed height for all labels (and a large negative y)
        # so just use the font size instead
        if labels[0]:
            # may need extra room to left or top for first label
            bounds = fm.boundingRect(labels[0])
            xywh = bounds.getRect()
            # Qt seemingly will not return the actual height of a text string; estimate all lower case
            # to be 2/3 height
            label_height = (font_height * 2/3) if labels[0].islower() else font_height
            label_size = label_height if layout == "vertical" else xywh[long_index+2]
            extra = max(label_size / 2 - label_positions[0], 0)
            start_offset[long_index] += extra
            pixels[long_index] += extra

        # need room below or to right to layout labels
        # if layout is vertical and justification is decimal-point, the "widest label" is actually the
        # combination of the widest to the left of the decimal point + the widest to the right of it
        decimal_widths = []
        if layout == "vertical" and self._justification == self.JUST_DECIMAL:
            left_widest = right_widest = 0
            for label in labels:
                overall = fm.boundingRect(label).getRect()[2]
                if '.' in label:
                    right = fm.boundingRect(label[label.index('.'):]).getRect()[2]
                    left = overall - right
                else:
                    left = overall
                    right = 0
                left_widest = max(left_widest, left)
                right_widest = max(right_widest, right)
                decimal_widths.append((left, right))
            extra = left_widest + right_widest + label_offset
        else:
            if layout == "vertical":
                extra = max([fm.boundingRect(lab).getRect()[3-long_index] for lab in labels]) + label_offset
            else:
                # Qt seemingly will not return the actual height of a text string; estimate all lower case
                # to be 2/3 height
                for label in labels:
                    if label and not label.islower():
                        label_height = font_height
                        break
                else:
                    label_height = font_height * 2/3
                extra = label_height + label_offset
            decimal_widths = [(None, None)] * len(labels)
        if self._label_side == self.LS_LEFT_TOP:
            start_offset[1-long_index] += extra
        else:
            end_offset[1-long_index] += extra
        pixels[1-long_index] += extra

        pixels[1] += font_descender
        end_offset[1] += font_descender

        if labels[-1]:
            # may need extra room to right or bottom for last label
            bounds = fm.boundingRect(labels[-1])
            xywh = bounds.getRect()
            # Qt seemingly will not return the actual height of a text string; estimate all lower case
            # to be 2/3 height
            label_height = (font_height * 2/3) if labels[-1].islower() else font_height
            label_size = label_height if layout == "vertical" else xywh[long_index+2]
            extra = max(label_size / 2 - (rect_pixels[long_index] - label_positions[-1]), 0)
            end_offset[long_index] += extra
            pixels[long_index] += extra

        image = QImage(max(pixels[0], 1), max(pixels[1], 1), QImage.Format_ARGB32)
        image.fill(QColor(0,0,0,0))    # Set background transparent

        try:
            p = QPainter(image)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(Qt.NoPen))

            if self._color_treatment == self.CT_BLENDED:
                edge1, edge2 = start_offset[1-long_index], pixels[1-long_index] - end_offset[1-long_index]
                for i in range(len(rect_positions)-1):
                    start = start_offset[long_index] + rect_positions[i]
                    stop = start_offset[long_index] + rect_positions[i+1]
                    if layout == "vertical":
                        x1, y1, x2, y2 = edge1, start, edge2, stop
                        gradient = QLinearGradient(0, start, 0, stop)
                    else:
                        x1, y1, x2, y2 = start, edge1, stop, edge2
                        gradient = QLinearGradient(start, 0, stop, 0)
                    gradient.setColorAt(0, QColor(*rgbas[i]))
                    gradient.setColorAt(1, QColor(*rgbas[i+1]))
                    p.setBrush(QBrush(gradient))
                    p.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)))
                # The one-call gradient below doesn't seem to position the transition points
                # completely correct, whereas the above piecemeal code does
                """
                gradient = QLinearGradient()
                gradient.setCoordinateMode(QLinearGradient.ObjectMode)
                rect_start = [start_offset[i] / pixels[i] for i in (0,1)]
                rect_end = [(pixels[i] - end_offset[i]) / pixels[i] for i in (0,1)]
                if layout == "vertical":
                    start, stop = (rect_start[0], rect_end[1]), (rect_start[0], rect_start[1])
                else:
                    start, stop = (rect_start[0], rect_start[1]), (rect_end[0], rect_start[1])
                gradient.setStart(*start)
                gradient.setFinalStop(*stop)
                for rgba, rect_pos in zip(rgbas, rect_positions):
                    fraction = rect_pos/rect_positions[-1]
                    if layout == "vertical":
                        fraction = 1.0 - fraction
                    gradient.setColorAt(fraction, QColor(*rgba))
                p.setBrush(QBrush(gradient))
                p.drawRect(QRect(QPoint(start_offset[0], start_offset[1]),
                    QPoint(pixels[0] - end_offset[0], pixels[1] - end_offset[1])))
                """
            else:
                for i in range(len(rect_positions)-1):
                    brush = QBrush(QColor(*rgbas[i]))
                    p.setBrush(brush)
                    if layout == "vertical":
                        x1, y1 = 0, rect_positions[i]
                        x2, y2 = rect_pixels[0], rect_positions[i+1]
                    else:
                        x1, y1 = rect_positions[i], 0
                        x2, y2 = rect_positions[i+1], rect_pixels[1]
                    p.drawRect(QRect(QPoint(x1 + start_offset[0], y1 + start_offset[1]),
                        QPoint(x2 + start_offset[0], y2 + start_offset[1])))
            p.setFont(font)
            from chimerax.core.colors import contrast_with_background
            rgba = contrast_with_background(self.session) if self._label_rgba is None else self._label_rgba
            p.setPen(QColor(*[int(255.0*c + 0.5) for c in rgba]))
            for label, pos, decimal_info in zip(labels, label_positions, decimal_widths):
                if not label:
                    continue
                rect = fm.boundingRect(label)
                if layout == "vertical":
                    if self._justification == self.JUST_DECIMAL:
                        pre_decimal_width, decimal_width = decimal_info
                        if self._label_side == self.LS_LEFT_TOP:
                            x = start_offset[0] - right_widest - pre_decimal_width - label_offset
                        else:
                            x = pixels[0] - right_widest - pre_decimal_width
                    elif self._justification == self.JUST_LEFT:
                        if self._label_side == self.LS_LEFT_TOP:
                            x = 0
                        else:
                            x = pixels[0] - end_offset[0] + label_offset
                    else:
                        if self._label_side == self.LS_LEFT_TOP:
                            x = start_offset[0] - (rect.width() - rect.x()) - label_offset
                        else:
                            x = pixels[0] - (rect.width() - rect.x())
                    # Qt seemingly will not return the actual height of a text string; estimate all
                    # lower case to be 2/3 height
                    label_height = (font_height * 2/3) if label.islower() else font_height
                    y = start_offset[1] + pos + label_height / 2
                else:
                    if self._label_side == self.LS_LEFT_TOP:
                        y = font_height
                    else:
                        y = pixels[1] - font_descender
                    x = start_offset[0] + pos - (rect.width() - rect.x())/2
                p.drawText(x, y, label)
        finally:
            p.end()

        # Convert to numpy rgba array
        from chimerax.graphics import qimage_to_numpy
        return qimage_to_numpy(image)

    def _rect_positions(self, long_size):
        proportional = False
        texts = [color_text[1] for color_text in self._rgbas_and_labels]
        if self._numeric_label_spacing == self.NLS_PROPORTIONAL:
            import locale
            local_numeric = locale.getlocale(locale.LC_NUMERIC)
            try:
                locale.setlocale(locale.LC_NUMERIC, 'en_US.UTF-8')
                try:
                    values = [locale.atof(t) for t in texts]
                except (ValueError, TypeError):
                    pass
                else:
                    if values == sorted(values):
                        proportional = True
                    else:
                        values.reverse()
                        if values == sorted(values):
                            proportional = True
                        values.reverse()
            finally:
                locale.setlocale(locale.LC_NUMERIC, local_numeric)
        if not proportional:
            values = range(len(texts))
        if self._color_treatment == self.CT_BLENDED:
            val_size = abs(values[0] - values[-1])
            rect_positions = [long_size * abs(v - values[0])/val_size for v in values]
        else:
            v0 = values[0] - (values[1] - values[0])/2.0
            vN = values[-1] + (values[-1] - values[-2])/2.0
            val_size = abs(vN-v0)
            positions = [long_size * abs(v-v0) / val_size for v in values]
            rect_positions = [0.0] + [(positions[i] + positions[i+1])/2.0
                for i in range(len(values)-1)] + [long_size]
        return rect_positions

    def _set_key_image(self, rgba):
        if self._position is None:
            return
        key_x, key_y = self._position
        # adjust to the corner of the key itself, excluding labels etc.
        w, h = self._window_size
        key_x -= self.start_offset[0] / w
        key_y -= self.end_offset[1] / h
        x, y = (-1 + 2*key_x, -1 + 2*key_y)    # Convert 0-1 position to -1 to 1.
        y *= self._aspect
        th, tw = rgba.shape[:2]
        self._texture_size = (tw, th)
        uw, uh = 2*tw/w, 2*th/h
        from chimerax.graphics.drawing import rgba_drawing
        rgba_drawing(self, rgba, (x, y), (uw, uh), opaque=False)