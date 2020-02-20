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

def run(session, text, *, log=True, downgrade_errors=False):
    """execute a textual command

    Parameters
    ----------
    text : string
        The text of the command to execute.
    log : bool
        Print the command text to the reply log.
    downgrade_errors : bool
        True if errors in the command should be logged as informational.
    """

    from chimerax.core.commands import Command
    from chimerax.core.errors import UserError
    command = Command(session)
    try:
        results = command.run(text, log=log)
    except UserError as err:
        if downgrade_errors:
            session.logger.info(str(err))
        else:
            raise
        results = []
    return results[0] if len(results) == 1 else results

def concise_model_spec(session, models, relevant_types=None, allow_empty_spec=True):
    """For commands where the spec will be automatically narrowed down to specific types of models
       (e.g. command uses AtomicStructureArg rather than ModelsArgs), providing the 'relevant_types'
       arg (e.g. relevant_types=AtomicStructure) may allow a more concise spec to be generated.
       The 'models' arg will be pruned down to only those types.  If allow_empty_spec is True
       and all open models are to be specified then the empty string is returned.  If allow_empty_spec
       is False then a non-empty spec will always be returned.
    """
    universe = set(session.models if relevant_types is None else [x for x in session.models
        if isinstance(x, relevant_types)])
    if relevant_types:
        models = [m for m in models if isinstance(m, relevant_types)]
    models = [m for m in models if m.id is not None]
    if not models:
        return '#'
    # algorithm only works (namely _make_id_tree) if ids are longest to shortest...
    universe = sorted(universe, key=lambda m: len(m.id))
    models = sorted(models, key=lambda m: len(m.id))
    u_id_tree = _make_id_tree(universe)
    m_id_tree = _make_id_tree(models)

    if allow_empty_spec and u_id_tree == m_id_tree:
        # for some reason '#' doesn't select all models, so...
        return ""

    full_idents = []
    for ident in m_id_tree.keys():
        u_subtree = u_id_tree[ident]
        m_subtree = m_id_tree[ident]
        full_idents.extend(_traverse_tree([ident], m_subtree, u_subtree))
    # full idents that end in '0' have submodels under them that should be excluded,
    # so handle them separately
    hash_idents = []
    hash_bang_idents = []
    for ident in full_idents:
        if ident[-1] == 0:
            hash_bang_idents.append(ident[:-1])
        else:
            hash_idents.append(ident)
    full_spec = ""
    for prefix, idents in [('#', hash_idents), ('#!', hash_bang_idents)]:
        if not idents:
            continue
        idents.sort(key=lambda x: ((len(x), x)))
        spec = prefix
        ident1 = ident2 = idents[0]
        show_full = True
        for ident in idents[1:]:
            if len(ident) != len(ident1) or ident[:-1] != ident2[:-1]:
                spec += _make_spec(ident1, ident2, show_full) + prefix
                ident1 = ident2 = ident
                show_full = True
            else:
                if ident[-1] == ident2[-1] + 1:
                    ident2 = ident
                else:
                    spec += _make_spec(ident1, ident2, show_full) + ','
                    ident1 = ident2 = ident
                    show_full = False
        spec += _make_spec(ident1, ident2, show_full)
        full_spec += spec
    return full_spec if full_spec else '#'

def sel_or_all(session, sel_type_info, sel="sel", restriction=None):
    # sel_type_info is either a list of strings each of which is appropriate as an arg for
    # session.selection.items(arg), or a Model subclass

    from chimerax.core.errors import UserError
    from chimerax.core.models import Model
    if isinstance(sel_type_info, Model):
        type_models = [m for m in session.models.list(type=sel_type_info)]
        if not type_models:
            raise UserError("No %s models open" % sel_type_info.__name__)
        msel = [m for m in type_models if m.selected]
        if msel:
            if restriction:
                return '(%s & %s)' % (concise_model_spec(msel), restriction)
            return concise_model_spec(msel)
        if session.selection.empty():
            mshown = [m for m in type_models if m.visible]
            if mshown and mshown != type_models:
                if restriction:
                    return '(%s & %s)' % (concise_model_spec(mshown), restriction)
                return concise_model_spec(mshown)
            if restriction:
                return '(%s & %s)' % (concise_model_spec(type_models), restriction)
            return concise_model_spec(type_models)
        raise UserError("No %s models selected" % sel_type_info.__name__)

    # specific types rather than a Model subclass
    for sel_type in sel_type_info:
        if session.selection.items(sel_type):
            if restriction:
                return '(%s & %s)' % (sel, restriction)
            return sel
    if session.selection.empty():
        return ""
    raise UserError("No %s selected" % " or ".join(sel_type_info))

def _make_id_tree(models):
    tree = {}
    for m in models:
        subtree = tree
        for i, ident in enumerate(m.id):
            subtree = subtree.setdefault(ident, { 0: i == len(m.id)-1 })
    return tree

def _traverse_tree(prefix, m_tree, u_tree):
    if m_tree == u_tree:
        return [prefix]
    idents = []
    for ident in m_tree.keys():
        if ident == 0 and not m_tree[ident]:
            continue
        m_subtree = m_tree[ident]
        u_subtree = u_tree[ident]
        if isinstance(m_subtree, bool):
            if m_subtree:
                idents.append(prefix + [ident])
        elif m_subtree == u_subtree:
            idents.append(prefix + [ident])
        else:
            idents.extend(_traverse_tree(prefix +[ident], m_subtree, u_subtree))
    return idents

def _make_spec(ident1, ident2, show_full):
    if show_full:
        full1 = '.'.join([str(x) for x in ident1])
        if ident1 == ident2:
            return full1
        else:
            return "%s-%d" % (full1, ident2[-1])
    if ident1 == ident2:
        return "%d" % ident1[-1]
    return "%d-%d" % (ident1[-1], ident2[-1])
