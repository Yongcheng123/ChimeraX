# vim: set expandtab ts=4 sw=4:

"""acceptor geometry testing functions"""

from chimerax.core.geometry import look_at, angle, distance_squared
from numpy import linalg
from chimerax.core.atomic.bond_geom import bond_positions
from chimerax.core.atomic.idatm import tetrahedral
from . import hbond
from .common_geom import test_phi, test_theta, sulphur_compensate, get_phi_plane_params
from math import sqrt

@line_profile
def acc_syn_anti(donor, donor_hyds, acceptor, syn_atom, plane_atom, syn_r2, syn_phi,
        syn_theta, anti_r2, anti_phi, anti_theta):
    """'plane_atom' (in conjunction with acceptor, and with 'syn_atom'
        defining the 'up' direction) defines a plane.  If donor is on
        the same side as 'syn_atom', use syn params, otherwise anti params.
    """

    if hbond.verbose:
        print("acc_syn_anti")
    dc = donor.scene_coord
    dp = dc
    ac = acceptor.scene_coord
    ap = ac
    pp = plane_atom.scene_coord
    sp = syn_atom.scene_coord

    syn_xform = look_at(ap, pp, sp - pp)
    xdp = syn_xform * dp

    phi_base_pos = pp
    phi_plane = [ap, pp, sp]

    if xdp[1] > 0.0:
        if hbond.verbose:
            print("Syn")
        if donor.element.name == "S":
            # increase distance cutoff to allow for larger vdw radius of sulphur
            # (which isn't considered as a donor in original paper)
            syn_r2 = sulphur_compensate(syn_r2)
        return test_phi_psi(dp, donor_hyds, ap, phi_base_pos, phi_plane,
                        syn_r2, syn_phi, syn_theta)
    if hbond.verbose:
        print("Anti")
    if donor.element.name == "S":
        # increase distance to compensate for sulphur radius
        anti_r2 = sulphur_compensate(anti_r2)
    return test_phi_psi(dp, donor_hyds, ap, phi_base_pos, phi_plane,
                        anti_r2, anti_phi, anti_theta)

@line_profile
def acc_phi_psi(donor, donor_hyds, acceptor, bonded1, bonded2, r2, phi, theta):
    if hbond.verbose:
        print("acc_phi_psi")

    # when acceptor bonded to one heavy atom
    if not bonded1:
        # water
        bonded = acceptor.neighbors
        if len(bonded) > 0:
            bonded1 = bonded[0]
            if len(bonded) > 1:
                bonded2 = bonded[1]

    phi_plane, phi_base_pos = get_phi_plane_params(acceptor, bonded1, bonded2)
    if donor.element.name == "S":
        r2 = sulphur_compensate(r2)
    return test_phi_psi(donor.scene_coord, donor_hyds,
        acceptor.scene_coord, phi_base_pos, phi_plane, r2, phi, theta)

@line_profile
def test_phi_psi(dp, donor_hyds, ap, bp, phi_plane, r2, phi, theta):
    if hbond.verbose:
        print("distance: %g, cut off: %g" % (linalg.norm(dp-ap), sqrt(r2)))
    if distance_squared(dp, ap) > r2:
        if hbond.verbose:
            print("dist criteria failed")
        return False
    if hbond.verbose:
        print("dist criteria OK")

    if not test_phi(dp, ap, bp, phi_plane, phi):
        return False

    return test_theta(dp, donor_hyds, ap, theta)

@line_profile
def acc_theta_tau(donor, donor_hyds, acceptor, upsilon_partner, r2,
                        upsilon_low, upsilon_high, theta):
    if hbond.verbose:
        print("acc_theta_tau")
    dp = donor.scene_coord
    ap = acceptor.scene_coord

    if donor.element.name == "S":
        r2 = sulphur_compensate(r2)
    if hbond.verbose:
        print("distance: %g, cut off: %g" % (linalg.norm(dp-ap), sqrt(r2)))
    if distance_squared(dp, ap) > r2:
        if hbond.verbose:
            print("dist criteria failed")
        return False
    if hbond.verbose:
        print("dist criteria okay")
    
    if upsilon_partner:
        up_pos = upsilon_partner.scene_coord
    else:
        # upsilon measured from "lone pair" (bisector of attached
        # atoms)
        bonded_pos = []
        for bonded in acceptor.neighbors:
            bonded_pos.append(bonded.scene_coord)
        lonePairs = bond_positions(ap, tetrahedral, 1.0, bonded_pos)
        bisectors = []
        for lp in lonePairs:
            bisectors.append(ap - (lp - ap))
        up_pos = bisectors[0]
        for bs in bisectors[1:]:
            if hbond.verbose:
                print("Testing 'extra' lone pair")
            if test_theta_tau(dp, donor_hyds, ap, bs, upsilon_low, upsilon_high, theta):
                return True
    return test_theta_tau(dp, donor_hyds, ap, up_pos, upsilon_low, upsilon_high, theta)

@line_profile
def test_theta_tau(dp, donor_hyds, ap, pp, upsilon_low, upsilon_high, theta):
    upsilon_high = 0 - upsilon_high
    upsilon = angle(pp, ap, dp)
    if upsilon < upsilon_low or upsilon > upsilon_high:
        if hbond.verbose:
            print("upsilon (%g) failed (%g-%g)" % (upsilon, upsilon_low, upsilon_high))
        return False
    if hbond.verbose:
        print("upsilon okay")
    return test_theta(dp, donor_hyds, ap, theta)

@line_profile
def acc_generic(donor, donor_hyds, acceptor, r2, min_angle):
    if hbond.verbose:
        print("generic acceptor")
    dp = donor.scene_coord
    ap = acceptor.scene_coord
    if donor.element.name == "S":
        r2 = sulphur_compensate(r2)
    if hbond.verbose:
        print("distance: %g, cut off: %g" % (linalg.norm(dp-ap), sqrt(r2)))
    if distance_squared(dp, ap) > r2:
        if hbond.verbose:
            print("dist criteria failed")
        return False
    if hbond.verbose:
        print("dist criteria okay")
     
    ap = acceptor.scene_coord
    dp = donor.scene_coord
    for bonded in acceptor.neighbors:
        bp = bonded.scene_coord
        if hbond.verbose:
            print("angle: %g" % angle(bp, ap, dp))
        ang = angle(bp, ap, dp)
        if ang < min_angle:
            if hbond.verbose:
                print("angle too sharp (%g < %g)" % (ang, min_angle))
            return False
    if hbond.verbose:
        print("angle(s) okay (all > %g)" % min_angle)
    return True