# -----------------------------------------------------------------------------
#
def save_session(path, session):
  '''
  Save a session.
  '''
  from os.path import expanduser
  p = expanduser(path)
  s = session_state(session)
  s['session path'] = path
  f = open(p, 'w')
  from ..files.SessionUtil import objecttree
  objecttree.write_basic_tree(s, f)
  f.close()

  # Set file icon image on Mac
  from . import fileicon
  fileicon.set_file_icon(p, session)

  session.file_history.add_entry(p, replace_image = True)

# -----------------------------------------------------------------------------
#
def restore_session(path, session):
  '''
  Restore a session.
  '''
  f = open(path, 'r')
  s = f.read()
  f.close()
  import ast
  d = ast.literal_eval(s)
  session.close_all_models()

  file_paths = File_Locator(path, d.get('session path'))
  set_session_state(d, session, file_paths)

  session.file_history.add_entry(path)

# -----------------------------------------------------------------------------
#
def session_state(session, attributes_only = False):
  '''
  Create a dictionary representing a session including molecule models,
  surface models, density map models and scenes.  This dictionary is written
  to a Python file as a session.  It contains only basic Python types:
  numbers, strings, booleans, tuples, lists, dictionaries.
  '''
  viewer = session.view
  s = {'version': 3,
       'view': view_state(viewer),
       'camera': camera_state(viewer.camera),
       'lighting': lighting_state(viewer.lighting()),
       'material': material_state(viewer.material()),
  }

  from ..map.session import map_states
  vs = map_states(session)
  if vs:
    s['volumes'] = vs

  from ..map.series.session import map_series_states
  mss = map_series_states(session)
  if mss:
    s['map series'] = mss

  from ..map.series.session import map_series_slider_states
  sls = map_series_slider_states(session)
  if sls:
    s['map series gui'] = sls

  mlist = session.molecules()
  if mlist:
    from ..molecule import mol_session
    s['molecules'] = tuple(mol_session.molecule_state(m) for m in mlist)

  from .read_stl import STL_Surface
  slist = tuple(m.session_state() for m in session.model_list()
                if isinstance(m, STL_Surface))
  if slist:
    s['stl surfaces'] = slist

  if not attributes_only:
    from .. import scenes
    ss = scenes.scene_state(session)
    if ss:
      s['scenes'] = ss

  return s

# -----------------------------------------------------------------------------
#
def set_session_state(s, session, file_paths, attributes_only = False):

  v = session.view
  if 'view' in s:
    restore_view(s['view'], v)

  if 'camera' in s:
    restore_camera(s['camera'], v.camera)

  if 'lighting' in s:
    restore_lighting(s['lighting'], s['version'], v.lighting())

  if 'material' in s:
    restore_material(s['material'], s['version'], v.material())

  if 'volumes' in s:
    from ..map.session import restore_maps
    restore_maps(s['volumes'], session, file_paths, attributes_only)

  if 'map series' in s:
    from ..map.series.session import restore_map_series
    restore_map_series(s['map series'], session, file_paths, attributes_only)

  if 'map series gui' in s:
    from ..map.series.session import restore_map_series_sliders
    restore_map_series_sliders(s['map series gui'], session, file_paths, attributes_only)

  if 'molecules' in s:
    from ..molecule.mol_session import restore_molecules
    restore_molecules(s['molecules'], session, file_paths, attributes_only)

  if 'stl surfaces' in s:
    from .read_stl import restore_stl_surfaces
    restore_stl_surfaces(s['stl surfaces'], session, file_paths, attributes_only)

  if not attributes_only:
    scene_states = s.get('scenes', [])
    from ..scenes import restore_scenes
    restore_scenes(scene_states, session)

  if not attributes_only:
    mlist = session.top_level_models()
    session.next_id = max(m.id for m in mlist) + 1 if len(mlist) > 0 else 1


# -----------------------------------------------------------------------------
# Locate files using relative paths.
#
class File_Locator:

  def __init__(self, new_path, old_path):
    self.new_path = new_path
    self.old_path = old_path
    self.replaced = {}

  def find(self, path, ask = True):
    from os.path import isfile
    if self.new_path == self.old_path or self.old_path is None:
      p = path
    elif isfile(path):
      p = path
    else:
      # Try a relative path.
      sp = split_path(path)
      so = split_path(self.old_path)
      m = initial_match_count(sp, so)
      sn = split_path(self.new_path)
      from os.path import join
      p = join(*tuple(sn[:len(sn)-len(so)+m] + sp[m:]))

    if isfile(p):
      return p
    else:
      # Check if replacement file was chosen previously.
      repl = self.replaced
      if p in repl:
        return repl[p]
      else:
        # Check for previously replaced file in same directory as this one.
        from os.path import dirname, basename, join
        d = dirname(p)
        if d in repl:
          rp = join(repl[d], basename(p))
          if isfile(rp):
            return rp
        if ask:
          from .. import ui
          rp = ui.locate_file_dialog(path)	# Ask for replacement file with a dialog.
          if rp:
            repl[p] = rp
            repl[d] = dirname(rp)
            return rp

    return None

# -----------------------------------------------------------------------------
# Divide a file path into list of directories and filename.
#
def split_path(p):
  from os.path import basename, dirname
  b = basename(p)
  if b:
    return split_path(dirname(p)) + [b]
  return [p]

# -----------------------------------------------------------------------------
# Count number of initial entries of sequences a and b that match.
#
def initial_match_count(a,b):
  n = min(len(a),len(b))
  for i in range(n):
    if a[i] != b[i]:
      return i
  return n

# -----------------------------------------------------------------------------
#
def scene_state(session):
  return session_state(session, attributes_only = True)
def restore_scene(s, session):
  set_session_state(s, session, None, attributes_only = True)

# -----------------------------------------------------------------------------
#
view_parameters = (
  'center_of_rotation',
  'window_size',
  'background_color',
)

# -----------------------------------------------------------------------------
#
def view_state(viewer):
  v = dict((name,getattr(viewer,name)) for name in view_parameters)
  return v

# -----------------------------------------------------------------------------
#
def restore_view(vs, viewer):
  exclude = set(('window_size', 'camera_view', 'field_of_view'))
  for name in view_parameters:
    if name in vs and not name in exclude:
      setattr(viewer, name, vs[name])
  if 'camera_view' in vs:
    # Old session files had camera parameters saved with viewer state
    from ..geometry.place import Place
    c = viewer.camera
    c.position = Place(vs['camera_view'])
    c.field_of_view = vs['field_of_view']

  return True

# -----------------------------------------------------------------------------
#
camera_parameters = (
  'place',
  'field_of_view',
  'stereo',
  'eye_separation',
  'screen_distance',
)

# -----------------------------------------------------------------------------
#
def camera_state(camera):

  v = dict((name,getattr(camera,name)) for name in camera_parameters if hasattr(camera,name))
  v['place'] = camera.position.matrix
  return v

# -----------------------------------------------------------------------------
#
def restore_camera(cs, camera):

  exclude = ('place',)
  for name in camera_parameters:
    if name in cs and not name in exclude:
      setattr(camera, name, cs[name])
  from ..geometry.place import Place
  camera.position = Place(cs['place'])

# -----------------------------------------------------------------------------
#
light_parameters = (
  'key_light_direction',
  'key_light_intensity',
  'key_light_color',
  'fill_light_direction',
  'fill_light_intensity',
  'fill_light_color',
  'ambient_light_intensity',
  'ambient_light_color',
  'depth_cue_distance',
  'depth_cue_darkest',
  'move_lights_with_camera',
  )

# -----------------------------------------------------------------------------
#
def lighting_state(light_params):
  v = dict((name,getattr(light_params,name)) for name in light_parameters)
  return v

# -----------------------------------------------------------------------------
#
def restore_lighting(ls, version, light_params):
  for name in light_parameters:
    if name in ls:
      setattr(light_params, name, ls[name])
  if version <= 2 and 'fill_light_color' in ls:
    # Correct for introduction of light intensity parameters
    light_params.fill_light_color = tuple(2*c for c in light_params.fill_light_color)

# -----------------------------------------------------------------------------
#
material_parameters = (
  'ambient_reflectivity',
  'diffuse_reflectivity',
  'specular_reflectivity',
  'specular_exponent',
  )

# -----------------------------------------------------------------------------
#
def material_state(material):
  v = dict((name,getattr(material,name)) for name in material_parameters)
  return v

# -----------------------------------------------------------------------------
#
def restore_material(ms, version, material):
  for name in material_parameters:
    if name in ms:
      setattr(material, name, ms[name])
  if version <= 2 and 'ambient_reflectivity' in ms:
    # Correct for change in default ambient reflectivity
    material.ambient_reflectivity = (0.8/0.3)*material.ambient_reflectivity

# -----------------------------------------------------------------------------
#
class Session_Object_Ids:

  def __init__(self):
    self.next_object_id = 1
    self.object_to_id = {}
    self.id_to_object = {}

  def object_id(self, object):
    oid = self.object_to_id
    if not object in oid:
      id = self.next_object_id
      oid[object] = id
      self.id_to_object[id] = object
      self.next_object_id += 1
    return oid[object]

  def set_object_id(self, object, id):
    self.object_to_id[object] = id
    self.id_to_object[id] = object
    self.next_object_id = max(id+1, self.next_object_id)

  def object_from_id(self, id):
    ido = self.id_to_object
    return ido.get(id,None)
