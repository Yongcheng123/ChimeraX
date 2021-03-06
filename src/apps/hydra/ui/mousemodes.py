class MouseModes:

    def __init__(self, graphics_window, session):

        self.graphics_window = graphics_window
        self.session = session
        self.view = graphics_window.view

        self.mouse_modes = {}           # Maps 'left', 'middle', 'right', 'wheel', 'pause' to MouseMode instance

        # Mouse pause parameters
        self.last_mouse_time = None
        self.mouse_pause_interval = 0.5         # seconds
        self.mouse_pause_position = None

        self.bind_standard_mouse_modes()

        self.set_mouse_event_handlers()

        self.trackpad_speed = 4         # Trackpad position scaling to match mouse position sensitivity
        self.trackpad_xy = None

    def cursor_position(self):
        import wx
        return self.graphics_window.ScreenToClient(wx.GetMousePosition())

    def bind_standard_mouse_modes(self, buttons = ('left', 'middle', 'right', 'wheel', 'pause')):
        modes = (
            ('left', RotateMouseMode),
            ('middle', TranslateMouseMode),
            ('right', TranslateMouseMode),
            ('wheel', ZoomMouseMode),
            ('pause', ObjectIdMouseMode),
            )
        s = self.session
        for button, mode_class in modes:
            if button in buttons:
                self.bind_mouse_mode(button, mode_class(s))

    # Button is "left", "middle", "right", "wheel", or "pause"
    def bind_mouse_mode(self, button, mode):
        self.mouse_modes[button] = mode

    def wheel_event(self, event):
        if self.is_trackpad_wheel_event(event):
            return
        f = self.mouse_modes.get('wheel')
        if f:
            f.wheel(self.MouseEvent(event))

    def is_trackpad_wheel_event(self, event):
        # Suppress trackpad wheel events when using multitouch
        # Ignore scroll events generated by the Mac trackpad (2-finger drag).
        # There seems to be no reliable way to tell if a scroll came from the trackpad.
        # Scrolls from the Apple Magic Mouse look like a trackpad scroll.
        # Only way to tell true trackpad events seems to be to look at trackpad touches.
        if getattr(self, 'last_trackpad_touch_count', 0) >= 2:
            return True # Ignore trackpad generated scroll
        if hasattr(self, 'last_trackpad_touch_time'):
            import time
            if time.time() < self.last_trackpad_touch_time + 1.0:
                # Suppress momentum scrolling for 1 second after trackpad scrolling ends.
                return True
        return False

    def mouse_pause_tracking(self):
        cp = self.cursor_position()
        w,h = self.view.window_size
        x,y = cp
        if x < 0 or y < 0 or x >= w or y >= h:
            return      # Cursor outside of graphics window
        from time import time
        t = time()
        mp = self.mouse_pause_position
        if cp == mp:
            lt = self.last_mouse_time
            if lt and t >= lt + self.mouse_pause_interval:
                self.mouse_pause()
                self.mouse_pause_position = None
                self.last_mouse_time = None
            return
        self.mouse_pause_position = cp
        if mp:
            # Require mouse move before setting timer to avoid
            # repeated mouse pause callbacks at same point.
            self.last_mouse_time = t

    def mouse_pause(self):
        m = self.mouse_modes.get('pause')
        if m:
            m.pause(self.mouse_pause_position)

    def process_touches(self, touches):
        min_pinch = 0.1
        n = len(touches)
        import time
        self.last_trackpad_touch_time = time.time()
        self.last_trackpad_touch_count = n
        s = self.trackpad_speed
        moves = [(id, s*(x-lx), s*(y-ly)) for id,x,y,lx,ly in touches]
        if n == 2:
            (dx0,dy0),(dx1,dy1) = moves[0][1:], moves[1][1:]
            from math import sqrt, exp, atan2, pi
            l0,l1 = sqrt(dx0*dx0 + dy0*dy0),sqrt(dx1*dx1 + dy1*dy1)
            d12 = dx0*dx1+dy0*dy1
            if l0 >= min_pinch and l1 >= min_pinch and d12 < -0.7*l0*l1:
                # pinch or twist
                (x0,y0),(x1,y1) = [t[1:3] for t in touches[:2]]
                sx,sy = x1-x0,y1-y0
                sn = sqrt(sx*sx + sy*sy)
                sd0,sd1 = sx*dx0 + sy*dy0, sx*dx1 + sy*dy1
                if abs(sd0) > 0.5*sn*l0 and abs(sd1) > 0.5*sn*l1:
                    # pinch to zoom
                    s = 1 if sd1 > 0 else -1
                    tm = [m for m in self.mouse_modes.values() if isinstance(m, TranslateMouseMode)]
                    if tm:
                        tm[0].translate((0,0,10*s*(l0+l1)))
                    return
                else:
                    # twist
                    a = (atan2(-sy*dx1+sx*dy1,sn*sn) +
                         atan2(sy*dx0-sx*dy0,sn*sn))*180/pi
                    zaxis = (0,0,1)
                    rm = [m for m in self.mouse_modes.values() if isinstance(m, RotateMouseMode)]
                    if rm:
                        rm[0].rotate(zaxis, -3*a)
                    return
            dx = sum(x for id,x,y in moves)
            dy = sum(y for id,x,y in moves)
            # rotation
            from math import sqrt
            angle = 0.3*sqrt(dx*dx + dy*dy)
            if angle != 0:
                axis = (dy, dx, 0)
                rm = [m for m in self.mouse_modes.values() if isinstance(m, RotateMouseMode)]
                if rm:
                    rm[0].rotate(axis, angle)
        elif n == 3:
            dx = sum(x for id,x,y in moves)/n
            dy = sum(y for id,x,y in moves)/n
            # translation
            if dx != 0 or dy != 0:
                m = self.mouse_modes.get('right')
                if m:
                    if self.trackpad_xy is None:
                        self.trackpad_xy = self.cursor_position()
                        action = 'mouse_down'
                    else:
                        x,y = self.trackpad_xy
                        self.trackpad_xy = (x+dx, y+dy)
                        action = 'mouse_drag'
                    e = self.trackpad_event(*self.trackpad_xy)
                    getattr(m, action)(e)

class MouseMode:

    def __init__(self, session):
        self.session = session
        self.view = session.view

        self.mouse_down_position = None
        self.last_mouse_position = None

    def mouse_down(self, event):
        pos = event.position()
        self.mouse_down_position = pos
        self.last_mouse_position = pos

    def mouse_up(self, event):
        self.mouse_down_position = None
        self.last_mouse_position = None

    def mouse_motion(self, event):
        lmp = self.last_mouse_position
        x, y = pos = event.position()
        if lmp is None:
            dx = dy = 0
        else:
            dx = x - lmp[0]
            dy = y - lmp[1]
            # dy > 0 is downward motion.
        self.last_mouse_position = pos
        return dx, dy

    def wheel(self):
        pass

    def pause(self, position):
        pass

    def pixel_size(self, min_scene_frac = 1e-5):
        return pixel_size(self.view, min_scene_frac)

def pixel_size(view, min_scene_frac = 1e-5):
    psize = view.pixel_size()
    b = view.drawing_bounds()
    if not b is None:
        w = b.width()
        psize = max(psize, w*min_scene_frac)
    return psize

class RotateMouseMode(MouseMode):

    def __init__(self, session):
        MouseMode.__init__(self, session)
        self.mouse_perimeter = False

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        x,y = event.position()
        w,h = self.view.window_size
        cx, cy = x-0.5*w, y-0.5*h
        fperim = 0.9
        self.mouse_perimeter = (abs(cx) > fperim*0.5*w or abs(cy) > fperim*0.5*h)

    def mouse_up(self, event):
        if event.position() == self.mouse_down_position:
            self.mouse_select(event)
        MouseMode.mouse_up(self, event)

    def mouse_drag(self, event):
        axis, angle = self.mouse_rotation(event)
        self.rotate(axis, angle)

    def rotate(self, axis, angle):
        v = self.view
        # Convert axis from camera to scene coordinates
        saxis = v.camera.position.apply_without_translation(axis)
        v.rotate(saxis, angle, self.models())

    def mouse_rotation(self, event):

        dx, dy = self.mouse_motion(event)
        import math
        angle = 0.5*math.sqrt(dx*dx+dy*dy)
        if self.mouse_perimeter:
            # z-rotation
            axis = (0,0,1)
            w, h = self.view.window_size
            x, y = event.position()
            ex, ey = x-0.5*w, y-0.5*h
            if -dy*ex+dx*ey < 0:
                angle = -angle
        else:
            axis = (dy,dx,0)
        return axis, angle

    def models(self):
        return None

    def mouse_select(self, event):

        x,y = event.position()
        v = self.view
        p, pick = v.first_intercept(x,y)
        ses = self.session
        toggle = event.shift_down()
        if pick is None:
            if not toggle:
                ses.clear_selection()
                ses.logger.status('cleared selection')
        else:
            if not toggle:
                ses.clear_selection()
            pick.select(toggle)
        ses.clear_selection_hierarchy()

class RotateSelectedMouseMode(RotateMouseMode):

    def models(self):
        m = self.session.selected_models()
        return None if len(m) == 0 else m

class TranslateMouseMode(MouseMode):

    def mouse_drag(self, event):

        dx, dy = self.mouse_motion(event)
        self.translate((dx, -dy, 0))

    def translate(self, shift):

        psize = self.pixel_size()
        s = tuple(dx*psize for dx in shift)     # Scene units
        v = self.view
        step = v.camera.position.apply_without_translation(s)    # Scene coord system
        v.translate(step, self.models())

    def models(self):
        return None

class TranslateSelectedMouseMode(TranslateMouseMode):

    def models(self):
        m = self.session.selected_models()
        return None if len(m) == 0 else m

class ZoomMouseMode(MouseMode):

    def mouse_drag(self, event):        

        dx, dy = self.mouse_motion(event)
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.position.apply_without_translation((0, 0, 3*psize*dy))
        v.translate(shift)

    def wheel(self, event):
        import sys
        d = event.wheel_value()
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.position.apply_without_translation((0, 0, 100*d*psize))
        v.translate(shift)

class ObjectIdMouseMode(MouseMode):

    def pause(self, position):
        x,y = position
        f, p = self.view.first_intercept(x,y)
        if p:
            self.session.logger.status('Mouse over %s' % p.description())
        # TODO: Clear status if it is still showing mouse over message but mouse is over nothing.
        #      Don't want to clear a different status message, only mouse over message.
