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

"""
session: Application session support
====================================

A session provides access to most of the application's state.
At a minimum, it does not include the operating system state,
like the current directory, nor the environment,
nor any Python interpreter state
-- e.g., the exception hook, module globals, etc.

Code should be designed to support multiple sessions per process
since it is easier to start with that assumption rather than add it later.
Possible uses of multiple sessions include:
one session per tabbed graphics window,
or for comparing two sessions.

Session data, ie., data that is archived, uses the :py:class:`State` API.
"""

from .state import RestoreError, State, copy_state, dereference_state
from .commands import CmdDesc, OpenFileNameArg, SaveFileNameArg, register, commas, plural_form

_builtin_open = open
#: session file suffix
SESSION_SUFFIX = ".cxs"

# triggers:

#: version of session file that is written
CORE_SESSION_VERSION = 2


class _UniqueName:
    # uids are (class_name, ordinal)
    # The class_name is either the name of a core class
    # or a tuple (bundle name, class name)

    _cls_ordinals = {}  # {class: ordinal}
    _uid_to_obj = {}    # {uid: obj}
    _obj_to_uid = {}    # {id(obj): uid}
    _bundle_infos = set()

    __slots__ = ['uid']

    @classmethod
    def reset(cls):
        cls._cls_ordinals.clear()
        cls._uid_to_obj.clear()
        cls._obj_to_uid.clear()

    @classmethod
    def lookup(cls, unique_name):
        return cls._uid_to_obj.get(unique_name.uid, None)

    @classmethod
    def add(cls, uid, obj):
        # allows for non-_UniqueName uids
        cls._uid_to_obj[uid] = obj
        cls._obj_to_uid[id(obj)] = uid

    def obj(self):
        return self._uid_obj[self.uid]

    def __init__(self, uid):
        self.uid = uid

    @classmethod
    def from_obj(cls, toolshed, obj, logger):
        """Return a unique identifier for an object in session
        Consequently, the identifier is composed of simple data types.

        Parameters
        ----------
        obj : any object
        bundle_info : optional :py:class:`~chimerax.core.toolshed.BundleInfo` instance
            Explicitly denote which bundle object comes from.
        """

        uid = cls._obj_to_uid.get(id(obj), None)
        if uid is not None:
            return cls(uid)
        obj_cls = obj.__class__
        bundle_info = toolshed.find_bundle_for_class(obj_cls)
        if bundle_info is None:
            raise RuntimeError('No bundle information for %s.%s' % (
                obj_cls.__module__, obj_cls.__name__))
        else:
            class_name = (bundle_info.name, obj_cls.__name__)
            # double check that class will be able to be restored
            if obj_cls != bundle_info.get_class(obj_cls.__name__, logger):
                raise RuntimeError(
                    'unable to restore objects of %s class in %s bundle' %
                    (obj_cls.__name__, bundle_info.name))

        ordinal = cls._cls_ordinals.get(class_name, 0)
        if ordinal == 0 and bundle_info is not None:
            cls._bundle_infos.add(bundle_info)
        ordinal += 1
        uid = (class_name, ordinal)
        cls._cls_ordinals[class_name] = ordinal
        cls._uid_to_obj[uid] = obj
        cls._obj_to_uid[id(obj)] = uid
        return cls(uid)

    def __repr__(self):
        if len(self.uid) == 1:
            return '<%r>' % self.uid
        return '<%r, %r>' % self.uid

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.uid == other.uid

    def __hash__(self):
        return hash(self.uid)

    def class_name_of(self):
        """Extract class name associated with unique id for messages"""
        class_name = self.uid[0]
        if isinstance(class_name, str):
            return "Core's %s" % class_name
        return "Bundle %s's %s" % class_name

    def class_of(self, session):
        """Return class associated with unique id

        The restore process makes sure that the right bundles are present,
        so if there is an error, return None.
        """
        class_name, ordinal = self.uid
        if isinstance(class_name, str):
            from chimerax.core import bundle_api
            cls = bundle_api.get_class(class_name)
        else:
            bundle_name, class_name = class_name
            bundle_info = session.toolshed.find_bundle(bundle_name, session.logger)
            if bundle_info is None:
                cls = None
            else:
                cls = bundle_info.get_class(class_name, session.logger)
        return cls

#    @classmethod
#    def restore_unique_id(self, obj, uid):
#        """Restore unique identifier for an object"""
#        class_name, ordinal = uid
#        obj._cache_uid = ordinal
#        self._uid_to_obj[uid] = obj
#        current_ordinal = self._cls_ordinals.get(class_name, 0)
#        if ordinal > current_ordinal:
#            self._cls_ordinals[class_name] = ordinal


class _SaveManager:
    """Manage session saving"""

    def __init__(self, session, state_flags):
        self.session = session
        self.state_flags = state_flags
        self.graph = {}         # dependency graph
        self.unprocessed = []   # item: LIFO [obj]
        self.processed = {}     # item: {_UniqueName(obj)/attr_name: data}
        self._found_objs = []
        _UniqueName.reset()

    def discovery(self, containers):
        for key, value in containers.items():
            sm = self.session.snapshot_methods(value)
            if sm is None and len(value) == 0:
                continue
            try:
                if sm is None:
                    self.processed[key] = self.process(value)
                    self.graph[key] = self._found_objs
                else:
                    self.unprocessed.append(value)
                    uid = _UniqueName.from_obj(self.session.toolshed, value, self.session.logger)
                    self.processed[key] = uid
                    self.graph[key] = [uid]
            except ValueError as e:
                raise ValueError("error processing: %r" % key)
        while self.unprocessed:
            obj = self.unprocessed.pop()
            key = _UniqueName.from_obj(self.session.toolshed, obj, self.session.logger)
            if key not in self.processed:
                try:
                    self.processed[key] = self.process(obj)
                except ValueError as e:
                    raise ValueError("error processing key: %s: %s" % (key, e))
                self.graph[key] = self._found_objs

    def _add_obj(self, obj):
        uid = _UniqueName.from_obj(self.session.toolshed, obj, self.session.logger)
        self._found_objs.append(uid)
        if uid not in self.processed:
            self.unprocessed.append(obj)
        return uid

    def process(self, obj):
        self._found_objs = []
        data = None
        sm = self.session.snapshot_methods(obj)
        if sm:
            try:
                data = sm.take_snapshot(obj, self.session, self.state_flags)
            except:
                # TODO: give user option to report error?
                # import sys, traceback  # DEBUG
                # traceback.print_exc(file=sys.__stderr__)  # DEBUG
                pass
        if data is None:
            self.session.logger.warning('Unable to save "%s".  Session might not restore properly.' % obj.__class__.__name__)
        return copy_state(data, convert=self._add_obj)

    def walk(self):
        # generator that walks processed items in correct order
        from .order_dag import order_dag
        odg = order_dag(self.graph)
        while 1:
            try:
                key = next(odg)
                value = self.processed[key]
                yield key, value
            except StopIteration:
                return

    def bundle_infos(self):
        bundle_infos = {}
        for bi in _UniqueName._bundle_infos:
            bundle_infos[bi.name] = (bi.version, bi.session_write_version)
        return bundle_infos


class _RestoreManager:

    def __init__(self):
        _UniqueName.reset()
        self.bundle_infos = {}

    def check_bundles(self, session, bundle_infos):
        missing_bundles = []
        out_of_date_bundles = []
        for bundle_name, (bundle_version, bundle_state_version) in bundle_infos.items():
            bi = session.toolshed.find_bundle(bundle_name, session.logger)
            if bi is None:
                missing_bundles.append(bundle_name)
                continue
            # check if installed bundles can restore data
            if bundle_state_version not in bi.session_versions:
                out_of_date_bundles.append(bi)
        if missing_bundles or out_of_date_bundles:
            msg = "Unable to restore all of session"
            if missing_bundles:
                msg += "; missing %s: %s" % (
                    plural_form(missing_bundles, 'bundle'),
                    commas(missing_bundles, ' and'))
            if out_of_date_bundles:
                msg += "; out of date %s: %s" % (
                    plural_form(out_of_date_bundles, 'bundle'),
                    commas(out_of_date_bundles, ' and'))
            raise RestoreError(msg)
        self.bundle_infos = bundle_infos

    def resolve_references(self, data):
        # resolve references in data
        return dereference_state(data, _UniqueName.lookup, _UniqueName)

    def add_reference(self, name, obj):
        _UniqueName.add(name.uid, obj)


class Session:
    """Session management

    The metadata attribute should be a dictionary with information about
    the session, e.g., a thumbnail, a description, the author, etc.

    Attributes that support the :py:class:`State` API are automatically added as state managers
    (e.g. the session's add_state_manager method is called with the 'tag' argument
    the same as the attribute name).
    Conversely, deleting the attribute will call remove_state_manager.
    If a session attribute is not desired, the add/remove_state_manager methods can
    be called directly.

    Attributes
    ----------
    logger : An instance of :py:class:`~chimerax.core.logger.Logger`
        Use to log information, warning, errors.
    metadata : dict
        Information kept at beginning of session file, eg., a thumbnail
    models : Instance of :py:class:`~chimerax.core.models.Models`.
    triggers : An instance of :py:class:`~chimerax.core.triggerset.TriggerSet`
        Starts with session triggers.
    """

    #: common exception for needing a newer version of the application
    NeedNewerError = RestoreError(
        "Need newer version of bundle to restore session")

    def __init__(self, app_name, *, debug=False, silent=False, minimal=False):
        self.app_name = app_name
        self.debug = debug
        self.silent = silent
        from . import logger
        self.logger = logger.Logger(self)
        from . import triggerset
        self.triggers = triggerset.TriggerSet()
        self._state_containers = {}  # stuff to save in sessions
        self.metadata = {}           #: session metadata
        self.in_script = InScriptFlag()
        if minimal:
            return

        # initialize state managers for various properties
        from . import models
        self.models = models.Models(self)
        from .graphics.view import View
        self.main_view = View(self.models.drawing, window_size=(256, 256),
                              trigger_set=self.triggers)

        from . import colors
        self.user_colors = colors.UserColors()
        self.user_colormaps = colors.UserColormaps()
        # tasks and bundles are initialized later
        # TODO: scenes need more work
        # from .scenes import Scenes
        # sess.add_state_manager('scenes', Scenes(sess))

    def _get_view(self):
        return self._state_containers['main_view']

    def _set_view(self, view):
        self._state_containers['main_view'] = view
    view = property(_get_view, _set_view)

    @property
    def scenes(self):
        return self._state_containers['scenes']

    def reset(self):
        """Reset session to data-less state"""
        self.metadata.clear()
        for tag in self._state_containers:
            container = self._state_containers[tag]
            sm = self.snapshot_methods(container)
            if sm:
                sm.reset_state(container, self)
            else:
                container.clear()

    def __setattr__(self, name, value):
        # need to actually set attr first,
        # since add_state_manager will check if the attr exists
        object.__setattr__(self, name, value)
        if self.snapshot_methods(value) is not None:
            self.add_state_manager(name, value)

    def __delattr__(self, name):
        if name in self._state_containers:
            self.remove_state_manager(name)
        object.__delattr__(self, name)

    def add_state_manager(self, tag, container):
        sm = self.snapshot_methods(container)
        if sm is None and not hasattr(container, 'clear'):
            raise ValueError('container "%s" of type "%s" does not have snapshot methods and does not have clear method' % (tag, str(type(container))))
        self._state_containers[tag] = container

    def get_state_manager(self, tag):
        return self._state_containers[tag]

    def remove_state_manager(self, tag):
        del self._state_containers[tag]

    def snapshot_methods(self, object, instance=True):
        """Return an object having take_snapshot() and restore_snapshot() methods for the given object.
        Can return if no save/restore methods are available, for instance for primitive types.
        """
        cls = object.__class__ if instance else object
        if issubclass(cls, State):
            return cls
        elif not hasattr(self, '_snapshot_methods'):
            from .graphics import View, MonoCamera, OrthographicCamera, Lighting, Material, ClipPlane, Drawing
            from .graphics import gsession as g
            from .geometry import Place, Places, psession as p
            self._snapshot_methods = {
                View: g.ViewState,
                MonoCamera: g.CameraState,
                OrthographicCamera: g.CameraState,
                Lighting: g.LightingState,
                Material: g.MaterialState,
                ClipPlane: g.ClipPlaneState,
                Drawing: g.DrawingState,
                Place: p.PlaceState,
                Places: p.PlacesState,
            }

        methods = self._snapshot_methods.get(cls, None)
        return methods

    def save(self, stream, version):
        """Serialize session to binary stream."""
        from . import serialize
        self.triggers.activate_trigger("begin save session", self)
        if version == 1:
            fserialize = serialize.pickle_serialize
            fserialize(stream, version)
        else:
            if version != 2:
                from .errors import UserError
                raise UserError("Only session file versions 1 and 2 are supported")
            stream.write(b'# ChimeraX Session version %d\n' % CORE_SESSION_VERSION)
            stream = serialize.msgpack_serialize_stream(stream)
            fserialize = serialize.msgpack_serialize
        # stash attribute info into metadata...
        attr_info = {}
        for tag, container in self._state_containers.items():
            attr_info[tag] = getattr(self, tag, None) == container
        self.metadata['attr_info'] = attr_info
        fserialize(stream, self.metadata)
        # guarantee that bundles are serialized first, so on restoration,
        # all of the related code will be loaded before the rest of the
        # session is restored
        mgr = _SaveManager(self, State.SESSION)
        mgr.discovery(self._state_containers)
        fserialize(stream, mgr.bundle_infos())
        # TODO: collect OrderDAGError exceptions from walk and analyze
        for name, data in mgr.walk():
            fserialize(stream, name)
            fserialize(stream, data)
        fserialize(stream, None)
        self.triggers.activate_trigger("end save session", self)

    def restore(self, stream, metadata_only=False):
        """Deserialize session from binary stream."""
        from . import serialize
        if hasattr(stream, 'peek'):
            use_pickle = stream.peek(1)[0] != ord(b'#')
        else:
            use_pickle = stream.buffer.peek(1)[0] != ord(b'#')
        if use_pickle:
            version = serialize.pickle_deserialize(stream)
            if version != 1:
                raise RestoreError('Not a ChimeraX session file')
            fdeserialize = serialize.pickle_deserialize
        else:
            line = stream.readline(256)   # limit line length to avoid DOS
            tokens = line.split()
            if line[-1] != ord(b'\n') or len(tokens) < 5 or tokens[0:4] != [b'#', b'ChimeraX', b'Session', b'version']:
                raise RuntimeError('Not a ChimeraX session file')
            version = int(tokens[4])
            if not (2 <= version <= CORE_SESSION_VERSION):
                raise self.NeedNewerError
            stream = serialize.msgpack_deserialize_stream(stream)
            fdeserialize = serialize.msgpack_deserialize
        metadata = fdeserialize(stream)
        metadata['session_version'] = version
        if metadata_only:
            self.metadata.update(metadata)
            return

        mgr = _RestoreManager()
        bundle_infos = fdeserialize(stream)
        try:
            mgr.check_bundles(self, bundle_infos)
        except RestoreError as e:
            self.logger.warning(str(e))

        self.triggers.activate_trigger("begin restore session", self)
        try:
            self.reset()
            self.metadata.update(metadata)
            attr_info = self.metadata.pop('attr_info', {})
            while True:
                name = fdeserialize(stream)
                if name is None:
                    break
                data = fdeserialize(stream)
                data = mgr.resolve_references(data)
                if isinstance(name, str):
                    if attr_info.get(name, False):
                        setattr(self, name, data)
                    else:
                        self.add_state_manager(name, data)
                else:
                    # _UniqueName: find class
                    cls = name.class_of(self)
                    if cls is None:
                        continue
                    sm = self.snapshot_methods(cls, instance=False)
                    if sm is None:
                        obj = None
                        self.logger.warning('Unable to restore "%s" object' % cls.__name__)
                    else:
                        obj = sm.restore_snapshot(self, data)
                    mgr.add_reference(name, obj)
        except:
            import traceback
            self.logger.error("Unable to restore session, resetting.\n\n%s"
                              % traceback.format_exc())
            self.reset()
        finally:
            self.triggers.activate_trigger("end restore session", self)


class InScriptFlag:

    def __init__(self):
        self._level = 0

    def __enter__(self):
        self._level += 1

    def __exit__(self, *_):
        self._level -= 1

    def __bool__(self):
        return self._level > 0


def save(session, filename, format, version=1, uncompressed=False):
    """command line version of saving a session"""
    my_open = None
    if hasattr(filename, 'write'):
        # called via export, it's really a stream
        output = filename
    else:
        from os.path import expanduser
        filename = expanduser(filename)         # Tilde expansion
        if not filename.endswith(SESSION_SUFFIX):
            filename += SESSION_SUFFIX

        if uncompressed:
            try:
                output = _builtin_open(filename, 'wb')
            except IOError as e:
                from .errors import UserError
                raise UserError(e)
        else:
            # Save compressed files
            def my_open(filename):
                import gzip
                from .safesave import SaveFile
                f = SaveFile(filename, open=lambda filename: gzip.GzipFile(filename, 'wb'))
                return f
            try:
                output = my_open(filename)
            except IOError as e:
                from .errors import UserError
                raise UserError(e)

    session.logger.warning("<b><i>Session file format is not finalized, and thus might not be restorable in other versions of ChimeraX.</i></b>", is_html=True)
    # TODO: put thumbnail in session metadata
    try:
        session.save(output, version=version)
    except:
        if my_open is not None:
            output.close("exceptional")
        raise
    finally:
        if my_open is not None:
            output.close()

    # Associate thumbnail image with session file for display by operating system file browser.
    from . import utils
    if isinstance(filename, str) and utils.can_set_file_icon():
        width = height = 512
        try:
            image = session.main_view.image(width, height)
        except RuntimeError:
            pass
        else:
            utils.set_file_icon(filename, image)

    # Remember session in file history
    if isinstance(filename, str):
        from .filehistory import remember_file
        remember_file(session, filename, 'ses', 'all models', file_saved=True)


def sdump(session, session_file, output=None):
    """dump contents of session for debugging"""
    from . import serialize
    if not session_file.endswith(SESSION_SUFFIX):
        session_file += SESSION_SUFFIX
    if is_gzip_file(session_file):
        import gzip
        stream = gzip.open(session_file, 'rb')
    else:
        stream = _builtin_open(session_file, 'rb')
    if output is not None:
        # output = open_filename(output, 'w')
        output = _builtin_open(output, 'w')
    from pprint import pprint
    with stream:
        if hasattr(stream, 'peek'):
            use_pickle = stream.peek(1)[0] != ord(b'#')
        else:
            use_pickle = stream.buffer.peek(1)[0] != ord(b'#')
        if use_pickle:
            fdeserialize = serialize.pickle_deserialize
            version = fdeserialize(stream)
        else:
            tokens = stream.readline().split()
            version = int(tokens[4])
            stream = serialize.msgpack_deserialize_stream(stream)
            fdeserialize = serialize.msgpack_deserialize
        print("==== session version:", file=output)
        pprint(version, stream=output)
        print("==== session metadata:", file=output)
        metadata = fdeserialize(stream)
        pprint(metadata, stream=output)
        print("==== bundle info:", file=output)
        bundle_infos = fdeserialize(stream)
        pprint(bundle_infos, stream=output)
        while True:
            name = fdeserialize(stream)
            if name is None:
                break
            data = fdeserialize(stream)
            print('==== name/uid:', name, file=output)
            pprint(data, stream=output)


def open(session, filename, *args, **kw):
    if hasattr(filename, 'read'):
        # Given a stream instead of a file name.
        fname = filename.name
        filename.close()
    else:
        fname = filename

    if is_gzip_file(fname):
        import gzip
        stream = gzip.open(fname, 'rb')
    else:
        stream = _builtin_open(fname, 'rb')
    # TODO: active trigger to allow user to stop overwritting
    # current session
    session.restore(stream)
    return [], "opened ChimeraX session"


def is_gzip_file(filename):
    f = _builtin_open(filename, 'rb')
    magic = f.read(2) + b'00'
    f.close()
    return (magic[0] == 0x1f and magic[1] == 0x8b)


def save_x3d(session, filename, format, transparent_background=False):
    # Settle on using Interchange profile as that is the intent of
    # X3D exporting.
    from . import x3d
    from .fetch import html_user_agent
    from chimerax import app_dirs
    from html import unescape
    import datetime
    import os
    x3d_scene = x3d.X3DScene()
    meta = {}
    generator = unescape(html_user_agent(app_dirs))
    generator += ", %s" % "http://www.cgl.ucsf.edu/chimerax/"
    meta['generator'] = generator
    year = datetime.datetime.today().year
    # TODO: better way to get full user name
    user = os.environ.get('USERNAME', None)
    if user is None:
        user = os.getlogin()
    meta['author'] = user

    # record needed X3D components
    x3d_scene.need(x3d.Components.EnvironmentalEffects, 1)  # Background
    # x3d_scene.need(x3d.Components.EnvironmentalEffects, 2)  # Fog
    camera = session.main_view.camera
    if camera.name == "orthographic":
        x3d_scene.need(x3d.Components.Navigation, 3)  # OrthoViewpoint
    else:
        x3d_scene.need(x3d.Components.Navigation, 1)  # Viewpoint, NavigationInfo
    # x3d_scene.need(x3d.Components.Rendering, 5)  # ClipPlane
    # x3d_scene.need(x3d.Components.Lighting, 1)  # DirectionalLight
    for m in session.models.list():
        m.x3d_needs(x3d_scene)

    with _builtin_open(filename, 'w', encoding='utf-8') as stream:
        x3d_scene.write_header(
            stream, 0, meta, profile_name='Interchange',
            # TODO? Skip units since it confuses X3D viewers and requires version 3.3
            units={'length': ('ångström', 1e-10)},
            # not using any of Chimera's extensions yet
            # namespaces={"chimera": "http://www.cgl.ucsf.edu/chimera/"}
        )
        cofr = session.main_view.center_of_rotation
        r, a = camera.position.rotation_axis_and_angle()
        t = camera.position.translation()
        if camera.name == "orthographic":
            hw = camera.field_width / 2
            f = (-hw, -hw, hw, hw)
            print('  <OrthoViewpoint centerOfRotation="%g %g %g" fieldOfView="%g %g %g %g" orientation="%g %g %g %g" position="%g %g %g"/>'
                  % (cofr[0], cofr[1], cofr[2], f[0], f[1], f[2], f[3], r[0], r[1], r[2], a, t[0], t[1], t[2]), file=stream)
        else:
            from math import tan, atan, radians
            h, w = session.main_view.window_size
            horiz_fov = radians(camera.field_of_view)
            vert_fov = 2 * atan(tan(horiz_fov / 2) * h / w)
            fov = min(horiz_fov, vert_fov)
            print('  <Viewpoint centerOfRotation="%g %g %g" fieldOfView="%g" orientation="%g %g %g %g" position="%g %g %g"/>'
                  % (cofr[0], cofr[1], cofr[2], fov, r[0], r[1], r[2], a, t[0], t[1], t[2]), file=stream)
        print('  <NavigationInfo type=\'"EXAMINE" "ANY"\' headlight=\'true\'/>', file=stream)
        c = session.main_view.background_color
        if transparent_background:
            t = 1
        else:
            t = 0
        print("  <Background skyColor='%g %g %g' transparency='%g'/>" % (c[0], c[1], c[2], t), file=stream)
        # TODO: write out lighting?
        from .geometry import Place
        p = Place()
        for m in session.models.list():
            m.write_x3d(stream, x3d_scene, 2, p)
        x3d_scene.write_footer(stream, 0)


def register_session_format(session):
    from . import io, toolshed
    io.register_format(
        "ChimeraX session", toolshed.SESSION, SESSION_SUFFIX, ("session",),
        mime="application/x-chimerax-session",
        reference="http://www.rbvi.ucsf.edu/chimerax/",
        open_func=open, export_func=save)

    from .commands import CmdDesc, register, SaveFileNameArg, IntArg, BoolArg
    desc = CmdDesc(
        required=[('filename', SaveFileNameArg)],
        keyword=[('version', IntArg), ('uncompressed', BoolArg)],
        hidden=['version', 'uncompressed'],
        synopsis='save session'
    )

    def save_session(session, filename, **kw):
        kw['format'] = 'session'
        from .commands.save import save
        save(session, filename, **kw)
    register('save session', desc, save_session, logger=session.logger)


def register_x3d_format():
    from . import io, toolshed
    io.register_format(
        "X3D", toolshed.GENERIC3D, ".x3d", "x3d",
        mime="model/x3d+xml",
        reference="http://www.web3d.org/standards",
        export_func=save_x3d)


def common_startup(sess):
    """Initialize session with common data containers"""

    from .core_triggers import register_core_triggers
    register_core_triggers(sess.triggers)

    from .selection import Selection
    sess.selection = Selection(sess)

    try:
        from .core_settings import settings
        sess.main_view.background_color = settings.bg_color.rgba
    except ImportError:
        pass

    from .updateloop import UpdateLoop
    sess.update_loop = UpdateLoop()

    from .atomic import ChangeTracker
    sess.change_tracker = ChangeTracker()
    # change_tracker needs to exist before global pseudobond manager
    # can be created
    from .atomic import PseudobondManager
    sess.pb_manager = PseudobondManager(sess)

    from . import commands
    commands.register_core_commands(sess)
    commands.register_core_selectors(sess)

    register(
        'debug sdump',
        CmdDesc(required=[('session_file', OpenFileNameArg)],
                optional=[('output', SaveFileNameArg)],
                synopsis="create human-readable session"),
        sdump,
        logger=sess.logger
    )

    _register_core_file_formats(sess)
    _register_core_database_fetch()


def _register_core_file_formats(session):
    register_session_format(session)
    from .atomic import pdb
    pdb.register_pdb_format()
    from .atomic import mmcif
    mmcif.register_mmcif_format()
    from . import scripting
    scripting.register()
    from . import map
    map.register_map_file_formats(session)
    from .atomic import readpbonds
    readpbonds.register_pbonds_format()
    from .surface import collada
    collada.register_collada_format()
    from . import image
    image.register_image_save(session)
    register_x3d_format()


def _register_core_database_fetch():
    from .atomic import pdb
    pdb.register_pdb_fetch()
    from .atomic import mmcif
    mmcif.register_mmcif_fetch()
    from . import map
    map.register_eds_fetch()
    map.register_emdb_fetch()
    from . import fetch
    fetch.register_web_fetch()
