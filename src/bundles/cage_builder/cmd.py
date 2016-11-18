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

def cage(session, cage, place_model = None, polygon_sides = 6,
         surface_only = False, resolution = None):
    '''Build polygonal cages and place molecules on faces.

    Parameters
    ----------
    cage : Structure
      Cage model.
    place_model : Model
      Place copies of model on each n-sided polygon of cage.
    polygon_sides : int
      Place on polygons with this number of sides.
    surface_only : bool
      Instead of showing instances of the molecule, show instances
      of surfaces of each chain.  The chain surfaces are computed if
      they do not already exist.
    resolution : float
      Resolution for computing surfaces when surface_only is true.
    '''

    from chimerax.core.commands import AnnotationError
    if place_model is None:
        raise AnnotationError('Cage command requires "place_model" argument')
    if not hasattr(cage, 'cage_placements'):
        raise AnnotationError('Model %s is not a cage model.' % cage.name)

    n = polygon_sides
    p = cage.cage_placements(n)
    if len(p) == 0:
        raise AnnotationError('Cage %s has no %d-gons.' % (cage.name, n))
    c = place_model.bounds().center()
    pc = make_closest_placement_identity(p, c)

    # TODO: Is positioning right if cage is moved?
    from chimerax.core.atomic import Structure
    if surface_only and isinstance(place_model, Structure):
        from chimerax.core.commands.surface import surface
        surfs = surface(session, place_model.atoms, resolution = resolution)
        mpinv = place_model.scene_position.inverse()
        for s in surfs:
            s.positions = mpinv * pc * s.scene_position
    else:
        place_model.positions = pc * place_model.scene_position

    session.logger.info('Placed %s at %d positions on %d-sided polygons'
                        % (place_model.name, len(pc), n))

# -----------------------------------------------------------------------------
# Find the transform that maps (0,0,0) closest to the molecule center and
# multiply all transforms by the inverse of that transform.  This chooses
# the best placement for the current molecule position and makes all other
# placements relative to that one.
#
def make_closest_placement_identity(tflist, center):

    d = tflist * (0,0,0)
    d -= center
    d2 = (d*d).sum(axis = 1)
    i = d2.argmin()
    tfinv = tflist[i].inverse()

    from chimerax.core.geometry import Place, Places
    rtflist = Places([Place()] + [tf*tfinv for tf in tflist[:i]+tflist[i+1:]])
    return rtflist

def register_cage_command():
    from chimerax.core.commands import CmdDesc, register, ModelArg, IntArg, NoArg, FloatArg
    desc = CmdDesc(required = [('cage', ModelArg)],
                   keyword = [('place_model', ModelArg),
                              ('polygon_sides', IntArg),
                              ('surface_only', NoArg),
                              ('resolution', FloatArg)],
                   synopsis = 'Place copies of model on polygons of cage.')
    register('cage', desc, cage)