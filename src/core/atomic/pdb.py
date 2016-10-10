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
pdb: PDB format support
=======================

Read Protein DataBank (PDB) files.
"""

def open_pdb(session, filename, name, *args, **kw):

    if hasattr(filename, 'read'):
        # it's really a fetched stream
        input = filename
        path = filename.name if hasattr(filename, 'name') else None
    else:
        input = open(filename, 'rb')
        path = filename

    explode = kw.get('explode', True)
    from . import pdbio
    pointers = pdbio.read_pdb_file(input, log=session.logger, explode=explode)
    if input != filename:
        input.close()

    smid = kw.get('smart_initial_display', True)
    
    from .structure import AtomicStructure
    models = [AtomicStructure(session, name = name, c_pointer = p, smart_initial_display = smid) for p in pointers]

    if path:
        for m in models:
            m.filename = path

    return models, ("Opened PDB data containing %d atoms and %d bonds"
                    % (sum(m.num_atoms for m in models),
                       sum(m.num_bonds for m in models)))


def fetch_pdb(session, pdb_id, ignore_cache=False, **kw):
    if len(pdb_id) != 4:
        from ..errors import UserError
        raise UserError('PDB identifiers are 4 characters long, got "%s"' % pdb_id)
    import os
    # check on local system -- TODO: configure location
    lower = pdb_id.lower()
    subdir = lower[1:3]
    sys_filename = "/databases/mol/pdb/%s/pdb%s.ent" % (subdir, lower)
    if os.path.exists(sys_filename):
        return sys_filename, pdb_id

    pdb_name = "%s.pdb" % pdb_id.upper()
    url = "http://www.pdb.org/pdb/files/%s" % pdb_name
    from ..fetch import fetch_file
    filename = fetch_file(session, url, 'PDB %s' % pdb_id, pdb_name, 'PDB',
                          ignore_cache=ignore_cache)

    from .. import io
    models, status = io.open_data(session, filename, format = 'pdb', name = pdb_id, **kw)
    return models, status

def register_pdb_format():
    from .. import io
    from . import structure
    io.register_format(
        "PDB", structure.CATEGORY, (".pdb", ".pdb1", ".ent", ".pqr"), ("pdb",),
        mime=("chemical/x-pdb", "chemical/x-spdbv"),
        reference="http://wwpdb.org/docs.html#format",
        open_func=open_pdb)

def register_pdb_fetch(session):
    from .. import fetch
    fetch.register_fetch(session, 'pdb', fetch_pdb, 'pdb', prefixes = [])

def process_chem_name(name, use_greek=True, probable_abbrs=False):
    text = ""
    word = ""
    for c in name.strip().lower():
        if c.isalpha():
            word += c
            continue
        if word:
            if c.isdigit() or (text and text[-1].isdigit()):
                text += _process_chem_word(word, use_greek, probable_abbrs).upper()
            else:
                text += _process_chem_word(word, use_greek, probable_abbrs)
            word = ""
        text += c
    if word:
        if c.isdigit() or (text and text[-1].isdigit()):
            text += _process_chem_word(word, use_greek, probable_abbrs).upper()
        else:
            text += _process_chem_word(word, use_greek, probable_abbrs)
    return text

greek_letters = {
    'alpha': u'\N{GREEK SMALL LETTER ALPHA}',
    'beta': u'\N{GREEK SMALL LETTER BETA}',
    'gamma': u'\N{GREEK SMALL LETTER GAMMA}',
    'delta': u'\N{GREEK SMALL LETTER DELTA}',
    'epsilon': u'\N{GREEK SMALL LETTER EPSILON}',
    'zeta': u'\N{GREEK SMALL LETTER ZETA}',
    'eta': u'\N{GREEK SMALL LETTER ETA}',
    'theta': u'\N{GREEK SMALL LETTER THETA}',
    'iota': u'\N{GREEK SMALL LETTER IOTA}',
    'kappa': u'\N{GREEK SMALL LETTER KAPPA}',
    'lambda': u'\N{GREEK SMALL LETTER LAMDA}',
    'lamda': u'\N{GREEK SMALL LETTER LAMDA}',
    'mu': u'\N{GREEK SMALL LETTER MU}',
    'nu': u'\N{GREEK SMALL LETTER NU}',
    'xi': u'\N{GREEK SMALL LETTER XI}',
    'omicron': u'\N{GREEK SMALL LETTER OMICRON}',
    'pi': u'\N{GREEK SMALL LETTER PI}',
    'rho': u'\N{GREEK SMALL LETTER RHO}',
    'sigma': u'\N{GREEK SMALL LETTER SIGMA}',
    'tau': u'\N{GREEK SMALL LETTER TAU}',
    'upsilon': u'\N{GREEK SMALL LETTER UPSILON}',
    'phi': u'\N{GREEK SMALL LETTER PHI}',
    'chi': u'\N{GREEK SMALL LETTER CHI}',
    'psi': u'\N{GREEK SMALL LETTER PSI}',
    'omega': u'\N{GREEK SMALL LETTER OMEGA}',
}
def _process_chem_word(word, use_greek, probable_abbrs):
    if len(word) == 1:
        return word.upper()
    from . import Element
    if len(word) == 2 and word.capitalize() in Element.names:
        return word.capitalize()
    if set(list(word)) <= set(["i", "v", "x"]):
        # Roman numeral
        return word.upper()
    if use_greek and word in greek_letters:
        return greek_letters[word]
    if probable_abbrs and len(word) < 5 and word != "cell":
        return word.upper()
    segs = []
    for seg in word.split('-'):
        if seg.startswith("rna") or seg.startswith("dna"):
            segs.append(seg[:3].upper() + seg[3:])
        elif seg.endswith("rna") or seg.endswith("dna"):
            segs.append(seg[:-3] + seg[-3:].upper())
        else:
            segs.append(word)
    return '-'.join(segs)
