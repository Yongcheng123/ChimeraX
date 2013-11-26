class Surface:

  def __init__(self, name):
    self.name = name
    self.id = None              # positive integer
    self.displayed = True
    from ..geometry.place import Place
    self.placement = Place()
    self.copies = []
    self.plist = []
    self.selected = False
    self.redraw_needed = False
    self.__destroyed__ = False

  def surface_pieces(self):
    return self.plist

  def newPiece(self, name = None):
    p = Surface_Piece(name)
    p.surface = self
    self.plist.append(p)
    self.redraw_needed = True
    return p

  def removePiece(self, p):
    self.plist.remove(p)
    p.delete()
    self.redraw_needed = True

  def removePieces(self, pieces):
    pset = set(pieces)
    self.plist = [p for p in self.plist if not p in pset]
    for p in pieces:
      p.delete()
    self.redraw_needed = True

  def removeAllPieces(self):
    self.removePieces(self.plist)

  def get_display(self):
    return self.displayed
  def set_display(self, display):
    self.displayed = display
    self.redraw_needed = True
  display = property(get_display, set_display)

  def get_place(self):
    return self.placement
  def set_place(self, place):
    self.placement = place
    self.redraw_needed = True
  place = property(get_place, set_place)

  def showing_transparent(self):
    for p in self.plist:
      if p.display and not p.opaque():
        return True
    return False

  def draw(self, viewer, draw_pass, reverse_order = False):
    plist = self.plist[::-1] if reverse_order else self.plist
    self.draw_pieces(plist, viewer, draw_pass)

  def draw_pieces(self, plist, viewer, draw_pass):

    if draw_pass == viewer.OPAQUE_DRAW_PASS:
      for p in plist:
        if p.display and p.opaque():
          p.draw(viewer)
    elif draw_pass in (viewer.TRANSPARENT_DRAW_PASS, viewer.TRANSPARENT_DEPTH_DRAW_PASS):
      ptransp = [p for p in plist if p.display and not p.opaque()]
      if ptransp:
        for p in ptransp:
          p.draw(viewer)

  def bounds(self):
    from ..geometry.bounds import union_bounds
    return union_bounds(p.bounds() for p in self.plist)

  def placed_bounds(self):
    b = self.bounds()
    if b is None or b == (None, None):
      return None
    if self.copies:
      copies = self.copies
    elif not self.placement.is_identity(tolerance = 0):
      copies = [self.placement]
    else:
      return b
    from ..geometry import bounds
    return bounds.copies_bounding_box(b, copies)

  def first_intercept(self, mxyz1, mxyz2):
    f = None
    sp = None
    # TODO handle surface model copies.
    from .. import _image3d
    for p in self.plist:
      if p.display:
        fmin = p.first_intercept(mxyz1, mxyz2)
        if not fmin is None and (f is None or fmin < f):
          f = fmin
          sp = p
    return f, Surface_Piece_Selection(sp)

  def delete(self):
    self.removeAllPieces()
  
class Surface_Piece(object):

  Solid = 'solid'
  Mesh = 'mesh'
  Dot = 'dot'

  TRIANGLE_DISPLAY_MASK = 8
  EDGE0_DISPLAY_MASK = 1
  ALL_EDGES_DISPLAY_MASK = 7

  def __init__(self, name = None):
    self.name = name
    self.vertices = None
    self.triangles = None
    self.normals = None
    self.shift_and_scale = None         # Instance copies
    self.copies34 = []                  # Instance matrices, 3x4
    self.copies44 = None                # Instance matrices, 4x4 opengl
    self.vertex_colors = None
    self.instance_colors = None
    self.edge_mask = None
    self.masked_edges = None
    self.display = True
    self.displayStyle = self.Solid
    self.color_rgba = (.7,.7,.7,1)
    self.texture = None
    self.textureCoordinates = None
    self.opaqueTexture = False
    self.__destroyed__ = False

    self.vao = None     	# Holds the buffer pointers and bindings
    self.shader = None		# VAO bindings are for this shader

    # Surface piece attribute name, shader variable name, instancing
    from .. import draw
    from numpy import uint32, uint8
    bufs = (('vertices', draw.VERTEX_BUFFER),
            ('normals', draw.NORMAL_BUFFER),
            ('shift_and_scale', draw.INSTANCE_SHIFT_AND_SCALE_BUFFER),
            ('copies44', draw.INSTANCE_MATRIX_BUFFER),
            ('vertex_colors', draw.VERTEX_COLOR_BUFFER),
            ('instance_colors', draw.INSTANCE_COLOR_BUFFER),
            ('textureCoordinates', draw.TEXTURE_COORDS_2D_BUFFER),
            ('elements', draw.ELEMENT_BUFFER),
            )
    obufs = []
    for a,v in bufs:
      b = draw.Buffer(v)
      b.surface_piece_attribute_name = a
      obufs.append(b)
    self.opengl_buffers = obufs
    self.element_buffer = obufs[-1]

  def delete(self):

    self.vertices = None
    self.triangles = None
    self.normals = None
    self.edge_mask = None
    self.texture = None
    self.textureCoordinates = None
    self.masked_edges = None
    for b in self.opengl_buffers:
      b.delete_buffer()

    self.vao = None

  def get_geometry(self):
    return self.vertices, self.triangles
  def set_geometry(self, g):
    self.vertices, self.triangles = g
    self.masked_edges = None
    self.edge_mask = None
    self.surface.redraw_needed = True
  geometry = property(get_geometry, set_geometry)

  def get_copies(self):
    return self.copies34
  def set_copies(self, copies):
    self.copies34 = copies
    self.copies44 = opengl_matrices(copies) if copies else None
    self.surface.redraw_needed = True
  copies = property(get_copies, set_copies)

  def new_bindings(self):
    from .. import draw
    self.vao = draw.Bindings()

  def bind_buffers(self):
    if self.vao is None:
      from .. import draw
      self.vao = draw.Bindings()
    self.vao.bind()

  def update_buffers(self, shader):

    shader_changed = (shader != self.shader)
    if shader_changed:
      self.shader = shader
      self.new_bindings()
      self.bind_buffers()

    for b in self.opengl_buffers:
      data = getattr(self, b.surface_piece_attribute_name)
      b.update_buffer(data, shader, shader_changed)

  def get_elements(self):

    ta = self.triangles
    if ta is None:
      return None
    if self.displayStyle == self.Mesh:
      if self.masked_edges is None:
        from .._image3d import masked_edges
        self.masked_edges = (masked_edges(ta) if self.edge_mask is None
                             else masked_edges(ta, self.edge_mask))
      ta = self.masked_edges
    return ta
  elements = property(get_elements, None)

  def element_count(self):
    return self.elements.size

  def get_color(self):
    return self.color_rgba
  def set_color(self, rgba):
    self.color_rgba = rgba
    self.surface.redraw_needed = True
  color = property(get_color, set_color)

  def opaque(self):
    return self.color_rgba[3] == 1 and (self.texture is None or self.opaqueTexture)

  def draw(self, viewer):

    if self.triangles is None:
      return

    self.bind_buffers()     # Need bound vao to compile shader

    p = self.set_shader(viewer)

    self.update_buffers(p)

    # Set color
    from .. import draw
    if self.instance_colors is None:
      draw.set_single_color(p, self.color_rgba)

    # Draw triangles
    etype = {self.Solid:draw.triangles,
             self.Mesh:draw.lines,
             self.Dot:draw.points}[self.displayStyle]
    self.element_buffer.draw_elements(etype, self.instance_count())

    if not self.texture is None:
      self.texture.unbind_texture()

  def set_shader(self, viewer):
    # Push special shader if needed.
    skw = {}
    from .. import draw
    lit = getattr(self, 'useLighting', True)
    if not lit:
      skw[draw.SHADER_LIGHTING] = False
    t = self.texture
    if not t is None:
      t.bind_texture()
      from .. import draw
      skw[draw.SHADER_TEXTURE_2D] = True
    if not self.shift_and_scale is None:
      skw[draw.SHADER_SHIFT_AND_SCALE] = True
    elif not self.copies44 is None:
      skw[draw.SHADER_INSTANCING] = True
#    if viewer.selected and not self.surface.selected:
#      skw[draw.SHADER_UNSELECTED] = True
    if self.surface.selected:
      skw[draw.SHADER_SELECTED] = True
    p = viewer.set_shader(**skw)
    return p

  def instance_count(self):
    if not self.shift_and_scale is None:
      ninst = len(self.shift_and_scale)
    elif not self.copies44 is None:
      ninst = len(self.copies44)
    else:
      ninst = None
    return ninst

  def get_triangle_and_edge_mask(self):
    return self.edge_mask
  def set_triangle_and_edge_mask(self, temask):
    self.edge_mask = temask
    self.surface.redraw_needed = True
  triangleAndEdgeMask = property(get_triangle_and_edge_mask,
                                 set_triangle_and_edge_mask)
    
  def set_edge_mask(self, emask):

    em = self.edge_mask
    if em is None:
      if emask is None:
        return
      em = (emask & self.ALL_EDGES_DISPLAY_MASK)
      em |= self.TRIANGLE_DISPLAY_MASK
      self.edge_mask = em
    else:
      if emask is None:
        em |= self.ALL_EDGES_DISPLAY_MASK
      else:
        em = (em & self.TRIANGLE_DISPLAY_MASK) | (em & emask)
      self.edge_mask = em

    self.surface.redraw_needed = True
    self.masked_edges = None

  def bounds(self):

    # TODO: cache surface piece bounds
    va = self.vertices
    if va is None or len(va) == 0:
      return None
    xyz_min = va.min(axis = 0)
    xyz_max = va.max(axis = 0)
    sas = self.shift_and_scale
    if not sas is None and len(sas) > 0:
      xyz = sas[:,:3]
      xyz_min += xyz.min(axis = 0)
      xyz_max += xyz.max(axis = 0)
      # TODO: use scale factors
    b = (xyz_min, xyz_max)
    if self.copies:
      from ..geometry import bounds
      b = bounds.copies_bounding_box(b, self.copies)
    return b

  def first_intercept(self, mxyz1, mxyz2):
    # TODO check intercept of bounding box as optimization
    # TODO handle surface piece shift_and_scale.
    f = None
    va, ta = self.geometry
    from .. import _image3d
    if len(self.copies) == 0:
      fmin, tmin = _image3d.closest_geometry_intercept(va, ta, mxyz1, mxyz2)
      if not fmin is None and (f is None or fmin < f):
        f = fmin
    else:
      for tf in self.copies:
        cxyz1, cxyz2 = tf.inverse() * (mxyz1, mxyz2)
        fmin, tmin = _image3d.closest_geometry_intercept(va, ta, cxyz1, cxyz2)
        if not fmin is None and (f is None or fmin < f):
          f = fmin
    return f

class Surface_Piece_Selection:
  def __init__(self, p):
    self.piece = p
  def description(self):
    p = self.piece
    n =  '%d triangles' % len(p.triangles) if p.name is None else p.name
    d = '%s %s' % (p.surface.name, n)
    return d
  def models(self):
    return [self.piece.surface]

def surface_image(qi, pos, size, surf = None):
    rgba = image_rgba_array(qi)
    if surf is None:
        surf = Surface('Image')
    return rgba_surface_piece(rgba, pos, size, surf)

def rgba_surface_piece(rgba, pos, size, surf):
    p = surf.newPiece()
    x,y = pos
    sx,sy = size
    from numpy import array, float32, uint32
    vlist = array(((x,y,0),(x+sx,y,0),(x+sx,y+sy,0),(x,y+sy,0)), float32)
    tlist = array(((0,1,2),(0,2,3)), uint32)
    tc = array(((0,0),(1,0),(1,1),(0,1)), float32)
    p.geometry = vlist, tlist
    p.color = (1,1,1,1)         # Modulates texture values
    p.useLighting = False
    p.textureCoordinates = tc
    from ..draw import Texture
    p.texture = Texture(rgba)
    return p

# Extract rgba values from a QImage.
def image_rgba_array(i):
    s = i.size()
    w,h = s.width(), s.height()
    from ..ui.qt import QtGui
    i = i.convertToFormat(QtGui.QImage.Format_RGB32)    #0ffRRGGBB
    b = i.bits()        # sip.voidptr
    n = i.byteCount()
    import ctypes
    si = ctypes.string_at(int(b), n)
    # si = b.asstring(n)  # Uses METH_OLDARGS in SIP 4.10, unsupported in Python 3

    # TODO: Handle big-endian machine correctly.
    # Bytes are B,G,R,A on little-endian machine.
    from numpy import ndarray, uint8
    rgba = ndarray(shape = (h,w,4), dtype = uint8, buffer = si)

    # Flip vertical axis.
    rgba = rgba[::-1,:,:].copy()

    # Swap red and blue to get R,G,B,A
    t = rgba[:,:,0].copy()
    rgba[:,:,0] = rgba[:,:,2]
    rgba[:,:,2] = t

    return rgba

def opengl_matrices(places):
  m34_list = tuple(p.matrix for p in places)
  n = len(m34_list)
  from numpy import empty, float32, transpose
  m = empty((n,4,4), float32)
  m[:,:,:3] = transpose(m34_list, axes = (0,2,1))
  m[:,:3,3] = 0
  m[:,3,3] = 1
  return m
