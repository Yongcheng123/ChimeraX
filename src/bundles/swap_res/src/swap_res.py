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

from chimerax.core.errors import LimitationError, UserError
from chimerax.atomic.rotamers import NoResidueRotamersError, RotamerLibrary, NoRotamerLibraryError, \
    UnsupportedResTypeError

from .cmd import default_criteria
def swap_aa(session, residues, res_type, *, bfactor=None, clash_hbond_allowance=None, clash_score_method="sum",
        clash_threshold=None, criteria=default_criteria, density=None, hbond_angle_slop=None,
        hbond_dist_slop=None, hbond_relax=True, ignore_other_models=False, lib="Dunbrack", log=True,
        preserve=None, retain=False):
    """backend implementation of "swapaa" command."""
    rotamers = {}
    destroy_list = []
    for res in residues:
        if res_type == "same":
            r_type = res.name
        else:
            r_type = res_type.upper()
        if criteria == "manual":
            raise LimitationError("swapaa 'manual' criteria not implemented yet")
            #TODO
            '''
            for library in libraries:
                if library.importName == lib:
                    break
            else:
                raise MidasError("No such rotamer library: %s" % lib)
            from gui import RotamerDialog
            RotamerDialog(res, r_type, library)
            '''
            continue
        try:
            rots = get_rotamers(session, res, res_type=r_type, lib=lib, log=log)
        except UnsupportedResTypeError:
            raise LimitationError("%s rotamer library does not support %s" %(lib, r_type))
        except NoResidueRotamersError:
            if log:
                session.logger.info("Swapping %s to %s\n" % (res, r_type))
            try:
                template_swap_res(res, r_type, bfactor=bfactor)
            except TemplateSwapError as e:
                raise UserError(str(e))
            continue
        except NoRotamerLibraryError:
            raise UserError("No rotamer library named '%s'" % lib)
        if preserve is not None:
            rots = prune_by_chis(session, rots, res, preserve, log=log)
        rotamers[res] = rots
        destroy_list.extend(rots)
    if not rotamers:
        return

    # this implementation allows tie-breaking criteria to be skipped if
    # there are no ties
    if isinstance(criteria, str) and not criteria.isalpha():
        raise UserError("Nth-most-probable criteria cannot be mixed with other criteria")
    #TODO
    cmp = lambda p1,p2: 1 if p1 > p2 else (0 if p1 == p2 else -1)
    for char in str(criteria):
        if char == "d":
            #TODO
            raise LimitationError("'d' criteria not implemented")
            # density
            if density == None:
                if criteria is default_criteria:
                    continue
                raise MidasError("Density criteria requested"
                    " but no density model specified")
            from VolumeViewer.volume import Volume
            if isinstance(density, list):
                density = [d for d in density
                        if isinstance(d, Volume)]
            else:
                density = [density]
            if not density:
                raise MidasError("No volume models in"
                    " specified model numbers")
            if len(density) > 1:
                raise MidasError("Multiple volume models in"
                    " specified model numbers")
            allRots = []
            for res, rots in rotamers.items():
                chimera.openModels.add(rots,
                    sameAs=res.molecule, hidden=True)
                allRots.extend(rots)
            processVolume(allRots, "cmd", density[0])
            chimera.openModels.remove(allRots)
            fetch = lambda r: r.volumeScores["cmd"]
            test = cmp
        elif char == "c":
            #TODO
            raise LimitationError("'c' criteria not implemented")
            # clash
            if clash_hbond_allowance is None or clash_threshold is None:
                from chimerax.atomic.clashes.settings import defaults
                if clash_hbond_allowance is None:
                    clash_hbond_allowance = defaults['clash_hbond_allowance']
                if clash_threshold is None:
                    clash_threshold = defaults['clash_threshold']
            for res, rots in rotamers.items():
                chimera.openModels.add(rots, sameAs=res.molecule, hidden=True)
                processClashes(res, rots, clash_threshold,
                    clash_hbond_allowance, clash_score_method, False,
                    None, None, ignore_other_models)
                chimera.openModels.remove(rots)
            fetch = lambda r: r.clashScore
            test = cmp
        elif char == 'h':
            #TODO
            raise LimitationError("'h' criteria not implemented")
            # H bonds
            if hbond_angle_slop is None or hbond_dist_slop is None:
                from chimerax.atomic.hbonds import rec_angle_slop, rec_dist_slop
                if hbond_angle_slop is None:
                    hbond_angle_slop = rec_angle_slop
                if hbond_dist_slop is None:
                    hbond_dist_slop = rec_dist_slop
            for res, rots in rotamers.items():
                chimera.openModels.add(rots, sameAs=res.molecule, hidden=True)
                processHbonds(res, rots, False, None, None,
                    relax, hbond_dist_slop, hbond_angle_slop, False,
                    None, None, ignore_other_models,
                    cacheDA=True)
                chimera.openModels.remove(rots)
            from chimerax.atomic.hbonds import flush_cache
            flush_cache()
            fetch = lambda r: r.numHbonds
            test = cmp
        elif char == 'p':
            # most probable
            fetch = lambda r: r.rotamer_prob
            test = cmp
        elif isinstance(criteria, int):
            #TODO
            raise LimitationError("Nth-prob criteria not implemented")
            # Nth most probable
            index = criteria - 1
            for res, rots in rotamers.items():
                if index >= len(rots):
                    if log:
                        replyobj.status("Residue %s does not have %d %s"
                            " rotamers; skipping" % (res, criteria, r_type),
                            log=True, color="red")
                    continue
                rotamers[res] = [rots[index]]
            fetch = lambda r: 1
            test = lambda v1, v2: 1

        for res, rots in list(rotamers.items()):
            best = None
            for rot in rots:
                val = fetch(rot)
                if best == None or test(val, best_val) > 0:
                    best = [rot]
                    best_val = val
                elif test(val, best_val) == 0:
                    best.append(rot)
            if len(best) > 1:
                rotamers[res] = best
            else:
                use_rotamer(session, res, [best[0]], retain=retain, log=log)
                del rotamers[res]
        if not rotamers:
            break
    for res, rots in rotamers.items():
        if log:
            session.logger.info("%s has %d equal-value rotamers;"
                " choosing one arbitrarily.\n" % (res, len(rots)))
        use_rotamer(session, res, [rots[0]], retain=retain, log=log)
    for rot in destroy_list:
        rot.delete()

def get_rotamers(session, res, phi=None, psi=None, cis=False, res_type=None, lib="Dunbrack", log=False):
    """Takes a Residue instance and optionally phi/psi angles (if different from the Residue), residue
       type (e.g. "TYR"), and/or rotamer library name.  Returns a list of AtomicStructure instances.
       The AtomicStructures are each a single residue (a rotamer) and are in descending probability order.
       Each has an attribute "rotamer_prob" for the probability and "chis" for the chi angles.
    """
    res_type = res_type or res.name
    if res_type == "ALA" or res_type == "GLY":
        raise NoResidueRotamersError("No rotamers for %s" % res_type)

    if not isinstance(lib, RotamerLibrary):
        lib = session.rotamers.library(lib)

    # check that the residue has the n/c/ca atoms needed to position the rotamer
    # and to ensure that it is an amino acid
    from chimerax.atomic import Residue, AtomicStructure
    match_atoms = {}
    for bb_name in Residue.aa_min_backbone_names:
        match_atoms[bb_name] = a = res.find_atom(bb_name)
        if a is None:
            raise LimitationError("%s missing from %s; needed to position CB" % (bb_name, res))
    match_atoms["CB"] = res.find_atom("CB")
    if not phi and not psi:
        phi, psi = res.phi, res.psi
        omega = res.omega
        cis = False if omega is None or abs(omega) > 90 else True
        if log:
            def _info(ang):
                if ang is None:
                    return "none"
                return "%.1f" % ang
            session.logger.info("%s: phi %s, psi %s %s" % (res, _info(phi), _info(psi),
                "cis" if cis else "trans"))
    session.logger.status("Retrieving rotamers from %s library" % lib.display_name)
    res_template_func = lib.res_template_func
    params = lib.rotamer_params(res_type, phi, psi, cis=cis)
    session.logger.status("Rotamers retrieved from %s library" % lib.display_name)

    mapped_res_type = lib.res_name_mapping.get(res_type, res_type)
    template = lib.res_template_func(mapped_res_type)
    tmpl_N = template.find_atom("N")
    tmpl_CA = template.find_atom("CA")
    tmpl_C = template.find_atom("C")
    tmpl_CB = template.find_atom("CB")
    if tmpl_CB:
        res_match_atoms, tmpl_match_atoms = [match_atoms[x]
            for x in ("C", "CA", "CB")], [tmpl_C, tmpl_CA, tmpl_CB]
    else:
        res_match_atoms, tmpl_match_atoms = [match_atoms[x]
            for x in ("N", "CA", "C")], [tmpl_N, tmpl_CA, tmpl_C]
    from chimerax.core.geometry import align_points
    from numpy import array
    xform, rmsd = align_points(array([fa.coord for fa in tmpl_match_atoms]),
        array([ta.scene_coord for ta in res_match_atoms]))
    n_coord = xform * tmpl_N.coord
    ca_coord = xform * tmpl_CA.coord
    cb_coord = xform * tmpl_CB.coord
    info = Residue.chi_info[mapped_res_type]
    bond_cache = {}
    angle_cache = {}
    from chimerax.atomic.struct_edit import add_atom, add_dihedral_atom, add_bond
    structs = []
    middles = {}
    ends = {}
    for i, rp in enumerate(params):
        s = AtomicStructure(session, name="rotamer %d of %s" % (i+1, res))
        structs.append(s)
        r = s.new_residue(mapped_res_type, 'A', 1)
        s.rotamer_prob = rp.p
        s.chis = rp.chis
        rot_N = add_atom("N", tmpl_N.element, r, n_coord)
        rot_CA = add_atom("CA", tmpl_CA.element, r, ca_coord, bonded_to=rot_N)
        rot_CB = add_atom("CB", tmpl_CB.element, r, cb_coord, bonded_to=rot_CA)
        todo = []
        for j, chi in enumerate(rp.chis):
            n3, n2, n1, new = info[j]
            b_len, angle = _len_angle(new, n1, n2, template, bond_cache, angle_cache)
            n3 = r.find_atom(n3)
            n2 = r.find_atom(n2)
            n1 = r.find_atom(n1)
            new = template.find_atom(new)
            a = add_dihedral_atom(new.name, new.element, n1, n2, n3, b_len, angle, chi, bonded=True)
            todo.append(a)
            middles[n1] = [a, n1, n2]
            ends[a] = [a, n1, n2]

        # if there are any heavy non-backbone atoms bonded to template
        # N and they haven't been added by the above (which is the
        # case for Richardson proline parameters) place them now
        for tnnb in tmpl_N.neighbors:
            if r.find_atom(tnnb.name) or tnnb.element.number == 1:
                continue
            tnnb_coord = xform * tnnb.coord
            add_atom(tnnb.name, tnnb.element, r, tnnb_coord, bonded_to=rot_N)

        # fill out bonds and remaining heavy atoms
        from chimerax.core.geometry import distance
        done = set([rot_N, rot_CA])
        while todo:
            a = todo.pop(0)
            if a in done:
                continue
            tmpl_A = template.find_atom(a.name)
            for bonded, bond in zip(tmpl_A.neighbors, tmpl_A.bonds):
                if bonded.element.number == 1:
                    continue
                rbonded = r.find_atom(bonded.name)
                if rbonded is None:
                    # use middles if possible...
                    try:
                        p1, p2, p3 = middles[a]
                        conn = p3
                    except KeyError:
                        p1, p2, p3 = ends[a]
                        conn = p2
                    t1 = template.find_atom(p1.name)
                    t2 = template.find_atom(p2.name)
                    t3 = template.find_atom(p3.name)
                    _ignore1, _ignore2, rmsd, _ignore3, xform = align([t1,t2,t3], to_atoms=[p1,p2,p3])
                    pos = xform * template.find_atom(bonded.name).coord
                    rbonded = add_atom(bonded.name, bonded.element, r, pos, bonded_to=a)
                    middles[a] = [rbonded, a, conn]
                    ends[rbonded] = [rbonded, a, conn]
                if a not in rbonded.neighbors:
                    add_bond(a, rbonded)
                if rbonded not in done:
                    todo.append(rbonded)
            done.add(a)
    return structs

def template_swap_res(res, res_type, *, preserve=False, bfactor=None):
    """change 'res' into type 'res_type'"""

    fixed, buds, start, end = get_res_info(res)

    if res_type == "HIS":
        res_type = "HIP"
    if res_type in ["A", "C", "G", "T"] and res.name in ["DA", "DC", "DT", "DG"]:
        res_type = "D" + res_type
    from chimerax.atomic import TmplResidue, Atom
    tmpl_res = TmplResidue.get_template(res_type, start=start, end=end)
    if not tmpl_res:
        raise TemplateError("No connectivity template for residue '%s'" % res_type)
    # sanity check:  does the template have the bud atoms?
    for bud in buds:
        if tmpl_res.find_atom(bud) is None:
            raise TemplateError("New residue type (%s) not compatible with"
                " starting residue type (%s)" % (res_type, res.name))

    # if bfactor not specified, find highest bfactor in residue and use that for swapped-in atoms
    if bfactor is None:
        import numpy
        bfactor = numpy.max(res.atoms.bfactors)

    if preserve:
        if "CA" in fixed and res_type not in ['GLY', 'ALA']:
            raise TemplateSwapError("'preserve' keyword not yet implemented for amino acids")
        a1 = res.find_atom("O4'")
        a2 = res.find_atom("C1'")
        if not a1 or not a2:
            preserve_pos = None
        else:
            dihed_names = {
                "N9": ["C4", "C8"],
                "N1": ["C2", "C6"]
            }
            a3 = res.find_atom("N9") or res.find_atom("N1")
            if a3:
                if a2 not in a3.neighbors:
                    preserve_pos = None
                else:
                    preserve_pos = a3.coord
            else:
                preserve_pos = None
        if preserve_pos:
            p1, p2, p3 = [a.coord for a in (a1, a2, a3)]
            preserved_pos = False
            prev_name, alt_name = dihed_names[a3.name]
            a4 = res.find_atom(prev_name)
            if a4 and a3 in a4.neighbors:
                p4 = a4.coord
                from chimerax.core.geometry import dihedral
                preserve_dihed = dihedral(p1, p2, p3, p4)
            else:
                preserve_dihed = None
        else:
            preserve_dihed = None

    # prune non-backbone atoms
    for a in res.atoms:
        if a.name not in fixed:
            a.structure.delete_atom(a)

    # add new sidechain
    new_atoms = []
    xf = None
    from chimerax.atomic.struct_edit import add_bond
    while len(buds) > 0:
        bud = buds.pop()
        tmpl_bud = tmpl_res.find_atom(bud)
        res_bud = res.find_atom(bud)

        try:
            info = Atom.idatm_info_map[tmpl_bud.idatm_type]
            geom = info.geometry
            subs = info.substituents
        except KeyError:
            raise AssertionError("Can't determine atom type information for atom %s of residue %s" % (bud, res))

        # use .coord rather than .scene_coord:  we want to set # the new atom's coord,
        # to which the proper xform will then be applied
        for a, b in zip(tmpl_bud.neighbors, tmpl_bud.bonds):
            if a.element.number == 1:
                # don't add hydrogens
                continue
            if res.find_atom(a.name):
                res_bonder = res.find_atom(a.name)
                if res_bonder not in res_bud.neighbors:
                    add_bond(a, res_bonder)
                continue

            new_atom = None
            num_bonded = len(res_bud.bonds)
            if num_bonded >= subs:
                raise AssertionError("Too many atoms bonded to %s of residue %s" % (bud, res))
            if num_bonded == 0:
                raise AssertionError("Atom %s of residue %s has no neighbors after pruning?!?" % (bud, res))
            # since fused ring systems may have distorted bond angles, always use dihedral placement
            real1 = res_bud.neighbors[0]
            kw = {}
            if preserve:
                if preserve_pos and not preserved_pos:
                    kw['pos'] = preserve_pos
                    preserved_pos = True
                    preserved_name = a.name
                elif preserve_dihed is not None:
                    prev_name, alt_name = dihed_names[preserved_name]
                    if a.name == prev_name:
                        kw['dihed'] = preserve_dihed
                    elif a.name == alt_name:
                        kw['dihed'] = preserve_dihed + 180.0
            if not kw and xf is not None:
                kw['pos'] = xf * a.coord

            new_atom = form_dihedral(res_bud, real1, tmpl_res, a, b, **kw)
            new_atom.draw_mode = res_bud.draw_mode
            new_atom.bfactor = bfactor
            new_atoms.append(new_atom)

            # TODO: need to iterate over CoordSets
            for bonded in a.neighbors:
                bond_atom = res.find_atom(bonded.name)
                if not bond_atom:
                    continue
                add_bond(new_atom, bond_atom)
            buds.append(new_atom.name)

        # once we've placed 3 side chain atoms, we use superpositioning to
        # place the remainder of the side chain, since dihedrals will
        # likely distort ring closures if 'preserve' is true
        if buds and not xf and len(new_atoms) >= 3:
            placed_positions = []
            tmpl_positions = []
            for na in new_atoms:
                placed_positions.append(na.coord)
                tmpl_positions.append(tmpl_res.find_atom(na.name).coord)
            import numpy
            from chimerax.core.geometry import align_points
            xf = align_points(numpy.array(tmpl_positions),
                numpy.array(placed_positions))[0]

    res.name = res_type

class TemplateSwapError(ValueError):
    pass
class BackboneError(TemplateSwapError):
    pass
class TemplateError(TemplateSwapError):
    pass

amino_info = (("N", "CA", "C", "O", "OXT"), ("CA", "C", ("O", "OXT")))
nucleic_info = (("O1P", "OP1", "O2P", "OP2", "O3P", "OP3", "P", "O5'", "C5'",
    "C4'", "C3'", "O3'", "C2'", "O2'", "C1'", "O4'"), ("C1'", "O4'", "C4'"))
def get_res_info(res):
    """return a list of the fixed atoms of the residue, a list of the fixed atoms that non-fixed atoms
    attach to, and whether this residue is the start and/or end of a chain"""

    errmsg =  "Cannot identify backbone of residue %s)" % res
    backbone = []
    if res.find_atom("N"):
        # putative amino acid
        basic_info = amino_info
        start = len([nb for nb in res.find_atom("N").neighbors if nb.element.number > 1]) != 2
        end = res.find_atom("OXT") is not None
    elif res.find_atom("O3'"):
        # putative nucleic acid
        basic_info = nucleic_info
        start = res.find_atom("P") is not None
        end = len([nb for nb in res.find_atom("O3'").neighbors if nb.element.name == "P"]) == 0
        if end and res.find_atom("O2'") is not None:
            end = len([nb for nb in res.find_atom("O2'").neighbors if nb.element.name == "P"]) == 0
    else:
        raise BackboneError(errmsg)
    fixed, bud = basic_info

    # must have the bud atoms present, (and resolve O/OXT ambiguity)
    final_bud = []
    for at_name in bud:
        if isinstance(at_name, tuple):
            for ambig in at_name:
                if res.find_atom(ambig) is not None:
                    final_bud.append(ambig)
                    break
            else:
                raise BackboneError(errmsg)
            continue
        if res.find_atom(at_name) is not None:
            final_bud.append(at_name)
        else:
            raise BackboneError(errmsg)
    return (list(fixed), final_bud, start, end)

def form_dihedral(res_bud, real1, tmpl_res, a, b, pos=None, dihed=None):
    from chimerax.atomic.struct_edit import add_atom, add_dihedral_atom
    res = res_bud.residue
    if pos:
        return add_atom(a.name, a.element, res, pos, info_from=real1)
    # use neighbors of res_bud rather than real1 to avoid clashes with
    # other res_bud neighbors in case bond to real1 neighbor freely rotates
    inres = [nb for nb in res_bud.neighbors if nb != real1 and nb.residue == res]
    if len(inres) < 1:
        inres = [x for x in res.atoms if x not in [res_bud, real1]]
    if real1.residue != res or len(inres) < 1:
        raise AssertionError("Can't form in-residue dihedral for %s of residue %s" % (res_bud, res))
    if dihed:
        real1 = res.find_atom("C1'")
        real2 = res.find_atom("O4'")
    else:
        real2 = inres[0]
    xyz0, xyz1, xyz2 = [tmpl_res.find_atom(a.name).coord for a in (res_bud, real1, real2)]

    xyz = a.coord
    blen = b.length
    from chimerax.core.geometry import angle, dihedral
    ang = angle(xyz, xyz0, xyz1)
    if dihed is None:
        dihed = dihedral(xyz, xyz0, xyz1, xyz2)
    return add_dihedral_atom(a.name, a.element, res_bud, real1, real2, blen, ang, dihed, info_from=real1)

def prune_by_chis(session, rots, res, cutoff, log=False):
    if res.chi1 is None:
        return rots
    pruned = rots[:]
    for chi_num in range(4):
        next_pruned = []
        nearest = None
        target_chi = res.get_chi(chi_num, True)
        if target_chi is None:
            break
        for rot in pruned:
            rot_chi = rot.get_chi(chi_num, True)
            delta = abs(rot_chi - target_chi)
            if delta <= cutoff:
                next_pruned.append(rot)
            if nearest is None or near_delta > delta:
                nearest = rot
                near_delta = delta
        if next_pruned:
            pruned = next_pruned
        else:
            break
    if pruned:
        if log:
            session.info("Filtering rotamers with chi angles within %g of %s yields %d (of original %d)"
                % (cutoff, res, len(pruned), len(rots)))
        return pruned
    if log:
        session.info("No rotamer with all chi angles within %g of %s; using closest one" % (cutoff, res))
    return [nearest]

def side_chain_locs(residue):
    locs = set()
    for a in residue.atoms:
        if a.is_backbone():
            continue
        locs.add(a.alt_loc)
    return locs

def use_rotamer(session, res, rots, retain=False, log=False):
    """Takes a Residue instance and a list of one or more rotamers (as returned by get_rotamers,
       i.e. with backbone already matched) and swaps the Residue's side chain with the given rotamers.
       If more than one rotamer is in the list, then alt locs will be used to distinguish the different
       side chains.  The side chain(s) will be positioned using the current backbone altloc.

       If 'retain' is True, existing side chains will be retained.
    """
    N = res.find_atom("N")
    CA = res.find_atom("CA")
    C = res.find_atom("C")
    if not N or not C or not CA:
        raise LimitationError("N, CA, or C missing from %s: needed for side-chain pruning algorithm" % res)
    import string
    alt_locs = string.ascii_uppercase + string.ascii_lowercase + string.digits + string.punctuation
    if retain and res.name != rots[0].name:
        raise LimitationError("Cannot retain side chains if rotamers are a different residue type")
    retained_alt_locs = side_chain_locs(res) if retain else []
    num_retained = len(retained_alt_locs)
    if len(rots) + num_retained > len(alt_locs):
        raise LimitationError("Don't have enough unique alternate "
            "location characters to place %d rotamers." % len(rots))
    rot_anchors = {}
    for rot in rots:
        rot_res = rot.residues[0]
        rot_N, rot_CA = rot_res.find_atom("N"), rot_res.find_atom("CA")
        if not rot_N or not rot_CA:
            raise LimitationError("N or CA missing from rotamer: cannot matchup with original residue")
        rot_anchors[rot] = (rot_N, rot_CA)
    color_by_element = N.color != CA.color
    if color_by_element:
        carbon_color = CA.color
    else:
        uniform_color = N.color
    multi_sidechain = (len(rots) + num_retained) > 1
    # Don't know what to do if multiple rotamers being added to multi-position backbone, so check for that
    if multi_sidechain and CA.alt_loc != ' ':
        raise LimitationError("Cannot add multiple rotamers to multi-position backbone")
    # prune old side chain
    if not retain:
        res_atoms = res.atoms
        side_atoms = res_atoms.filter(res_atoms.is_side_onlys)
        serials = { a.name:a.serial_number for a in side_atoms }
        side_atoms.delete()
    else:
        serials = {}
    # for proline, also prune amide hydrogens
    if rots[0].residues[0].name == "PRO":
        for nnb in N.neighbors[:]:
            if nnb.element.number == 1:
                N.structure.delete_atom(nnb)

    tot_prob = sum([r.rotamer_prob for r in rots])
    orig_CA_alt_loc = CA.alt_loc
    res.structure.alt_loc_change_notify = False
    res.name = rots[0].residues[0].name
    from chimerax.atomic.struct_edit import add_atom, add_bond
    ca_alt_locs = [' '] if orig_CA_alt_loc == ' ' else CA.alt_locs
    for ca_alt_loc in ca_alt_locs:
        CA.alt_loc = ca_alt_loc
        if multi_sidechain:
            locs_rots = zip([c for c in alt_locs if c not in retained_alt_locs][:len(rots)], rots)
        else:
            locs_rots = [(ca_alt_loc, rots[0])]
        for alt_loc, rot in locs_rots:
            if log:
                extra = " using alt loc %s" % alt_loc if alt_loc != ' ' else ""
                session.logger.info("Applying %s rotamer (chi angles: %s) to %s%s"
                    % (rot_res.name, " ".join(["%.1f" % c for c in rot.chis]), res, extra))
            # add new side chain
            rot_N, rot_CA = rot_anchors[rot]
            visited = set([N, CA, C])
            sprouts = [rot_CA]
            while sprouts:
                sprout = sprouts.pop()
                built_sprout = res.find_atom(sprout.name)
                for nb in sprout.neighbors:
                    built_nb = res.find_atom(nb.name)
                    if tot_prob == 0.0:
                        # some rotamers in Dunbrack are zero prob!
                        occupancy = 1.0 / len(rots)
                    else:
                        occupancy = rot.rotamer_prob / tot_prob
                    if not built_nb:
                        serial = serials.get(nb.name, None)
                        built_nb = add_atom(nb.name, nb.element, res, nb.coord, occupancy=occupancy,
                            serial_number=serial, bonded_to=built_sprout, alt_loc=alt_loc)
                        if color_by_element:
                            if built_nb.element.name == "C":
                                built_nb.color = carbon_color
                            else:
                                from chimerax.atomic.colors import element_color
                                built_nb.color = element_color(built_nb.element.number)
                        else:
                            built_nb.color = uniform_color
                    elif built_nb not in visited:
                        built_nb.set_alt_loc(alt_loc, True)
                        built_nb.coord = nb.coord
                        built_nb.occupancy = occupancy
                    if built_nb not in visited:
                        sprouts.append(nb)
                        visited.add(built_nb)
                    if built_nb not in built_sprout.neighbors:
                        add_bond(built_sprout, built_nb)
    CA.alt_loc = orig_CA_alt_loc
    res.structure.alt_loc_change_notify = True

def _len_angle(new, n1, n2, template, bond_cache, angle_cache):
    from chimerax.core.geometry import distance, angle
    bond_key = (n1, new)
    angle_key = (n2, n1, new)
    try:
        bl = bond_cache[bond_key]
        ang = angle_cache[angle_key]
    except KeyError:
        n2pos = template.find_atom(n2).coord
        n1pos = template.find_atom(n1).coord
        newpos = template.find_atom(new).coord
        bond_cache[bond_key] = bl = distance(newpos, n1pos)
        angle_cache[angle_key] = ang = angle(newpos, n1pos, n2pos)
    return bl, ang

'''

class NoResidueRotamersError(ValueError):
    pass

class UnsupportedResTypeError(NoResidueRotamersError):
    pass

def _chimeraResTmpl(rt):
    return chimera.restmplFindResidue(rt, False, False)

class RotamerParams:
    """ 'p' attribute is probability of this rotamer;
        'chis' is list of chi angles
    """
    def __init__(self, p, chis):
        self.p = p
        self.chis = chis


        
amino20 = ["ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL"]
class RotamerLibraryInfo:
    """holds information about a rotamer library:
       how to import it, what citation to display, etc.
    """
    def __init__(self, importName):
        self.importName = importName
        exec "import %s as RotLib" % importName
        self.displayName = getattr(RotLib, "displayName", importName)
        self.description = getattr(RotLib, "description", None)
        self.citation = getattr(RotLib, "citation", None)
        self.citeName = getattr(RotLib, "citeName", None)
        self.citePubmedID = getattr(RotLib, "citePubmedID", None)
        self.residueTypes = getattr(RotLib, "residueTypes", amino20)
        self.resTypeMapping = getattr(RotLib, "resTypeMapping", {})

libraries = []
def registerLibrary(importName):
    """Takes a string indicated the "import name" of a library
       (i.e. what name to use in an import statement) and adds a  
       RotamerLibraryInfo instance for it to the list of known
       rotamer libraries ("Rotamers.libraries").
    """
    libraries.append(RotamerLibraryInfo(importName))
registerLibrary("Dunbrack")
registerLibrary("Richardson.mode")
registerLibrary("Richardson.common")
registerLibrary("Dynameomics")

backboneNames = set(['CA', 'C', 'N', 'O'])

def processClashes(residue, rotamers, overlap, hbondAllow, scoreMethod,
                makePBs, pbColor, pbWidth, ignoreOthers):
    testAtoms = []
    for rot in rotamers:
        testAtoms.extend(rot.atoms)
    from DetectClash import detectClash
    clashInfo = detectClash(testAtoms, clashThreshold=overlap,
                interSubmodel=True, hbondAllowance=hbondAllow)
    if makePBs:
        from chimera.misc import getPseudoBondGroup
        from DetectClash import groupName
        pbg = getPseudoBondGroup(groupName)
        pbg.deleteAll()
        pbg.lineWidth = pbWidth
        pbg.color = pbColor
    else:
        import DetectClash
        DetectClash.nukeGroup()
    resAtoms = set(residue.atoms)
    for rot in rotamers:
        score = 0
        for ra in rot.atoms:
            if ra.name in ("CA", "N", "CB"):
                # any clashes of CA/N/CB are already clashes of
                # base residue (and may mistakenly be thought
                # to clash with "bonded" atoms in nearby
                # residues
                continue
            if ra not in clashInfo:
                continue
            for ca, clash in clashInfo[ra].items():
                if ca in resAtoms:
                    continue
                if ignoreOthers \
                and ca.molecule.id != residue.molecule.id:
                    continue
                if scoreMethod == "num":
                    score += 1
                else:
                    score += clash
                if makePBs:
                    pbg.newPseudoBond(ra, ca)
        rot.clashScore = score
    if scoreMethod == "num":
        return "%2d"
    return "%4.2f"

def processHbonds(residue, rotamers, drawHbonds, bondColor, lineWidth, relax,
            distSlop, angleSlop, twoColors, relaxColor, groupName,
            ignoreOtherModels, cacheDA=False):
    from FindHBond import findHBonds
    if ignoreOtherModels:
        targetModels = [residue.molecule] + rotamers
    else:
        targetModels = chimera.openModels.list(
                modelTypes=[chimera.Molecule]) + rotamers
    if relax and twoColors:
        color = relaxColor
    else:
        color = bondColor
    hbonds = dict.fromkeys(findHBonds(targetModels, intramodel=False,
        distSlop=distSlop, angleSlop=angleSlop, cacheDA=True), color)
    if relax and twoColors:
        hbonds.update(dict.fromkeys(findHBonds(targetModels,
                    intramodel=False), bondColor))
    backboneNames = set(['CA', 'C', 'N', 'O'])
    # invalid H-bonds:  involving residue side chain or rotamer backbone
    invalidAtoms = set([ra for ra in residue.atoms
                    if ra.name not in backboneNames])
    invalidAtoms.update([ra for rot in rotamers for ra in rot.atoms
                    if ra.name in backboneNames])
    rotAtoms = set([ra for rot in rotamers for ra in rot.atoms
                    if ra not in invalidAtoms])
    for rot in rotamers:
        rot.numHbonds = 0

    if drawHbonds:
        from chimera.misc import getPseudoBondGroup
        pbg = getPseudoBondGroup(groupName)
        pbg.deleteAll()
        pbg.lineWidth = lineWidth
    elif groupName:
        nukeGroup(groupName)
    for hb, color in hbonds.items():
        d, a = hb
        if (d in rotAtoms) == (a in rotAtoms):
            # only want rotamer to non-rotamer
            continue
        if d in invalidAtoms or a in invalidAtoms:
            continue
        if d in rotAtoms:
            rot = d.molecule
        else:
            rot = a.molecule
        rot.numHbonds += 1
        if drawHbonds:
            pb = pbg.newPseudoBond(d, a)
            pb.color = color

def processVolume(rotamers, columnName, volume):
    import AtomDensity
    sums = []
    for rot in rotamers:
        AtomDensity.set_atom_volume_values(rot, volume, "_vscore")
        scoreSum = 0
        for a in rot.atoms:
            if a.name not in backboneNames:
                scoreSum += a._vscore
            delattr(a, "_vscore")
        if not hasattr(rot, "volumeScores"):
            rot.volumeScores = {}
        rot.volumeScores[columnName] = scoreSum
        sums.append(scoreSum)
    minSum = min(sums)
    maxSum = max(sums)
    absMax = max(maxSum, abs(minSum))
    if absMax >= 100 or absMax == 0:
        return "%d"
    addMinusSign = len(str(int(minSum))) > len(str(int(absMax)))
    if absMax >= 10:
        return "%%%d.1f" % (addMinusSign + 4)
    precision = 2
    while absMax < 1:
        precision += 1
        absMax *= 10
    return "%%%d.%df" % (precision+2+addMinusSign, precision)

def nukeGroup(groupName):
    mgr = chimera.PseudoBondMgr.mgr()
    group = mgr.findPseudoBondGroup(groupName)
    if group:
        chimera.openModels.close([group])

from math import pi, cos, sin
import chimera
from chimera import angle, dihedral, cross, Coord
from chimera.molEdit import addAtom, addDihedralAtom, addBond
from chimera.idatm import tetrahedral, planar, linear, single, typeInfo
from chimera.bondGeom import bondPositions
from chimera.match import matchPositions
'''
