# vi: set expandtab shiftwidth=4 softtabstop=4:
'''
Drawing
=======
'''


class Drawing:
    '''
    A Drawing represents a tree of objects each consisting of a set of
    triangles in 3 dimensional space.  Drawings are used to draw molecules,
    density maps, geometric shapes and other models.  A Drawing has a name,
    a unique id number which is a positive integer, it can be displayed
    or hidden, has a placement in space, or multiple copies can be placed
    in space, and a drawing can be selected.  The coordinates, colors,
    normal vectors and other geometric and display properties are managed
    by the Drawing objects.

    A drawing can have child drawings.  The purpose of child drawings is
    for convenience in adding, removing, displaying and selecting parts
    of a scene. Child drawings are created by the new_drawing() method.

    Multiple copies of a drawing be drawn with specified positions and
    colors. Copy positions can be specified by a shift and scale factor but
    no rotation, useful for copies of spheres.  Each copy can be displayed
    or hidden, selected or unselected.

    The basic data defining the triangles is an N by 3 array of vertices
    (float32 numpy array) and an array that defines triangles as 3 integer
    index values into the vertex array which define the 3 corners of
    a triangle.  The triangle array is of shape T by 3 and is a numpy
    int32 array.  The filled triangles or a mesh consisting of just the
    triangle edges can be shown.  The vertices can be individually colored
    with linear interpolation of colors across triangles, or all triangles
    can be given the same color, or a 2-dimensional texture can be used to
    color the triangles with texture coordinates assigned to the vertices.
    Transparency values can be assigned to the vertices. Individual
    triangles or triangle edges in mesh display style can be hidden.
    An N by 3 float array gives normal vectors, one normal per vertex,
    for lighting calculations.

    Rendering of drawings is done with OpenGL.
    '''

    def __init__(self, name):

        self._redraw_needed = None

        self.name = name
        "Name of this drawing."

        from ..geometry.place import Places
        # Copies of drawing are placed at these positions:
        self._positions = Places()
        from numpy import array, uint8
        # Colors for each position, N by 4 uint8 numpy array:
        self._colors = array(((178, 178, 178, 255),), uint8)
        # bool numpy array, show only some positions:
        self._displayed_positions = None
        self._any_displayed_positions = True
        # bool numpy array, selected positions:
        self._selected_positions = None
        self._selected_triangles_mask = None  # bool numpy array
        self._child_drawings = []

        # Used by grayscale rendering for depth ordering:
        self.reverse_order_children = False
        """Whether to render the children in reverse order for properly
        handling transparency."""
        self._cached_bounds = None

        # Geometry and colors
        self.vertices = None
        """Vertices of the rendered geometry, a numpy N by 3 array of
        float32 values."""

        self.triangles = None
        '''
        Vertex indices for the corners of each triangle making up the
        rendered geometry, a numpy M by 3 array of int32 values.
        '''

        self.normals = None
        """Normal vectors of the rendered geometry, a numpy N by 3 array
        of float32 values."""

        self.vertex_colors = None
        '''
        R, G, B, A color and transparency for each vertex, a numpy N by
        4 array of uint8 values, can be None in which case a single color
        (attribute color) is used for the object.
        '''

        self._triangle_mask = None
        '''
        A mask that allows hiding some triangles, a numpy array of
        length M (# of triangles) of type bool. This is used for
        showing just a patch of a surface.
        '''

        self._edge_mask = None
        '''
        A mask that allows hiding some edges, a numpy array of length M
        (# of triangles) of type uint8, where bits 0, 1, and 2 are whether
        to display each edge of the triangle.  This is used for
        square mesh density map display.
        '''

        self.display_style = self.Solid
        '''
        Display style can be Drawing.Solid, Drawing.Mesh or Drawing.Dot.
        Only one style can be used for a single Drawing instance.
        '''

        self.texture = None
        '''
        Texture to use in coloring the surface, a graphics.Texture object.
        Only 2-dimensional textures are supported.  Can be None.
        '''

        self.texture_coordinates = None
        """Texture coordinates, an N by 2 numpy array of float32 values
        in range 0-1"""

        # 3d texture that modulates colors.
        self.ambient_texture = None
        '''
        A 3-dimensional texture that modulates the brightness of surface
        vertex colors.  Used for fast rendering of ambient occlusion
        lighting.
        '''

        # Drawing to texture coordinates.
        self.ambient_texture_transform = None
        """Transformation mapping vertex coordinates to ambient_texture
        coordinates, a geometry.Place object."""

        self.opaque_texture = False
        "Whether the texture for surface coloring is opaque or transparent."

        self.use_lighting = True
        """Whether to use lighting when rendering.  If false then a flat
        unshaded color will be shown."""

        # OpenGL drawing
        self._draw_shape = None
        self._draw_selection = None
        self._shader_opt = None                 # Cached shader options
        self._vertex_buffers = []               # Buffers used by both drawing and selection
        self._need_buffer_update = True

        self.was_deleted = False
        "Indicates whether this Drawing has been deleted."

    def redraw_needed(self, **kw):
        """Function called when the drawing has been changed to indicate
        that the graphics needs to be redrawn."""
        rn = self._redraw_needed
        if rn is not None:
            rn(**kw)

    def __setattr__(self, key, value):
        if key in self._effects_shader:
            self._shader_opt = None       # Cause shader update
            self.redraw_needed()
        if key in self._effects_buffers:
            self._need_buffer_update = True
            gc = key in ('vertices', 'triangles')
            if gc:
                self._cached_bounds = None
            sc = (gc or (key in ('_displayed_positions', '_positions')))
            self.redraw_needed(shape_changed=sc)

        super(Drawing, self).__setattr__(key, value)

    # Display styles
    Solid = 'solid'
    "Display style showing filled triangles."
    Mesh = 'mesh'
    "Display style showing only edges of triangles."
    Dot = 'dot'
    "Display style showing only dots at triangle vertices."

    def child_drawings(self):
        '''Return the list of surface pieces.'''
        return self._child_drawings

    def all_drawings(self):
        '''Return all drawings including self and children at all levels.'''
        dlist = [self]
        for d in self.child_drawings():
            dlist.extend(d.all_drawings())
        return dlist

    def new_drawing(self, name=None):
        '''Create a new empty child drawing.'''
        d = Drawing(name)
        self.add_drawing(d)
        return d

    def add_drawing(self, d):
        '''Add a child drawing.'''
        d.set_redraw_callback(self._redraw_needed)
        cd = self._child_drawings
        cd.append(d)
        if hasattr(d, 'parent') and d.parent is not None:
            # Reparent drawing.
            d.parent.remove_drawing(d, delete=False)
        d.parent = self
        if self.display:
            self.redraw_needed(shape_changed=True)

    def remove_drawing(self, d, delete=True):
        '''Remove a specified child drawing.'''
        self._child_drawings.remove(d)
        if delete:
            d.delete()
        self.redraw_needed(shape_changed=True, selection_changed=True)

    def remove_drawings(self, drawings, delete=True):
        '''Remove specified child drawings.'''
        dset = set(drawings)
        self._child_drawings = [d for d in self._child_drawings
                                if d not in dset]
        if delete:
            for d in drawings:
                d.delete()
        self.redraw_needed(shape_changed=True, selection_changed=True)

    def remove_all_drawings(self, delete=True):
        '''Remove all child drawings.'''
        self.remove_drawings(self.child_drawings(), delete)

    @property
    def drawing_lineage(self):
        '''Return a sequence of drawings from the root down to the current drawing.'''
        if hasattr(self, 'parent'):
            return self.parent.drawing_lineage + [self]
        else:
            return [self]

    def set_redraw_callback(self, redraw_needed):
        self._redraw_needed = redraw_needed
        for d in self.child_drawings():
            d.set_redraw_callback(redraw_needed)

    def get_display(self):
        return self._any_displayed_positions and len(self._positions) > 0

    def set_display(self, display):
        dp = self._displayed_positions
        if dp is None:
            from numpy import empty, bool
            self._displayed_positions = dp = empty((len(self._positions),),
                                                   bool)
        dp[:] = display
        self._any_displayed_positions = display
        self.redraw_needed(shape_changed=True)

    display = property(get_display, set_display)
    '''Whether or not the surface is drawn.'''

    def get_display_positions(self):
        return self._displayed_positions

    def set_display_positions(self, position_mask):
        from numpy import array_equal
        dp = self._displayed_positions
        if ((position_mask is None and dp is None) or
            (position_mask is not None and dp is not None and
             array_equal(position_mask, dp))):
            return
        self._displayed_positions = position_mask
        self._any_displayed_positions = (position_mask.sum() > 0)
        self.redraw_needed(shape_changed=True)

    display_positions = property(get_display_positions, set_display_positions)
    '''Mask specifying which copies are displayed.'''

    def get_selected(self):
        sp = self._selected_positions
        tmask = self._selected_triangles_mask
        return (((sp is not None) and sp.sum() > 0) or
                ((tmask is not None) and tmask.sum() > 0))

    def set_selected(self, sel):
        if sel:
            sp = self._selected_positions
            if sp is None:
                from numpy import ones, bool
                self._selected_positions = ones(len(self.positions), bool)
            else:
                sp[:] = True
        else:
            self._selected_positions = None
            self._selected_triangles_mask = None
        self.redraw_needed(selection_changed=True)

    selected = property(get_selected, set_selected)
    '''Whether or not the drawing is selected.'''

    def get_selected_positions(self):
        return self._selected_positions

    def set_selected_positions(self, spos):
        self._selected_positions = spos
        self.redraw_needed(selection_changed=True)

    selected_positions = property(get_selected_positions,
                                  set_selected_positions)
    '''Mask specifying which drawing positions are selected.'''

    def get_selected_triangles_mask(self):
        return self._selected_triangles_mask

    def set_selected_triangles_mask(self, tmask):
        self._selected_triangles_mask = tmask
        self.redraw_needed(selection_changed=True)

    selected_triangles_mask = property(get_selected_triangles_mask,
                                       set_selected_triangles_mask)
    '''Mask specifying which triangles are selected.'''

    def any_part_selected(self):
        '''Is any part of this Drawing or its children selected.'''
        if self.selected:
            return True
        for d in self.child_drawings():
            if d.any_part_selected():
                return True
        return False

    def fully_selected(self):
        '''Is the entire Drawing including children selected.'''
        sp = self._selected_positions
        if sp is not None and sp.sum() == len(sp):
            return True
        for d in self.child_drawings():
            if not d.fully_selected():
                return False
        return True

    def clear_selection(self):
        '''Unselect this drawing. Child drawings may remain selected.'''
        self.selected = False
        self.redraw_needed(selection_changed=True)

    def promote_selection(self):
        '''
        Select the next larger containing group.  If one child is
        selected, then all become selected.
        '''
        pd = self._deepest_promotable_drawings()
        if len(pd) == 0:
            return

        plevel = min(level for level, drawing in pd)
        pdrawings = tuple(d for level, d in pd if level == plevel)
        prevsel = tuple((d, d.selected_positions.copy()) for d in pdrawings)
        if hasattr(self, 'promotion_tower'):
            self.promotion_tower.append(prevsel)
        else:
            self.promotion_tower = [prevsel]
        for d in pdrawings:
            d.selected = True

    # A drawing is promotable if some children are fully selected and others
    # are unselected, or if some copies are selected and other copies are
    # unselected.
    def _deepest_promotable_drawings(self, level=0):

        sp = self._selected_positions
        if sp is not None:
            ns = sp.sum()
            if ns == len(sp):
                return []         # Fully selected
        cd = self.child_drawings()
        if cd:
            nfsel = [d for d in cd if not d.fully_selected()]
            if nfsel:
                pd = sum((d.promotable_drawings(level + 1) for d in nfsel), [])
                if len(pd) == 0 and len(nfsel) < len(cd):
                    pd = [(level + 1, d) for d in nfsel]
                return pd
        if sp is not None and ns < len(sp):
            return [(level, self)]
        return []

    def demote_selection(self):
        '''If the selection has previously been promoted, this returns
        it to the previous smaller selection.'''
        pt = getattr(self, 'promotion_tower', None)
        if pt:
            for d, sp in pt.pop():
                d.selected_positions = sp

    def clear_selection_promotion_history(self):
        '''
        Forget the selection history promotion history.
        This is used when the selection is changed manually.
        '''
        if hasattr(self, 'promotion_tower'):
            delattr(self, 'promotion_tower')

    def get_position(self):
        return self._positions[0]

    def set_position(self, pos):
        from ..geometry.place import Places
        self._positions = Places([pos])
        self.redraw_needed(shape_changed=True)

    @property
    def scene_position(self):
        from ..geometry.place import product
        return product([d.position for d in self.drawing_lineage])

    position = property(get_position, set_position)
    '''Position and orientation of the surface in space.'''

    def get_positions(self, displayed_only=False):
        if displayed_only:
            return self._positions.masked(self.display_positions)
        return self._positions

    def set_positions(self, positions):
        self._positions = positions
        self._displayed_positions = None
        self._selected_positions = None
        self.redraw_needed(shape_changed=True)

    positions = property(get_positions, set_positions)
    '''
    Copies of the surface piece are placed using a 3 by 4 matrix with
    the first 3 columns giving a linear transformation, and the last
    column specifying a shift.
    '''

    def number_of_positions(self, displayed_only=False):
        '''Number of positions the Drawing is placed at.'''
        if displayed_only and not self.display:
            return 0
        dp = self.display_positions
        np = len(self.positions) if dp is None else dp.sum()
        return np

    def get_color(self):
        return self._colors[0]

    def set_color(self, rgba):
        from numpy import empty, uint8
        c = empty((len(self._positions), 4), uint8)
        c[:, :] = rgba
        self._colors = c
        self.redraw_needed()

    color = property(get_color, set_color)
    '''Single color of drawing used when per-vertex coloring is not
    specified.'''

    def get_colors(self):
        return self._colors

    def set_colors(self, rgba):
        from numpy import ndarray, array, uint8
        c = rgba if isinstance(rgba, ndarray) else array(rgba, uint8)
        self._colors = c
        self.redraw_needed()

    colors = property(get_colors, set_colors)
    '''Color for each position used when per-vertex coloring is not
    specified.'''

    def _opaque(self):
        # TODO: Should render transparency for each copy separately
        return self._colors[0][3] == 255 and (self.texture is None or
                                              self.opaque_texture)

    def showing_transparent(self):
        '''Are any transparent objects being displayed. Includes all
        children.'''
        if self.display:
            if not self.empty_drawing() and not self._opaque():
                return True
            for d in self.child_drawings():
                if d.showing_transparent():
                    return True
        return False

    def get_geometry(self):
        return self.vertices, self.triangles

    def set_geometry(self, g):
        self.vertices, self.triangles = g
        self._edge_mask = None
        self._triangle_mask = None
        self.redraw_needed(shape_changed=True)

    geometry = property(get_geometry, set_geometry)
    '''Geometry is the array of vertices and array of triangles.'''

    def all_geometries(self):
        '''
        Return geometry of this drawing and all its chidren as a list of
        3-tuples, each containing the vertices, triangles, and a Places
        object that contains all the scene locations of those vertices
        and triangles.
        '''
        va, ta = self.geometry
        g = [] if va is None else [(va, ta, self.positions)]
        for d in self.child_drawings():
            g.extend([(_va, _ta, self.positions * dpositions)
                      for _va, _ta, dpositions in d.all_geometries()])
        return g

    def empty_drawing(self):
        '''Does this drawing have no geometry? Does not consider child
        drawings.'''
        return self.vertices is None

    def number_of_triangles(self, displayed_only=False):
        '''Return the number of triangles including all child drawings
        and all positions.'''
        np = self.number_of_positions(displayed_only)
        if np == 0:
            return 0
        t = self.triangles
        tc = 0 if t is None else np * len(t)
        for d in self.child_drawings():
            tc += np * d.number_of_triangles(displayed_only)
        return tc

    OPAQUE_DRAW_PASS = 'opaque'
    "Draw pass to render only opaque drawings."
    TRANSPARENT_DRAW_PASS = 'transparent'
    "Draw pass to render only transparent drawings."
    TRANSPARENT_DEPTH_DRAW_PASS = 'transparent depth'
    "Draw pass to render only the depth of transparent drawings."
    SELECTION_DRAW_PASS = 'selection'
    "Draw pass to render only the selected parts of drawings."

    def draw(self, renderer, place, draw_pass, selected_only=False):
        '''Draw this drawing and children using the given draw pass.'''

        if not self.display:
            return

        if not self.empty_drawing():
            self.draw_self(renderer, place, draw_pass, selected_only)

        if self.child_drawings():
            sp = self._selected_positions
            for i, p in enumerate(self.positions):
                so = selected_only and (sp is None or not sp[i])
                pp = place if p.is_identity() else place * p
                self._draw_children(renderer, pp, draw_pass, so)

    def draw_self(self, renderer, place, draw_pass, selected_only=False):
        '''Draw this drawing without children using the given draw pass.'''

        if selected_only and not self.selected:
            return

        if (len(self.positions) == 1 and
                self.positions.shift_and_scale_array() is None):
            p = self.position
            pp = place if p.is_identity() else place * p
        else:
            pp = place
        renderer.set_model_matrix(pp)

        if draw_pass == self.OPAQUE_DRAW_PASS:
            if self._opaque():
                self._draw_geometry(renderer, selected_only)
        elif draw_pass in (self.TRANSPARENT_DRAW_PASS,
                           self.TRANSPARENT_DEPTH_DRAW_PASS):
            if not self._opaque():
                self._draw_geometry(renderer, selected_only)
        elif draw_pass == self.SELECTION_DRAW_PASS:
            self._draw_geometry(renderer, selected_only)

    def _draw_children(self, renderer, place, draw_pass, selected_only=False):
        dlist = self.child_drawings()
        if self.reverse_order_children:
            dlist = dlist[::-1]
        for d in dlist:
            d.draw(renderer, place, draw_pass, selected_only)

    def _draw_geometry(self, renderer, selected_only=False):
        ''' Draw the geometry.'''

        if self.vertices is None:
            return

        if len(self._vertex_buffers) == 0:
            self._create_vertex_buffers()

        ds = self._draw_selection if selected_only else self._draw_shape
        ds.activate_shader_and_bindings(renderer, self._shader_options())

        if self._need_buffer_update:
            # Updating buffers has to be done after activating bindings to
            # avoid changing the element buffer binding for the previously
            # active bindings.
            self._update_buffers()
            self._need_buffer_update = False
        ds.update_bindings()

        # Set color
        if self.vertex_colors is None and len(self._colors) == 1:
            renderer.set_single_color([c / 255.0 for c in self._colors[0]])

        t = self.texture
        if t is not None:
            t.bind_texture()

        at = self.ambient_texture
        if at is not None:
            at.bind_texture()
            renderer.set_ambient_texture_transform(
                self.ambient_texture_transform)

        # Draw triangles
        ds.draw(self.display_style)

        if self.texture is not None:
            self.texture.unbind_texture()

    def _shader_options(self):
        sopt = self._shader_opt
        if sopt is None:
            sopt = 0
            from .opengl import Render
            if self.use_lighting:
                sopt |= Render.SHADER_LIGHTING
            if (self.vertex_colors is not None) or len(self._colors) > 1:
                sopt |= Render.SHADER_VERTEX_COLORS
            if self.texture is not None:
                sopt |= Render.SHADER_TEXTURE_2D
            if self.ambient_texture is not None:
                sopt |= Render.SHADER_TEXTURE_3D_AMBIENT
            if self.positions.shift_and_scale_array() is not None:
                sopt |= Render.SHADER_SHIFT_AND_SCALE
            elif len(self.positions) > 1:
                sopt |= Render.SHADER_INSTANCING
            self._shader_opt = sopt
        return sopt

    _effects_shader = set(
        ('use_lighting', 'vertex_colors', '_colors', 'texture',
         'ambient_texture', '_positions'))

    # Update the contents of vertex, element and instance buffers
    # if associated arrays have changed.
    def _update_buffers(self):

        p, c = self.positions, self.colors
        pm = self._position_mask()
        pmsel = self._position_mask(True)
        ta = self.triangles
        em = self._edge_mask if self.display_style == self.Mesh else None
        tm = self._triangle_mask
        tmsel = self._selected_triangles_mask
        if tm is not None:
            # Combine selected and displayed triangle masks
            if tmsel is not None:
                from numpy import logical_and
                tmsel = logical_and(tmsel, tm)
            else:
                tmsel = tm

        ds, dss = self._draw_shape, self._draw_selection
        ds.update_buffers(p, c, pm, ta, tm, em)		# Update drawing buffers
        dss.update_buffers(p, c, pmsel, ta, tmsel, em)  # Update selection buffers

        # Update buffers shared by drawing and selection
        for b in self._vertex_buffers:
            data = getattr(self, b.buffer_attribute_name)
            if b.update_buffer_data(data):
                ds._update_buffer_bindings.add(b)
                dss._update_buffer_bindings.add(b)

    def _position_mask(self, selected_only=False):
        dp = self._displayed_positions        # bool array
        if selected_only:
            sp = self._selected_positions
            if sp is not None:
                import numpy
                dp = sp if dp is None else numpy.logical_and(dp, sp)
        return dp

    def bounds(self, positions=True):
        '''
        The bounds of drawing and displayed children and displayed positions.
        '''
        dbounds = [d.bounds() for d in self.child_drawings() if d.display]
        if not self.empty_drawing():
            dbounds.append(self._geometry_bounds())
        from ..geometry import bounds
        b = bounds.union_bounds(dbounds)
        if positions:
            b = bounds.copies_bounding_box(
                b, self.get_positions(displayed_only=True))
        return b

    def _geometry_bounds(self):
        '''
        Return the bounds of the drawing not including positions nor children.
        '''
        cb = self._cached_bounds
        if cb is not None:
            return cb

        va = self.vertices
        if va is None or len(va) == 0:
            return None
        xyz_min = va.min(axis=0)
        xyz_max = va.max(axis=0)
        from ..geometry.bounds import Bounds
        b = Bounds(xyz_min, xyz_max)
        self._cached_bounds = b
        return b

    def first_intercept(self, mxyz1, mxyz2, exclude=None):
        '''
        Find the first intercept of a line segment with the displayed part
        of this drawing and its children.  Return a Pick object for the intercepted item.
        The Pick object has a distance attribute giving the fraction (0-1)
        along the segment where the intersection occurs.
        For no intersection None is returned.  This routine is used for
        selecting objects, for identifying objects during mouse-over, and
        to determine the front-most point in the center of view to be used
        as the interactive center of rotation.
        '''
        pclosest = None
        if self.display and (exclude is None or not hasattr(self, exclude)):
            if not self.empty_drawing():
                p = self._first_intercept_excluding_children(mxyz1, mxyz2)
                if p and (pclosest is None or p.distance < pclosest.distance):
                    pclosest = p
            cd = self.child_drawings()
            if cd:
                pos = [p.inverse() * (mxyz1, mxyz2) for p in self.positions]
                for d in cd:
                    if d.display and (exclude is None or not hasattr(d, exclude)):
                        for cp, (cxyz1, cxyz2) in enumerate(pos):
                            p = d.first_intercept(cxyz1, cxyz2, exclude)
                            if p and (pclosest is None or p.distance < pclosest.distance):
                                pclosest = p
        return pclosest

    def _first_intercept_excluding_children(self, mxyz1, mxyz2):
        if self.empty_drawing():
            return None
        va = self.vertices
        ta = self.masked_triangles
        if ta.shape[1] != 3:
            # TODO: Intercept only for triangles, not lines or points.
            return None
        # TODO: Check intercept of bounding box as optimization
        p = None
        from ._graphics import closest_geometry_intercept
        if self.positions.is_identity():
            fmin, tmin = closest_geometry_intercept(va, ta, mxyz1, mxyz2)
            if fmin is not None:
                p = TrianglePick(fmin, tmin, 0, self)
        else:
            # TODO: This will be very slow for large numbers of copies.
            dp = self._displayed_positions
            for c, tf in enumerate(self.positions):
                if dp is None or dp[c]:
                    cxyz1, cxyz2 = tf.inverse() * (mxyz1, mxyz2)
                    fmin, tmin = closest_geometry_intercept(va, ta, cxyz1, cxyz2)
                    if fmin is not None and (p is None or fmin < p.distance):
                        p = TrianglePick(fmin, tmin, c, self)
        return p

    def delete(self):
        '''
        Delete drawing and all child drawings.
        '''
        self._delete_geometry()
        self.remove_all_drawings()

    def _delete_geometry(self):
        '''Release all the arrays and graphics memory associated with
        the surface piece.'''
        self._positions = None
        self._colors = None
        self._displayed_positions = None
        self.vertices = None
        self.triangles = None
        self.normals = None
        self._edge_mask = None
        self._triangle_mask = None
        self.texture = None
        self.texture_coordinates = None

        for b in self._vertex_buffers:
            b.delete_buffer()

        self.was_deleted = True

    def _create_vertex_buffers(self):
        from . import opengl
        vbufs = (
            ('vertices', opengl.VERTEX_BUFFER),
            ('normals', opengl.NORMAL_BUFFER),
            ('vertex_colors', opengl.VERTEX_COLOR_BUFFER),
            ('texture_coordinates', opengl.TEXTURE_COORDS_2D_BUFFER),
        )

        self._vertex_buffers = vb = []
        for a, v in vbufs:
            b = opengl.Buffer(v)
            b.buffer_attribute_name = a
            vb.append(b)

        self._draw_shape = _DrawShape(vb)
        self._draw_selection = _DrawShape(vb)

    _effects_buffers = set(
        ('vertices', 'normals', 'vertex_colors', 'texture_coordinates',
         '_displayed_positions', '_colors', '_positions',
         '_edge_mask', '_triangle_mask', '_selected_triangles_mask'))

    EDGE0_DISPLAY_MASK = 1
    ALL_EDGES_DISPLAY_MASK = 7
    '''Edge mask for displaying all three triangle edges (bits 0, 1, 2).'''

    def get_triangle_mask(self):
        return self._triangle_mask

    def set_triangle_mask(self, tmask):
        self._triangle_mask = tmask
        self.redraw_needed(shape_changed=True)

    triangle_mask = property(get_triangle_mask, set_triangle_mask)
    '''
    The triangle mask is a 1-dimensional bool numpy array of
    length equal to the number of triangles used to control display
    of individual triangles.
    '''

    def get_edge_mask(self):
        return self._edge_mask

    def set_edge_mask(self, emask):
        self._edge_mask = emask
        self.redraw_needed(shape_changed=True)

    edge_mask = property(get_edge_mask, set_edge_mask)
    '''
    The edge mask is a 1-dimensional uint8 numpy array of
    length equal to the number of triangles.  The lowest 3 bits are used
    to control display of the 3 triangle edges in mesh mode.
    '''

    DRAWING_STATE_VERSION = 1

    @property
    def masked_triangles(self):
        ta = self.triangles
        tm = self._triangle_mask
        return ta if tm is None else ta[tm,:]

    def take_snapshot(self, phase, session, flags):
        from ..session import State
        if phase == State.CLEANUP_PHASE:
            for c in self.child_drawings():
                c.take_snapshot(session, phase, flags)
            return
        if phase != State.SAVE_PHASE:
            return
        # all drawing objects should have the same version
        data = {
            'children': [c.take_snapshot(session, phase, flags)[1]
                         for c in self.child_drawings()],
            'name': self.name,
            'vertices': self.vertices,
            'triangles': self.triangles,
            'normals': self.normals,
            'vertex_colors': self.vertex_colors,
            'triangle_mask': self._triangle_mask,
            'edge_mask': self._edge_mask,
            'display_style': self.display_style,
            'texture': self.texture,
            'ambient_texture ': self.ambient_texture,
            'ambient_texture_transform': self.ambient_texture_transform,
            'use_lighting': self.use_lighting,

            'display': self.display,
            'display_positions': self.display_positions,
            'selected': self.selected,
            'selected_positions': self.selected_positions,
            'position': self.position,
            'positions': self.positions,
            'selected_triangles_mask': self.selected_triangles_mask,
            'color': self.color,
            'colors': self.colors,
            'geometry': self.geometry,
        }
        return self.DRAWING_STATE_VERSION, data

    def restore_snapshot(self, phase, session, version, data):
        from ..session import State, RestoreError
        if version != self.DRAWING_STATE_VERSION:
            raise RestoreError("Unexpected version or data")
        if phase != State.CREATE_PHASE:
            return
        for child_data in data['children']:
            child = self.new_drawing()
            child.restore_snapshot(phase, session, version, child_data)
        self.name = data['name']
        self.vertices = data['vertices']
        self.triangles = data['triangles']
        self.normals = data['normals']
        self.vertex_colors = data['vertex_colors']
        self._triangle_mask = data['triangle_mask']
        self._edge_mask = data['edge_mask']
        self.display_style = data['display_style']
        self.texture = data['texture']
        self.ambient_texture = data['ambient_texture ']
        self.ambient_texture_transform = data['ambient_texture_transform']
        self.use_lighting = data['use_lighting']

        self.display = data['display']
        self.selected = data['selected']
        self.position = data['position']
        self.positions = data['positions']
        self.selected_triangles_mask = data['selected_triangles_mask']
        self.color = data['color']
        self.colors = data['colors']
        self.geometry = data['geometry']
        self.display_positions = data['display_positions']
        self.selected_positions = data['selected_positions']

    def reset_state(self):
        # delay implementing until needed
        raise NotImplemented()


def draw_drawings(renderer, cvinv, drawings, opaque_only = False):
    '''
    Render opaque and transparent draw passes for a given set of drawings,
    and given camera view (inverse camera transform).
    '''
    r = renderer
    r.set_view_matrix(cvinv)
    from ..geometry.place import Place
    p = Place()
    _draw_multiple(drawings, r, p, Drawing.OPAQUE_DRAW_PASS)
    if not opaque_only and _any_transparent_drawings(drawings):
        r.draw_transparent(
            lambda: _draw_multiple(drawings, r, p,
                                   Drawing.TRANSPARENT_DEPTH_DRAW_PASS),
            lambda: _draw_multiple(drawings, r, p,
                                   Drawing.TRANSPARENT_DRAW_PASS))


def _draw_multiple(drawings, r, place, draw_pass):
    selected_only = (draw_pass == Drawing.SELECTION_DRAW_PASS)
    for d in drawings:
        d.draw(r, place, draw_pass, selected_only)


def _any_transparent_drawings(drawings):
    for d in drawings:
        if d.showing_transparent():
            return True
    return False


def draw_depth(renderer, cvinv, drawings, opaque_only = True):
    '''Render only the depth buffer (not colors).'''
    r = renderer
    r.disable_shader_capabilities(r.SHADER_LIGHTING | r.SHADER_VERTEX_COLORS |
                                  r.SHADER_TEXTURE_2D)
    draw_drawings(r, cvinv, drawings, opaque_only)
    r.disable_shader_capabilities(0)


def draw_overlays(drawings, renderer):
    '''Render drawings using an identity projection matrix with no
    depth test.'''
    r = renderer
    r.set_projection_matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0),
                             (0, 0, 0, 1)))
    from ..geometry import place
    p0 = place.identity()
    r.set_view_matrix(p0)
    r.set_model_matrix(p0)
    r.enable_depth_test(False)
    _draw_multiple(drawings, r, p0, Drawing.OPAQUE_DRAW_PASS)
    r.enable_blending(True)
    _draw_multiple(drawings, r, p0, Drawing.TRANSPARENT_DRAW_PASS)
    r.enable_blending(False)
    r.enable_depth_test(True)


def draw_2d_overlays(drawings, renderer):
    '''Render drawings using an identity projection matrix with no
    depth test.'''
    r = renderer
    ww, wh = r.render_size()
    from .camera import ortho
    projection = ortho(0, ww, 0, wh, -1, 1)
    r.set_projection_matrix(projection)
    from ..geometry import place
    p0 = place.identity()
    r.set_view_matrix(p0)
    r.set_model_matrix(p0)
    r.enable_depth_test(False)
    _draw_multiple(drawings, r, p0, Drawing.OPAQUE_DRAW_PASS)
    r.enable_blending(True)
    _draw_multiple(drawings, r, p0, Drawing.TRANSPARENT_DRAW_PASS)
    r.enable_blending(False)
    r.enable_depth_test(True)


def draw_outline(renderer, cvinv, drawings):
    '''Draw the outlines of selected parts of the specified drawings.'''
    r = renderer
    r.set_view_matrix(cvinv)
    r.start_rendering_outline()
    from ..geometry.place import Place
    p = Place()
    _draw_multiple(drawings, r, p, Drawing.SELECTION_DRAW_PASS)
    r.finish_rendering_outline()


def _element_type(display_style):
    from .opengl import Buffer
    if display_style == Drawing.Solid:
        t = Buffer.triangles
    elif display_style == Drawing.Mesh:
        t = Buffer.lines
    elif display_style == Drawing.Dot:
        t = Buffer.points
    return t


class _DrawShape:

    def __init__(self, vertex_buffers):

        # Arrays derived from positions, colors and geometry
        self.instance_shift_and_scale = None   # N by 4 array, (x, y, z, scale)
        self.instance_matrices = None	    # matrices for displayed instances
        self.instance_colors = None
        self.elements = None                # Triangles after mask applied
        self.masked_edges = None
        self._edge_mask = None
        self._tri_mask = None

        # OpenGL rendering
        self.bindings = None    	      # Shader variable bindings in an opengl vertex array object
        self._update_buffer_bindings = set(vertex_buffers)  # New or reallocated buffers requiring update of
                                                            #   shader variable bindings
        self.vertex_buffers = vertex_buffers
        self.element_buffer = None
        self.instance_buffers = []

    def delete(self):

        self.masked_edges = None
        self.instance_shift_and_scale = None
        self.instance_matrices = None
        self.instance_colors = None
        if self.element_buffer:
            self.element_buffer.delete_buffer()
            for b in self.instance_buffers:
                b.delete_buffer()

        self.bindings = None

    def draw(self, display_style):

        eb = self.element_buffer
        etype = _element_type(display_style)
        ni = self.instance_count()
        if ni > 0:
            eb.draw_elements(etype, ni)

    def create_opengl_buffers(self):

        from . import opengl
        a, v = ('elements', opengl.ELEMENT_BUFFER)
        self.element_buffer = eb = opengl.Buffer(v)
        eb.buffer_attribute_name = a

        ub = self._update_buffer_bindings
        ub.add(eb)

        ibufs = (
            ('instance_shift_and_scale',
                opengl.INSTANCE_SHIFT_AND_SCALE_BUFFER),
            ('instance_matrices', opengl.INSTANCE_MATRIX_BUFFER),
            ('instance_colors', opengl.INSTANCE_COLOR_BUFFER),
        )
        self.instance_buffers = ib = []
        for a, v in ibufs:
            b = opengl.Buffer(v)
            b.buffer_attribute_name = a
            ib.append(b)

        ub.update(ib)

    def update_buffers(self, positions, colors, position_mask, triangles,
                       tmask, edge_mask):

        if self.element_buffer is None:
            self.create_opengl_buffers()

        self.elements = self.masked_elements(triangles, tmask, edge_mask)

        self.update_instance_arrays(positions, colors, position_mask)

        for b in self.instance_buffers + [self.element_buffer]:
            data = getattr(self, b.buffer_attribute_name)
            if b.update_buffer_data(data):
                self._update_buffer_bindings.add(b)

    def update_instance_arrays(self, positions, colors, position_mask):
        sas = positions.shift_and_scale_array()
        np = len(positions)
        ic = colors if np > 1 or sas is not None else None
        im = positions.opengl_matrices() if sas is None and np > 1 else None

        pm = position_mask
        if pm is not None:
            im = im[pm, :, :] if im is not None else None
            ic = ic[pm, :] if ic is not None else None
            sas = sas[pm, :] if sas is not None else None

        self.instance_matrices = im
        self.instance_shift_and_scale = sas
        self.instance_colors = ic

    def instance_count(self):
        im = self.instance_matrices
        isas = self.instance_colors
        if im is not None:
            ninst = len(im)
        elif isas is not None:
            ninst = len(isas)
        else:
            ninst = 1
        return ninst

    def masked_elements(self, triangles, tmask, edge_mask):

        ta = triangles
        if ta is None:
            return None
        if tmask is not None:
            ta = ta[tmask, :]
        if edge_mask is not None:
            # TODO: Need to reset masked_edges if edge_mask changed.
            me = self.masked_edges
            if (me is None or edge_mask is not self._edge_mask or
                    tmask is not self._tri_mask):
                kw = {}
                if edge_mask is not None:
                    kw['edge_mask'] = edge_mask
                if tmask is not None:
                    kw['triangle_mask'] = tmask
                from ._graphics import masked_edges
                self.masked_edges = me = masked_edges(ta, **kw)
                self._edge_mask, self._tri_mask = edge_mask, tmask
            ta = me
        return ta

    def activate_shader_and_bindings(self, renderer, sopt):
        # Need OpenGL VAO bound to compile shader
        self.activate_bindings()
        shader = renderer.shader(sopt)
        renderer.use_shader(shader)

    def update_bindings(self):
        bufs = self._update_buffer_bindings
        if bufs:
            bi = self.bindings
            for b in bufs:
                bi.bind_shader_variable(b)
            bufs.clear()

    def activate_bindings(self):
        if self.bindings is None:
            from . import opengl
            self.bindings = opengl.Bindings()
            self._update_buffer_bindings.update(self.all_buffers())
        self.bindings.activate()

    def all_buffers(self):
        bufs = self.vertex_buffers + self.instance_buffers
        ebuf = self.element_buffer
        if ebuf:
            bufs += [ebuf]
        return bufs

class Pick:
    '''
    A picked object returned by first_intercept() method of the Drawing class.
    '''
    def __init__(self, distance):
        self.distance = distance

    def description(self):
        '''Text description of the picked object.'''
        return None

    def drawing(self):
        '''The drawing immediately containing the picked object.'''
        return None

    def select(self, toggle=False):
        '''Cause this picked object to be marked as selected.'''
        pass

    def id_string(self):
        '''
        A text identifier that can be used in commands to specified the
        picked Model. The id number is not a standard attribute
        of Drawing, only of Model which is a subclass of Drawing,
        and is a tuple of integers.
        '''
        d = self.drawing()
        while True:
            if hasattr(d, 'id') and d.id is not None:
                s = '#' + '.'.join(('%d' % id) for id in d.id)
                return s
            if hasattr(d, 'parent') and not d.parent is None:
                d = d.parent
            else:
                break
        return '?'

class TrianglePick(Pick):
    '''
    A picked triangle of a drawing.
    '''
    def __init__(self, distance, triangle_number, copy_number, drawing):
        Pick.__init__(self, distance)
        self.triangle_number = triangle_number
        self._copy = copy_number
        self._drawing = drawing

    def description(self):
        d = self.drawing()
        fields = [self.id_string()]
        if d.name is not None:
            fields.append(d.name)
        if len(d.positions) > 1:
            fields.append('copy %d' % self._copy)
        fields.append('triangle %d of %d' % (self.triangle_number, len(d.triangles)))
        desc = ' '.join(fields)
        return desc

    def drawing(self):
        return self._drawing

    def select(self, toggle=False):
        d = self.drawing()
        pmask = d.selected_positions
        if pmask is None:
            from numpy import zeros, bool
            pmask = zeros((len(d.positions),), bool)
        c = self._copy
        pmask[c] = not pmask[c] if toggle else 1
        d.selected_positions = pmask


def rgba_drawing(rgba, pos=(-1, -1), size=(2, 2), drawing=None):
    '''
    Make a drawing that is a single rectangle with a texture to show an
    RGBA image on it.
    '''
    from . import opengl
    t = opengl.Texture(rgba)
    d = _texture_drawing(t, pos, size, drawing)
    return d


def _texture_drawing(texture, pos=(-1, -1), size=(2, 2), drawing=None):
    '''
    Make a drawing that is a single rectangle colored with a texture.
    '''
    d = drawing.new_drawing() if drawing else Drawing('rgba')
    x, y = pos
    sx, sy = size
    from numpy import array, float32, uint32
    vlist = array(((x, y, 0),
                   (x + sx, y, 0),
                   (x + sx, y + sy, 0),
                   (x, y + sy, 0)), float32)
    tlist = array(((0, 1, 2), (0, 2, 3)), uint32)
    tc = array(((0, 0), (1, 0), (1, 1), (0, 1)), float32)
    d.geometry = vlist, tlist
    d.color = (255, 255, 255, 255)         # Modulates texture values
    d.use_lighting = False
    d.texture_coordinates = tc
    d.texture = texture
    return d


def _draw_texture(texture, renderer):
    d = _texture_drawing(texture)
    d.opaque_texture = True
    draw_overlays([d], renderer)
