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


class PointerModels:
    '''Manage mouse or VR pointer models for all connected hosts.'''
    def __init__(self, session):
        self._session = session
        self._pointer_models = {}	# Map peer id to MousePointerModel or VRPointerModel

    def delete(self):
        for peer_id in tuple(self._pointer_models.keys()):
            self.remove_model(peer_id)

    def pointer_model(self, peer_id = None):
        pm = self._pointer_models
        if peer_id in pm:
            m = pm[peer_id]
            if not m.deleted:
                return m

        m = self.make_pointer_model(self._session)
        models = self._session.models
        models.add([m], minimum_id = 100)
        pm[peer_id] = m
        return m

    @property
    def pointer_models(self):
        return tuple(self._pointer_models.items())

    def make_pointer_model(self, session):
        # Must be defined by subclass.
        pass

    def update_model(self, msg):
        m = self.pointer_model(msg.get('id'))
        if not m.deleted:
            m.update_pointer(msg)

    def remove_model(self, peer_id):
        pm = self._pointer_models
        if peer_id in pm:
            m = pm[peer_id]
            del pm[peer_id]
            if not m.deleted:
                self._session.models.close([m])


class MouseTracking(PointerModels):
    def __init__(self, session, meeting):
        PointerModels.__init__(self, session)
        self._meeting = meeting		# MeetingServer instance

        t = session.triggers
        self._mouse_hover_handler = t.add_handler('mouse hover', self._mouse_hover_cb)

    def delete(self):
        t = self._session.triggers
        t.remove_handler(self._mouse_hover_handler)
        self._mouse_hover_handler = None

        PointerModels.delete(self)

    def update_model(self, msg):
        if 'mouse' in msg:
            PointerModels.update_model(self, msg)

    def make_pointer_model(self, session):
        return MousePointerModel(self._session, 'my pointer')

    def _mouse_hover_cb(self, trigger_name, xyz):
        if _vr_camera(self._session):
            return

        xyz = getattr(pick, 'position', None)
        if xyz is None:
            return
        c = self._session.main_view.camera
        axis = c.view_direction()
        msg = {'name': self._meeting._name,
               'color': tuple(self._meeting._color),
               'mouse': (tuple(xyz), tuple(axis)),
               }

        # Update my own mouse pointer position
        self.update_model(msg)

        # Tell connected peers my new mouse pointer position.
        self._meeting._send_message(msg)


from chimerax.core.models import Model
class MousePointerModel(Model):
    SESSION_SAVE = False

    def __init__(self, session, name, radius = 1, height = 3, color = (0,255,0,255)):
        Model.__init__(self, name, session)
        from chimerax.surface import cone_geometry
        va, na, ta = cone_geometry(radius = radius, height = height)
        va[:,2] -= 0.5*height	# Place tip of cone at origin
        self.set_geometry(va, na, ta)
        self.color = color

    def update_pointer(self, msg):
        if 'name' in msg:
            if 'id' in msg:  # If id not in msg leave name as "my pointer".
                self.name = '%s pointer' % msg['name']
        if 'color' in msg:
            self.color = msg['color']
        if 'mouse' in msg:
            xyz, axis = msg['mouse']
            from chimerax.geometry import vector_rotation, translation
            p = translation(xyz) * vector_rotation((0,0,1), axis)
            self.position = p


class VRTracking(PointerModels):
    def __init__(self, session, meeting, sync_coords = True, update_interval = 1):
        PointerModels.__init__(self, session)
        self._meeting = meeting		# MeetingServer instance
        self._sync_coords = sync_coords

        t = session.triggers
        self._vr_tracking_handler = t.add_handler('vr update', self._vr_tracking_cb)
        self._update_interval = update_interval	# Send vr position every N frames.
        self._last_vr_camera = c = _vr_camera(self._session)
        self._last_room_to_scene = c.room_to_scene if c else None
        self._new_face_image = None	# Path to image file
        self._face_image = None		# Encoded image
        self._send_face_image = False
        self._gui_state = {'shown':False, 'size':(0,0), 'room position':None, 'image':None}

    def delete(self):
        t = self._session.triggers
        t.remove_handler(self._vr_tracking_handler)
        self._vr_tracking_handler = None

        PointerModels.delete(self)

    @property
    def last_room_to_scene(self):
        return self._last_room_to_scene

    def _get_update_interval(self):
        return self._update_interval
    def _set_update_interval(self, update_interval):
        self._update_interval = update_interval
    update_interval = property(_get_update_interval, _set_update_interval)

    def update_model(self, msg):
        if 'vr coords' in msg and self._sync_coords:
            matrix = msg['vr coords']
            rts = self._last_room_to_scene = _matrix_place(matrix)
            c = _vr_camera(self._session)
            if c:
                c.room_to_scene = rts
                self._reposition_vr_head_and_hands(c)

        if 'vr head' in msg:
            PointerModels.update_model(self, msg)

    def make_pointer_model(self, session):
        # Make sure new meeting participant gets my head image and button modes.
        self._send_face_image = True
        self._send_button_modes()

        pm = VRPointerModel(self._session, 'VR', self._last_room_to_scene)
        return pm

    def new_face_image(self, path):
        self._new_face_image = path

    def _send_button_modes(self):
        c = _vr_camera(self._session)
        if c:
            for h in c._hand_controllers:
                h._meeting_button_modes = {}

    def _vr_tracking_cb(self, trigger_name, camera):
        c = camera

        if c is not self._last_vr_camera:
            # VR just turned on so use current meeting room coordinates
            self._last_vr_camera = c
            rts = self._last_room_to_scene
            if rts is not None:
                c.room_to_scene = rts

        scene_moved = (c.room_to_scene is not self._last_room_to_scene)
        if scene_moved:
            self._reposition_vr_head_and_hands(c)

        v = self._session.main_view
        if v.frame_number % self.update_interval != 0:
            return

        # Report VR hand and head motions.
        msg = {'name': self._meeting._name,
               'color': tuple(self._meeting._color),
               'vr head': self._head_position(c),	# In room coordinates
               'vr hands': self._hand_positions(c),	# In room coordinates
               }

        fi = self._face_image_update()
        if fi:
            msg['vr head image'] = fi

        hb = self._hand_buttons_update(c)
        if hb:
            msg['vr hand buttons'] = hb

        # Report scene moved in room
        if scene_moved:
            msg['vr coords'] = _place_matrix(c.room_to_scene)
            self._last_room_to_scene = c.room_to_scene

        # Report changes in VR GUI panel
        gu = self._gui_updates(c)
        if gu:
            msg.update(gu)

        # Tell connected peers my new vr state
        self._meeting._send_message(msg)

    def _head_position(self, vr_camera):
        from chimerax.geometry import scale
        return _place_matrix(vr_camera.room_position * scale(1/vr_camera.scene_scale))

    def _face_image_update(self):
        # Report VR face image change.
        fi = None
        if self._new_face_image:
            image = _encode_face_image(self._new_face_image)
            self._face_image = image
            fi = image
            self._new_face_image = None
            self._send_face_image = False
        elif self._send_face_image:
            self._send_face_image = False
            if self._face_image is not None:
                fi = self._face_image
        return fi

    def _hand_positions(self, vr_camera):
        # Hand controller room position includes scaling from room to scene coordinates
        return [_place_matrix(h.room_position)
                for h in vr_camera._hand_controllers if h.on]

    def _hand_buttons_update(self, vr_camera):
        bu = []
        update = False
        hc = vr_camera._hand_controllers
        for h in hc:
            last_mode = getattr(h, '_meeting_button_modes', None)
            if last_mode is None:
                h._meeting_button_modes = last_mode = {}
            hm = []
            for button, mode in h.button_modes.items():
                if mode != last_mode.get(button):
                    last_mode[button] = mode
                    hm.append((button, mode.name))
                    update = True
            bu.append(hm)
        return bu if update else None

    def _gui_updates(self, vr_camera):
        msg = {}
        c = vr_camera
        ui = c.user_interface
        shown = ui.shown()
        gui_state = self._gui_state
        shown_changed = (shown != gui_state['shown'])
        if shown_changed:
            msg['vr gui shown'] = gui_state['shown'] = shown
        if shown:
            rpos = ui.model.room_position
            if rpos is not gui_state['room position'] or shown_changed:
                gui_state['room position'] = rpos
                msg['vr gui position'] = _place_matrix(rpos)

            # Notify about changes in panel size, position or image.
            pchanges = []	# GUI panel changes
            for panel in ui.panels:
                name, size, pos, rgba = panel.name, panel.size, panel.drawing.position, panel.panel_image_rgba()
                pstate = gui_state.setdefault(('panel', name), {})
                pchange = {}
                if 'size' not in pstate or size != pstate['size'] or shown_changed:
                    pchange['size'] = pstate['size'] = size
                if 'position' not in pstate or pos != pstate['position'] or shown_changed:
                    pstate['position'] = pos
                    pchange['position'] = _place_matrix(pos)
                if 'image' not in pstate or rgba is not pstate['image'] or shown_changed:
                    pstate['image'] = rgba
                    pchange['image'] = _encode_numpy_array(rgba)
                if pchange:
                    pchange['name'] = panel.name
                    pchanges.append(pchange)

            # Notify about removed panels
            panel_names = set(panel.name for panel in ui.panels)
            for pname in tuple(gui_state.keys()):
                if (isinstance(pname, tuple) and len(pname) == 2 and pname[0] == 'panel'
                    and pname[1] not in panel_names):
                    pchanges.append({'name':pname[1], 'closed':True})
                    del gui_state[pname]

            if pchanges:
                msg['vr gui panels'] = pchanges

        return msg

    def _reposition_vr_head_and_hands(self, camera):
        '''
        If my room to scene coordinates change correct the VR head and hand model
        scene positions so they maintain the same apparent position in the room.
        '''
        c = camera
        rts = c.room_to_scene
        for peer_id, vrm in self.pointer_models:
            if isinstance(vrm, VRPointerModel):
                for m in vrm.child_models():
                    if m.room_position is not None:
                        m.scene_position = rts*m.room_position


from chimerax.core.models import Model
class VRPointerModel(Model):
    casts_shadows = False
    pickable = False
    skip_bounds = True
    SESSION_SAVE = False
    model_panel_show_expanded = False

    def __init__(self, session, name, room_to_scene, color = (0,255,0,255)):
        Model.__init__(self, name, session)
        self._head = h = VRHeadModel(session)
        self.add([h])
        self._hands = []
        self._color = color
        self._gui = None

	# Last room to scene transformation for this peer.
        # Used if we are not using VR camera so have no room coordinates.
        self._room_to_scene = room_to_scene

    def _hand_models(self, nhands):
        from chimerax.vive.vr import HandModel
        new_hands = [HandModel(self.session, 'Hand %d' % (i+1), color=self._color)
                     for i in range(len(self._hands), nhands)]
        if new_hands:
            self.add(new_hands)
            self._hands.extend(new_hands)
        return self._hands[:nhands]

    @property
    def _gui_panel(self):
        g = self._gui
        if g is None:
            self._gui = g = VRGUIModel(self.session)
            self.add([g])
        return g

    def _get_room_to_scene(self):
        c = _vr_camera(self.session)
        return c.room_to_scene if c else self._room_to_scene
    def _set_room_to_scene(self, rts):
        self._room_to_scene = rts
    room_to_scene = property(_get_room_to_scene, _set_room_to_scene)

    def update_pointer(self, msg):
        if 'name' in msg:
            if 'id' in msg:  # If id not in msg leave name as "my pointer".
                self.name = '%s VR' % msg['name']
        if 'color' in msg:
            for h in self._hands:
                h.set_cone_color(msg['color'])
        if 'vr coords' in msg:
            self.room_to_scene = _matrix_place(msg['vr coords'])
        if 'vr head' in msg:
            h = self._head
            h.room_position = rp = _matrix_place(msg['vr head'])
            h.position = self.room_to_scene * rp
        if 'vr head image' in msg:
            self._head.update_image(msg['vr head image'])
        if 'vr hands' in msg:
            hpos = msg['vr hands']
            rts = self.room_to_scene
            for h,hm in zip(self._hand_models(len(hpos)), hpos):
                h.room_position = rp = _matrix_place(hm)
                h.position = rts * rp
        if 'vr hand buttons' in msg:
            hbut = msg['vr hand buttons']
            from chimerax.vive.vr import hand_mode_icon_path
            for h,hb in zip(self._hand_models(len(hbut)), hbut):
                for button, mode_name in hb:
                    path = hand_mode_icon_path(self.session, mode_name)
                    if path:
                        h._set_button_icon(button, path)
        if 'vr gui shown' in msg:
            self._gui_panel.display = msg['vr gui shown']
        if 'vr gui position' in msg:
            g = self._gui_panel
            g.room_position = rp = _matrix_place(msg['vr gui position'])
            g.position = self.room_to_scene * rp
        if 'vr gui panels' in msg:
            for pchanges in msg['vr gui panels']:
                self._gui_panel.update_panel(pchanges)


class VRHeadModel(Model):
    '''Size in meters.'''
    casts_shadows = False
    pickable = False
    skip_bounds = True
    SESSION_SAVE = False
    default_face_file = 'face.png'
    def __init__(self, session, name = 'Head', size = 0.3, image_file = None):
        Model.__init__(self, name, session)
        self.room_position = None

        r = size / 2
        from chimerax.surface import box_geometry
        va, na, ta = box_geometry((-r,-r,-0.1*r), (r,r,0.1*r))

        if image_file is None:
            from os.path import join, dirname
            image_file = join(dirname(__file__), self.default_face_file)
        from Qt.QtGui import QImage
        qi = QImage(image_file)
        aspect = qi.width() / qi.height()
        va[:,0] *= aspect
        from chimerax.graphics import qimage_to_numpy, Texture
        rgba = qimage_to_numpy(qi)
        from numpy import zeros, float32
        tc = zeros((24,2), float32)
        tc[:] = 0.5
        tc[8:12,:] = ((0,0), (1,0), (0,1), (1,1))

        self.set_geometry(va, na, ta)
        self.color = (255,255,255,255)
        self.texture = Texture(rgba)
        self.texture_coordinates = tc

    def update_image(self, base64_image_bytes):
        image_bytes = _decode_face_image(base64_image_bytes)
        from Qt.QtGui import QImage
        qi = QImage()
        qi.loadFromData(image_bytes)
        aspect = qi.width() / qi.height()
        va = self.vertices
        caspect = va[:,0].max() / va[:,1].max()
        va[:,0] *= aspect / caspect
        self.set_geometry(va, self.normals, self.triangles)
        from chimerax.graphics import qimage_to_numpy, Texture
        rgba = qimage_to_numpy(qi)
        r = self.session.main_view.render
        r.make_current()
        self.texture.delete_texture()
        self.texture = Texture(rgba)


class VRGUIModel(Model):
    '''Size in meters.'''
    casts_shadows = False
    pickable = False
    skip_bounds = True
    SESSION_SAVE = False

    def __init__(self, session, name = 'GUI Panel'):
        Model.__init__(self, name, session)
        self.room_position = None
        self._panels = {}		# Maps panel name to VRGUIPanel

    def update_panel(self, panel_changes):
        name = panel_changes['name']
        panels = self._panels

        if 'closed' in panel_changes:
            if name in panels:
                self.remove_drawing(panels[name])
                del panels[name]
            return

        if name in panels:
            p = panels[name]
        else:
            panels[name] = p = VRGUIPanel(name)
            self.add_drawing(p)

        if 'size' in panel_changes:
            p.set_size(panel_changes['size'])
        if 'position' in panel_changes:
            p.position = _matrix_place(panel_changes['position'])
        if 'image' in panel_changes:
            p.update_image(panel_changes['image'], self.session)


from chimerax.graphics import Drawing
class VRGUIPanel(Drawing):
    casts_shadows = False
    pickable = False
    skip_bounds = True

    def __init__(self, name):
        Drawing.__init__(self, name)
        self._size = (1,1)		# Meters

    def set_size(self, size):
        self._size = (rw, rh) = size
        from chimerax.graphics.drawing import position_rgba_drawing
        position_rgba_drawing(self, pos = (-0.5*rw,-0.5*rh), size = (rw,rh))

    def update_image(self, encoded_rgba, session):
        rw, rh = self._size
        rgba = _decode_numpy_array(encoded_rgba)
        r = session.main_view.render
        r.make_current() # Required for deleting previous texture in rgba_drawing()
        from chimerax.graphics.drawing import rgba_drawing
        rgba_drawing(self, rgba, pos = (-0.5*rw,-0.5*rh), size = (rw,rh))


def _vr_camera(session):
    c = session.main_view.camera
    from chimerax.vive.vr import SteamVRCamera
    return c if isinstance(c, SteamVRCamera) else None


def _place_matrix(p):
    '''Encode Place as tuple for sending over socket.'''
    return tuple(tuple(row) for row in p.matrix)


def _matrix_place(m):
    from chimerax.geometry import Place
    return Place(matrix = m)


def _encode_face_image(path):
    from base64 import b64encode
    hf = open(path, 'rb')
    he = b64encode(hf.read())
    hf.close()
    return he


def _decode_face_image(bytes):
    from base64 import b64decode
    image_bytes = b64decode(bytes)
    return image_bytes


def _encode_numpy_array(array):
    from base64 import b64encode
    from zlib import compress
    data = b64encode(compress(array.tobytes(), level = 1))
    data = {
        'shape': tuple(array.shape),
        'dtype': array.dtype.str,
        'data': data
    }
    return data


def _decode_numpy_array(array_data):
    shape = array_data['shape']
    dtype = array_data['dtype']
    from base64 import b64decode
    from zlib import decompress
    data = decompress(b64decode(array_data['data']))
    import numpy
    a = numpy.frombuffer(data, dtype).reshape(shape)
    return a
