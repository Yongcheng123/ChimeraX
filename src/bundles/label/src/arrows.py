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


def arrow_create(session, name, start, end, *, color=None, weight=1.0,
                 visibility=True, mid_point=None, head_style="solid"):
    '''Create an arrow at a fixed position in the graphics window.

    Parameters
    ----------
    name : string
        Identifier for the arrow, used to change or delete arrow.
    start : numeric two-tuple
        Where arrow starts as x,y "screen coordinates" where coordinates go from 0 to 1, lower left
        to upper right.
    end : numeric two-tuple
        Where arrow ends (i.e. where arrowhead is placed) as x,y "screen coordinates" where coordinates
        go from 0 to 1, lower left to upper right.
    color : Color
      Color of the arrow.  If no color is specified black is used on light backgrounds
      and white is used on dark backgrounds.
    weight : float
      Relative thickness of arrow, where 1.0 is "normal" (default) thickness.
    visibility : bool
      Whether or not to display the label.
    mid_point : numeric two-tuple
        If given, the arrow will be curved.  The curve will be determined by taking a straight line
        through the 'start' and 'end' points and determining the distance from 'mid_point' to that
        line.  The arrow will be curved by that amount to the appropriate side (and therefore may not
        actually go through 'mid_point').
    head_style : string; "blocky", "solid", "pointy", or "pointer"
        Style of arrowhead.
    '''
    if name == 'all':
        from chimerax.core.errors import UserError
        raise UserError("'all' is reserved to refer to all arrows")

    kw = {
        'start': start,
        'end': end,
        'weight': weight,
        'visibility': visibility,
        'mid_point': mid_point,
        'head_style': head_style
    }

    from chimerax.core.colors import Color
    if isinstance(color, Color):
        kw['color'] = color.uint8x4()
    elif color == 'default':
        kw['color'] = None

    return Arrow(session, name, **kw)


def arrow_change(session, arrows, *, color=None, weight=None,
                 start=None, end=None, visibility=None, mid_point=None, head_style=None, frames=None):
    '''Change label parameters.'''
    kw = {
        'color': color,
        'weight': weight,
        'start': start,
        'end': end,
        'visibility': visibility,
        'mid_point': mid_point,
        'head_style': head_style,
        'frames': frames
    }
    return [_update_arrow(session, a, **kw) for a in arrows]


def _update_arrow(session, a, *, color=None, weight=None,
                 start=None, end=None, visibility=None, mid_point=None, head_style=None, frames=None):
    if head_style is not None: a.head_style = head_style
    if frames is None:
        if color is not None:
            a.color = None if color == 'default' else color.uint8x4()
        if weight is not None: a.weight = weight
        if start is not None: a.start = start
        if end is not None: a.end = end
        if visibility is not None: a.visibility = visibility
        if mid_point == 'none':
            a.mid_point = None
        elif mid_point is not None:
            a.mid_point = mid_point
        a.update_drawing()
    else:
        _InterpolateArrow(session, a, color, weight, start, end, visibility, mid_point, frames)


class _InterpolateArrow:
    def __init__(self, session, arrow, color, weight, start, end, visibility, mid_point, frames):
        self.arrow = arrow
        from numpy import array_equal
        # even if color/background not changing, need color1/2 and bg1/2 for visibility changes
        from numpy import array, uint8
        self.orig_color1 = None if arrow.color is None else arrow.color.copy()
        self.color1, self.color2 = array(arrow.drawing.arrow_color, dtype=uint8), (color.uint8x4()
            if color else color)
        if color is None:
            # no change
            self.interp_color = False
        else:
            color2 = None if color == 'none' else color.uint8x4()
            if array_equal(arrow.color, color2):
                self.interp_color = False
            else:
                self.interp_color = True
        self.weight1, self.weight2 = arrow.weight, weight
        self.start1, self.start2 = arrow.start, start
        self.end1, self.end2 = arrow.end, end
        self.visibility1, self.visibility2 = arrow.visibility, visibility
        if visibility is not None and self.visibility1 != self.visibility2:
            if self.arrow.color is None:
                # need to interpolate alpha, so set it to a real color;
                # the last frame will set it to the right final value
                self.arrow.color = array(self.arrow.drawing.arrow_color, dtype=uint8)
        if mid_point == 'none':
            if arrow.mid_point is None:
                self.interp_midpoint = False
            else:
                self.interp_midpoint = True
        elif mid_point is None:
            self.interp_midpoint = False
        else:
            self.interp_midpoint = True
        self.mid_point1, self.mid_point2 = arrow.mid_point, mid_point
        self.frames = frames
        from chimerax.core.commands import motion
        motion.CallForNFrames(self.frame_cb, frames, session)

    def frame_cb(self, session, frame):
        fraction = frame / (self.frames-1)
        from numpy import array_equal
        if self.interp_color:
            if frame == self.frames-1:
                self.arrow.color = self.color2
            else:
                self.arrow.color = ((1 - fraction) * self.color1
                    + fraction * self.color2).astype(self.color1.dtype)
        if self.weight2 is not None and self.weight1 != self.weight2:
            if frame == self.frames-1:
                self.arrow.weight = self.weight2
            else:
                self.arrow.weight = (1 - fraction) * self.weight1 + fraction * self.weight2
        if self.start2 is not None and self.start1 != self.start2:
            if frame == self.frames-1:
                self.arrow.start = self.start2
            else:
                x1, y1 = self.start1
                x2, y2 = self.start2
                self.arrow.start = ((1 - fraction) * x1 + fraction * x2,
                    (1 - fraction) * y1 + fraction * y2)
        if self.end2 is not None and self.end1 != self.end2:
            if frame == self.frames-1:
                self.arrow.end = self.end2
            else:
                x1, y1 = self.end1
                x2, y2 = self.end2
                self.arrow.end = ((1 - fraction) * x1 + fraction * x2,
                    (1 - fraction) * y1 + fraction * y2)
        if self.visibility2 is not None and self.visibility1 != self.visibility2:
            if frame == self.frames-1:
                self.arrow.visibility = self.visibility2
                self.arrow.color = self.orig_color1 if self.color2 is None else self.color2
            else:
                # fake gradual change in visibility via alpha channel
                if self.visibility2:
                    # becoming shown
                    self.arrow.color[-1] = self.color1[-1] * fraction
                else:
                    # becoming hidden
                    self.arrow.color[-1] = self.color1[-1] * (1 - fraction)
                self.arrow.visibility = True
        if self.interp_midpoint:
            if frame == self.frames-1:
                self.arrow.mid_point = self.mid_point2
            else:
                if self.mid_point2 is None:
                    # going to straight line from curved
                    mx1, my1 = self.mid_point1
                    mx2 = (self.arrow.start[0] + self.arrow.end[0]) / 2
                    my2 = (self.arrow.start[1] + self.arrow.end[1]) / 2
                elif self.mid_point1 is None:
                    # going from straight line to curved
                    mx1 = (self.arrow.start[0] + self.arrow.end[0]) / 2
                    my1 = (self.arrow.start[1] + self.arrow.end[1]) / 2
                    mx2, my2 = self.mid_point2
                else:
                    # going from one curve to another
                    mx1, my1 = self.mid_point1
                    mx2, my2 = self.mid_point2
                self.arrow.mid_point = ((1 - fraction) * mx1 + fraction * mx2,
                    (1 - fraction) * my1 + fraction * my2)
        self.arrow.update_drawing()


# -----------------------------------------------------------------------------
# TODO: more precision
def arrow_under_window_position(session, win_x, win_y):
    w,h = session.main_view.window_size
    fx,fy = (win_x+.5)/w, 1-(win_y+.5)/h    # win_y is 0 at top
    lm = session_arrows(session)
    if lm is None:
        return None
    for arr in lm.all_arrows:
        dx,dy = fx - arr.xpos, fy - arr.ypos
        lw,lh = arr.drawing.size
        if dx >=0 and dx < lw and dy >=0 and dy < lh:
            return arr
    return None


def arrow_delete(session, arrows = None):
    '''Delete arrow.'''
    if arrows is None:
        lm = session_arrows(session)
        arrows = lm.all_arrows if lm else ()
    for a in tuple(arrows):
        a.delete()


from chimerax.core.commands import Annotation
class NamedArrowsArg(Annotation):

    name = "'all' or a 2d arrow name"
    _html_name = "<b>all</b> or a 2d arrow name"

    @staticmethod
    def parse(text, session):
        from chimerax.core.commands import AnnotationError, next_token
        if not text:
            raise AnnotationError("Expected %s" % NamedArrowsArg.name)
        lm = session_arrows(session)
        token, text, rest = next_token(text)
        if lm.named_arrow(token) is None:
            possible = [name for name in lm.arrow_names() if name.startswith(token)]
            if 'all'.startswith(token):
                possible.append('all')
            if not possible:
                raise AnnotationError("Unknown arrow identifier: '%s'" % token)
            possible.sort(key=len)
            token = possible[0]
        arrows = lm.all_arrows if token == 'all' else [lm.named_arrow(token)]
        return arrows, token, rest


from chimerax.core.commands import ModelsArg
class ArrowsArg(ModelsArg):
    """Parse command arrow model specifier"""
    name = "an arrow models specifier"

    @classmethod
    def parse(cls, text, session):
        models, text, rest = super().parse(text, session)
        arrows = [m.arrow for m in models if isinstance(m, ArrowModel)]
        return arrows, text, rest


def register_arrow_command(logger):

    from chimerax.core.commands import CmdDesc, register, Or, BoolArg, IntArg, StringArg, FloatArg, ColorArg
    from chimerax.core.commands import Float2Arg, EnumOf
    from .label3d import DefArg, NoneArg

    arrows_arg = [('arrows', Or(NamedArrowsArg, ArrowsArg))]
    start_end_args = [('start', Float2Arg), ('end', Float2Arg)]
    # Create and change have same arguments
    common_args = [('color', Or(DefArg, ColorArg)),
             ('weight', FloatArg),
             ('visibility', BoolArg),
             ('head_style', EnumOf(("blocky", "solid", "pointy", "pointer")))]
    create_desc = CmdDesc(
        required=[('name', StringArg)] + start_end_args,
        keyword=[('mid_point', Float2Arg)] + common_args,
        synopsis='Create a 2d arrow')
    register('2dlabels acreate', create_desc, arrow_create, logger=logger)
    change_desc = CmdDesc(
        required=arrows_arg,
        keyword=common_args + start_end_args + [('mid_point', Or(NoneArg, Float2Arg)), ('frames', IntArg)],
        synopsis='Change a 2d arrow')
    register('2dlabels achange', change_desc, arrow_change, logger=logger)
    delete_desc = CmdDesc(optional=arrows_arg, synopsis = 'Delete a 2d arrow')
    register('2dlabels adelete', delete_desc, arrow_delete, logger=logger)


from chimerax.core.models import Model
class Arrows(Model):
    def __init__(self, session):
        Model.__init__(self, '2D arrows', session)
        self._arrows = []
        self._named_arrows = {}    # Map arrow name to Arrow object
        from chimerax.core.core_settings import settings
        settings.triggers.add_handler('setting changed', self._background_color_changed)
        session.main_view.add_overlay(self)
        self.model_panel_show_expanded = False

    def delete(self):
        self.session.main_view.remove_overlays([self], delete = False)
        Model.delete(self)

    def add_arrow(self, arrow):
        self._arrows.append(arrow)
        n = arrow.name
        if n:
            nl = self._named_arrows.get(n)
            if nl:
                nl.delete()
            self._named_arrows[n] = arrow
        self.add([arrow.drawing])

    @property
    def all_arrows(self):
        return self._arrows

    def named_arrow(self, name):
        return self._named_arrows.get(name)

    def arrow_names(self):
        return tuple(self._named_arrows.keys())

    def delete_arrow(self, arrow):
        if arrow.name:
            del self._named_arrows[arrow.name]
        self._arrows.remove(arrow)
        if len(self._arrows) == 0:
            self.delete()

    def _background_color_changed(self, tname, tdata):
        # Update arrow color when graphics background color changes.
        if tdata[0] == 'background_color':
            for a in self.all_arrows:
                if a.color is None:
                    a.update_drawing()

    SESSION_SAVE = True

    def take_snapshot(self, session, flags):
        lattrs = ('name', 'color', 'weight', 'head_style',
                  'start', 'end', 'mid_point', 'visibility')
        lstate = tuple({attr:getattr(a, attr) for attr in lattrs}
                       for a in self.all_arrows)
        data = {'arrows state': lstate,
                'model state': Model.take_snapshot(self, session, flags),
                'version': 1}
        return data

    @staticmethod
    def restore_snapshot(session, data):
        s = Arrows(session)
        Model.set_state_from_snapshot(s, session, data['model state'])
        session.models.add([s], root_model = True)
        s.set_state_from_snapshot(session, data)
        return s

    def set_state_from_snapshot(self, session, data):
        self._arrows = [Arrow(session, **ls) for ls in data['arrows state']]
        self._named_arrows = {a.name:a for a in self._arrows if a.name}


def find_arrow(session, name):
    lm = session_arrows(session)
    return lm.named_arrow(name) if lm else None

def all_arrows(session):
    lm = session_arrows(session)
    return lm.all_arrows if lm else []

def session_arrows(session, create=False):
    lmlist = session.models.list(type=Arrows)
    if lmlist:
        lm = lmlist[0]
    elif create:
        lm = Arrows(session)
        session.models.add([lm], root_model = True)
    else:
        lm = None
    return lm


class Arrow:
    def __init__(self, session, name, color=None, weight=1.0, start=(0.0, 0.0), end=(1.0, 1.0),
            mid_point=None, visibility=True, head_style="solid"):
        self.session = session
        self.name = name
        self.color = color
        self.weight = weight
        self.start = start
        self.end = end
        self.visibility = visibility
        self.mid_point = mid_point
        self.head_style = head_style
        self.drawing = d = ArrowModel(session, self)
        lb = session_arrows(session, create = True)
        lb.add_arrow(self)

    def update_drawing(self):
        d = self.drawing
        d.needs_update = True
        # Used to be in ArrowModel.update_drawing(), but that doesn't get called if display is False!
        d.display = self.visibility
        d.redraw_needed()

    def delete(self):
        d = self.drawing
        if d is None:
            return
        self.drawing = None
        d.delete()
        lm = session_arrows(self.session)
        if lm:
            lm.delete_arrow(self)


from chimerax.core.models import Model
class ArrowModel(Model):

    pickable = False
    casts_shadows = False
    SESSION_SAVE = False	# ArrowsModel saves all arrows

    STD_HALF_WIDTH = 0.01
    PIXEL_MARGIN = 5

    def __init__(self, session, arrow):
        Model.__init__(self, arrow.name, session)
        self.arrow = arrow
        self.window_size = None
        self.texture_size = None
        self.needs_update = True

    def draw(self, renderer, draw_pass):
        if not self.update_drawing():
            self.resize()
        Model.draw(self, renderer, draw_pass)

    @property
    def arrow_color(self):
        a = self.arrow
        if a.color is None:
            bg = [255*r for r in a.session.main_view.background_color]
            light_bg = (sum(bg[:3]) > 1.5*255)
            rgba8 = (0,0,0,255) if light_bg else (255,255,255,255)
        else:
            rgba8 = tuple(a.color)
        return rgba8

    def _get_single_color(self):
        return self.arrow_color
    def _set_single_color(self, color):
        a = self.arrow
        a.color = color
        a.update_drawing()
    single_color = property(_get_single_color, _set_single_color)

    def update_drawing(self):
        if not self.needs_update:
            return False
        self.needs_update = False
        a = self.arrow
        rgba = self.arrow_image_rgba()
        if rgba is None:
            a.session.logger.info("Can't find font for arrow")
            return True
        self.set_arrow_image(rgba)
        return True

    def arrow_params(self, width, height):
        scale_factor = min(width, height)
        sx, sy = self.arrow.start[0] * width, self.arrow.start[1] * height
        ex, ey = self.arrow.end[0] * width, self.arrow.end[1] * height

        if abs(ex-sx) < 18 and abs(ey-sy) < 18:
            return None, None

        half_width = scale_factor * self.STD_HALF_WIDTH * self.arrow.weight

        if self.arrow.mid_point:
            # curved arrow
            from chimerax.core.errors import LimitationError
            raise LimitationError("Curved arrows not implemented yet")

        # straight arrow
        vx, vy = ex - sx, ey - sy
        arrow_len_sq = vx * vx + vy * vy
        from math import sqrt
        arrow_len = sqrt(arrow_len_sq)
        norm_x, norm_y = vx/arrow_len, vy/arrow_len
        perp_x, perp_y = norm_y, -norm_x
        ext1, ext2 = perp_x * half_width, perp_y * half_width
        # tail end of arrow ("base")
        base1, base2 = (sx + ext1, sy + ext2), (sx - ext1, sy - ext2)

        # where shaft meets arrowhead ("inside")
        head_width = 4 * half_width
        cut_back = arrow_len - 2 * half_width
        extx, exty = norm_x * cut_back, norm_y * cut_back
        x1, y1 = base1
        x2, y2 = base2
        inside1, inside2 = (x1 + extx, y1 + exty), (x2 + extx, y2 + exty)

        left = min(base1[0], base2[0], inside1[0], inside2[0])
        right = max(base1[0], base2[0], inside1[0], inside2[0])
        bottom = min(base1[1], base2[1], inside1[1], inside2[1])
        top = max(base1[1], base2[1], inside1[1], inside2[1])

        return ((left, right, bottom, top), (base1, base2, inside2, inside1)), \
            (((inside1[0] + inside2[0])/2, (inside1[1] + inside2[1])/2), (norm_x, norm_y))

    def head_params(self, head_start, width, height):
        start_pos, norm = head_start
        perp = norm[1], -norm[0]
        style = self.arrow.head_style
        scale_factor = min(width, height)
        half_width = self.STD_HALF_WIDTH * self.arrow.weight * scale_factor
        ex, ey = width * self.arrow.end[0], height * self.arrow.end[1]
        bounding_pts = [(ex, ey)]
        if style == "pointer":
            bounding_pts.append((start_pos[0] + half_width * perp[0], start_pos[1] + half_width * perp[1]))
            bounding_pts.append((start_pos[0] - half_width * perp[0], start_pos[1] - half_width * perp[1]))
        else:
            head_width = 4 * half_width
            head_back = (ex - norm[0] * head_width, ey - norm[1] * head_width)
            bounding_pts.append((head_back[0] + head_width * perp[0], head_back[1] + head_width * perp[1]))
            bounding_pts.append((head_back[0] - head_width * perp[0], head_back[1] - head_width * perp[1]))
            # even though the "blocky" style has an extra corner, that corner can never be on the
            # bounding box of the overall arrow, so we can ignore it for this routine
        xs = [pt[0] for pt in bounding_pts]
        ys = [pt[1] for pt in bounding_pts]
        return min(xs), max(xs), min(ys), max(ys)

    def arrow_image_rgba(self):
    #TODO: same techniques as chimerax.core.graphics.text_image_rgba, but using QPainter's arc drawing
    # plus: remainder of this file

        w, h = self.arrow.session.main_view.window_size
        shaft_info, head_start = self.arrow_params(w, h)
        if head_start is None:
            # too short to draw
            return None
        shaft_bounds, shaft_geom = shaft_info
        s_left, s_right, s_bottom, s_top = shaft_bounds
        h_left, h_right, h_bottom, h_top = self.head_params(head_start, w, h)

        left = min(s_left, h_left)
        right = max(s_right, h_right)
        bottom = min(s_bottom, h_bottom)
        top = max(s_top, h_top)
        self.xpos = left / w
        self.ypos = bottom / h

        from PyQt5.QtGui import QImage, QPainter, QColor, QBrush, QPen

        image = QImage(int((right-left))+2*self.PIXEL_MARGIN, int((top-bottom))+2*self.PIXEL_MARGIN,
            QImage.Format_ARGB32)
        image.fill(QColor(0,0,0,0))    # Set background transparent

        with QPainter(image) as p:
            p.setRenderHint(QPainter.Antialiasing)
            bcolor = QColor(*self.arrow_color)
            from PyQt5.QtCore import Qt, QPointF
            pbr = QBrush(bcolor, Qt.SolidPattern)
            p.setBrush(pbr)
            ppen = QPen(Qt.NoPen)
            p.setPen(ppen)
            def image_xy(float_xy, l=left, t=top):
                x, y = float_xy
                # image y axis points down
                return (self.PIXEL_MARGIN + (x-l), self.PIXEL_MARGIN + (t-y))
            if len(shaft_geom) == 4:
                p.drawPolygon(*[QPointF(*image_xy(xy)) for xy in shaft_geom])
            else:
                #TODO: draw arc
                pass
            
            start_pos, norm = head_start
            scale_factor = min(w,h)
            half_width = scale_factor * self.STD_HALF_WIDTH * self.arrow.weight
            if self.arrow.head_style == "solid":
                head_width = 4 * half_width
                ex, ey = self.arrow.end[0] * w, self.arrow.end[1] * h
                head_back = (ex - norm[0] * head_width, ey - norm[1] * head_width)
                perp = norm[1], -norm[0]
                edge1 = (head_back[0] + head_width * perp[0], head_back[1] + head_width * perp[1])
                edge2 = (head_back[0] - head_width * perp[0], head_back[1] - head_width * perp[1])
                p.drawPolygon(*[QPointF(*image_xy(xy)) for xy in [edge1, edge2, (ex, ey)]])
            elif self.arrow.head_style == "blocky":
                pass
            #TODO: other head styles

            # Convert to numpy rgba array.
            from chimerax.core.graphics import qimage_to_numpy
            rgba = qimage_to_numpy(image)

        return rgba

    def set_arrow_image(self, rgba):
        x,y = (-1 + 2*self.xpos, -1 + 2*self.ypos)    # Convert 0-1 position to -1 to 1.
        v = self.arrow.session.main_view
        self.window_size = w,h = v.window_size
        th, tw = rgba.shape[:2]
        self.texture_size = (tw,th)
        uw,uh = 2*tw/w, 2*th/h
        from chimerax.core.graphics.drawing import rgba_drawing
        rgba_drawing(self, rgba, (x, y), (uw, uh), opaque = False)

    @property
    def size(self):
        '''Arrow size as fraction of window size (0-1).'''
        w,h = self.window_size
        tw,th = self.texture_size
        return (tw/w, th/h)

    def resize(self):
        a = self.arrow
        v = a.session.main_view
        if v.window_size != self.window_size:
            # Window has resized so update texture drawing size
            self.needs_update = True
            self.window_size = v.window_size

    def x3d_needs(self, x3d_scene):
        from .. import x3d
        x3d_scene.need(x3d.Components.Text, 1)  # Text

    def custom_x3d(self, stream, x3d_scene, indent, place):
        # TODO
        pass