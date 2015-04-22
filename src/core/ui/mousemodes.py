class MouseModes:

    def __init__(self, graphics_window, session):

        self.graphics_window = graphics_window
        self.session = session
        self.view = graphics_window.view
        self.mouse_modes = {}
        self.mouse_down_position = None
        self.last_mouse_position = None
        self.last_mouse_time = None
        self.mouse_pause_interval = 0.5         # seconds
        self.mouse_pause_position = None
        self.mouse_perimeter = False
        self.wheel_function = None
        self.bind_standard_mouse_modes()

        self.move_selected = False

        self.set_mouse_event_handlers()

        self.trackpad_speed = 4         # Trackpad position scaling to match mouse position sensitivity
    
    def set_mouse_event_handlers(self):
        pass
    def event_position(self, event):
        return (0,0)

    def bind_standard_mouse_modes(self, buttons = ['left', 'middle', 'right', 'wheel']):
        modes = (
            ('left', self.mouse_down, self.mouse_rotate, self.mouse_up_select),
            ('middle', self.mouse_down, self.mouse_translate, self.mouse_up),
            ('right', self.mouse_down, self.mouse_zoom, self.mouse_up),
            )
        for m in modes:
            if m[0] in buttons:
                self.bind_mouse_mode(*m)
        if 'wheel' in buttons:
            self.wheel_function = self.wheel_zoom

    # Button is "left", "middle", or "right"
    def bind_mouse_mode(self, button, mouse_down,
                        mouse_drag = None, mouse_up = None):
        self.mouse_modes[button] = (mouse_down, mouse_drag, mouse_up)

    def wheel_event(self, event):
        if self.is_trackpad_wheel_event(event):
            return
        f = self.wheel_function
        if f:
            f(event)

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

    def mouse_down(self, event):
        w,h = self.view.window_size
        x,y = pos = self.event_position(event)
        cx, cy = x-0.5*w, y-0.5*h
        fperim = 0.9
        self.mouse_perimeter = (abs(cx) > fperim*0.5*w or abs(cy) > fperim*0.5*h)
        self.mouse_down_position = pos
        self.last_mouse_position = pos

    def mouse_up(self, event):
        self.mouse_down_position = None
        self.last_mouse_position = None

    def mouse_up_select(self, event):
        if self.event_position(event) == self.mouse_down_position:
            self.mouse_select(event)
        self.mouse_down_position = None
        self.last_mouse_position = None

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
        lp = self.mouse_pause_position
        f, p = self.view.first_intercept(*lp)
        if p:
            self.session.logger.status('Mouse over %s' % p.description())
        # TODO: Clear status if it is still showing mouse over message but mouse is over nothing.
        #      Don't want to clear a different status message, only mouse over message.

    def mouse_motion(self, event):
        lmp = self.last_mouse_position
        x, y = pos = self.event_position(event)
        if lmp is None:
            dx = dy = 0
        else:
            dx = x - lmp[0]
            dy = y - lmp[1]
            # dy > 0 is downward motion.
        self.last_mouse_position = pos
        return dx, dy

    def mouse_rotate(self, event):
        axis, angle = self.mouse_rotation(event)
        self.rotate(axis, angle)

    def rotate(self, axis, angle):
        v = self.view
        # Convert axis from camera to scene coordinates
        saxis = v.camera.position.apply_without_translation(axis)
        v.rotate(saxis, angle, self.models())

    def models(self):
        if self.move_selected:
            m = self.session.selected_models()
            if len(m) == 0:
                m = None
        else:
            m = None
        return m

    def mouse_rotation(self, event):

        dx, dy = self.mouse_motion(event)
        import math
        angle = 0.5*math.sqrt(dx*dx+dy*dy)
        if self.mouse_perimeter:
            # z-rotation
            axis = (0,0,1)
            w, h = self.view.window_size
            ex, ey = event.x()-0.5*w, event.y()-0.5*h
            if -dy*ex+dx*ey < 0:
                angle = -angle
        else:
            axis = (dy,dx,0)
        return axis, angle

    def mouse_translate(self, event):

        dx, dy = self.mouse_motion(event)
        self.translate((dx, -dy, 0))

    def translate(self, shift):

        psize = self.pixel_size()
        s = tuple(dx*psize for dx in shift)     # Scene units
        v = self.view
        step = v.camera.position.apply_without_translation(s)    # Scene coord system
        v.translate(step, self.models())

    def mouse_zoom(self, event):        

        dx, dy = self.mouse_motion(event)
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.position.apply_without_translation((0, 0, 3*psize*dy))
        v.translate(shift)

    def wheel_zoom(self, event):
        import sys
        d = self.wheel_value(event)
        psize = self.pixel_size()
        v = self.view
        shift = v.camera.position.apply_without_translation((0, 0, 100*d*psize))
        v.translate(shift)

    def pixel_size(self, min_scene_frac = 1e-5):
        v = self.view
        psize = v.pixel_size()
        b = v.drawing_bounds()
        if not b is None:
            w = b.width()
            psize = max(psize, w*min_scene_frac)
        return psize

    def mouse_select(self, event):

        x,y = self.event_position(event)
        v = self.view
        p, pick = v.first_intercept(x,y)
        ses = self.session
        toggle = self.shift_down(event)
        if pick is None:
            if not toggle:
                ses.selection.clear()
                ses.logger.status('cleared selection')
        else:
            if not toggle:
                ses.selection.clear()
            pick.select(toggle)
        ses.selection.clear_hierarchy()

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
                    self.translate((0,0,10*s*(l0+l1)))
                    return
                else:
                    # twist
                    a = (atan2(-sy*dx1+sx*dy1,sn*sn) +
                         atan2(sy*dx0-sx*dy0,sn*sn))*180/pi
                    zaxis = (0,0,1)
                    self.rotate(zaxis, -3*a)
                    return
            dx = sum(x for id,x,y in moves)
            dy = sum(y for id,x,y in moves)
            # rotation
            from math import sqrt
            angle = 0.3*sqrt(dx*dx + dy*dy)
            if angle != 0:
                axis = (dy, dx, 0)
                self.rotate(axis, angle)
        elif n == 3:
            dx = sum(x for id,x,y in moves)
            dy = sum(y for id,x,y in moves)
            # translation
            if dx != 0 or dy != 0:
                f = self.mouse_modes.get('right')
                if f:
                    fnum = 0 if self.last_mouse_position is None else 1 # 0 = down, 1 = drag, 2 = up
                    e = self.trackpad_event(dx,dy)
                    f[fnum](e)
                    self.last_mouse_position = self.event_position(e)

class WxMouseModes(MouseModes):

    def set_mouse_event_handlers(self):
        import wx
        gw = self.graphics_window
        gw.opengl_canvas.Bind(wx.EVT_LEFT_DOWN,
            lambda e: self.dispatch_mouse_event(e, "left", 0))
        gw.opengl_canvas.Bind(wx.EVT_MIDDLE_DOWN,
            lambda e: self.dispatch_mouse_event(e, "middle", 0))
        gw.opengl_canvas.Bind(wx.EVT_RIGHT_DOWN,
            lambda e: self.dispatch_mouse_event(e, "right", 0))
        gw.opengl_canvas.Bind(wx.EVT_MOTION,
            lambda e: self.dispatch_mouse_event(e, None, 1))
        gw.opengl_canvas.Bind(wx.EVT_LEFT_UP,
            lambda e: self.dispatch_mouse_event(e, "left", 2))
        gw.opengl_canvas.Bind(wx.EVT_MIDDLE_UP,
            lambda e: self.dispatch_mouse_event(e, "middle", 2))
        gw.opengl_canvas.Bind(wx.EVT_RIGHT_UP,
            lambda e: self.dispatch_mouse_event(e, "right", 2))
        gw.opengl_canvas.Bind(wx.EVT_MOUSEWHEEL, self.wheel_event)

    def dispatch_mouse_event(self, event, button, fnum):
        if fnum == 0:
            # remember button for later drag events
            self.graphics_window.opengl_canvas.CaptureMouse()
        elif fnum == 1:
            if not event.Dragging():
                return
        elif fnum == 2:
            self.graphics_window.opengl_canvas.ReleaseMouse()
        if button is None:
            if event.LeftIsDown():
                button = "left"
            elif event.MiddleIsDown():
                button = "middle"
            elif event.RightIsDown():
                button = "right"
            else:
                return
            if not self.graphics_window.opengl_canvas.HasCapture():
                # a Windows thing; can lose mouse capture w/o mouse up
                return
        f = self.mouse_modes.get(button)
        if f and f[fnum]:
            f[fnum](event)

    def shift_down(self, event):
        return event.ShiftDown()

    def event_position(self, event):
        return event.GetPosition()

    def cursor_position(self):
        import wx
        return self.graphics_window.ScreenToClient(wx.GetMousePosition())

    def wheel_value(self, event):
        return event.GetWheelRotation()/120.0   # Usually one wheel click is delta of 120
