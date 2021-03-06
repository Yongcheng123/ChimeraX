# vim: set expandtab ts=4 sw=4:

from chimerax.core.errors import UserError
from chimerax.core.commands import CmdDesc, StringArg, AtomSpecArg, ObjectsArg
from chimerax.core.commands import RestOfLine, NoArg, AnnotationError


def name(session, name, text=None):
    if name == "all":
        raise UserError("\"all\" is reserved and cannot be redefined")
    if text is None:
        from chimerax.core.commands import get_selector
        try:
            sel = get_selector(name)
        except KeyError:
            raise UserError("\"%s\" is not defined" % name)
        else:
            value = _get_name_desc(sel, True)
            session.logger.info('\t'.join([name, value]))
    else:
        try:
            ast, used, unused = AtomSpecArg.parse(text, session)
            if unused:
                raise AnnotationError("contains extra trailing text")
        except AnnotationError as e:
            raise UserError("\"%s\": %s" % (text, str(e)))
        def selector(session, models, results, spec=text):
            objects, used, unused = ObjectsArg.parse(spec, session)
            results.combine(objects)
        selector.name_text = text
        from chimerax.core.commands import register_selector
        register_selector(name, selector, session.logger)
name_desc = CmdDesc(required=[("name", StringArg)],
                    optional=[("text", RestOfLine)],
                    non_keyword=["text"])


def name_frozen(session, name, objects):
    if name == "all":
        raise UserError("\"all\" is reserved and cannot be redefined")
    from chimerax.core.commands import register_selector
    register_selector(name, objects, session.logger)
name_frozen_desc = CmdDesc(required=[("name", StringArg),
                                     ("objects", ObjectsArg)])


def name_delete(session, name):
    from chimerax.core.commands import deregister_selector
    if name != "all":
        deregister_selector(name, session.logger)
    else:
        from chimerax.core.commands import list_selectors, get_selector
        for name in list_selectors():
            sel = get_selector(name)
            if not _is_builtin(sel):
                deregister_selector(name, session.logger)
name_delete_desc = CmdDesc(required=[("name", StringArg)])


def name_list(session, all=False, log=True):
    from chimerax.core.commands import list_selectors
    targets = {}
    for name in sorted(list_selectors()):
        value = _get_name_desc(name, all)
        if value:
            if log:
                session.logger.info('\t'.join([name, value]))
            targets[name] = value
    if not targets and log:
        session.logger.info("There are no user-defined targets.")
    return targets
name_list_desc = CmdDesc(optional=[("all", NoArg)])


def _get_name_desc(name, builtin_okay):
    from chimerax.core.commands import get_selector
    from chimerax.core.objects import Objects
    sel = get_selector(name)
    if callable(sel):
        if _is_builtin(sel):
            if not builtin_okay:
                return None
            value = "[Built-in]"
        else:
            try:
                value = sel.name_text
            except AttributeError:
                value = "[Function]"
    elif isinstance(sel, Objects):
        title = []
        if sel.num_atoms:
            title.append("%d atoms" % sel.num_atoms)
        if sel.num_bonds:
            title.append("%d bonds" % sel.num_bonds)
        if len(sel.models) > 1:
            title.append("%d models" % len(sel.models))
        value = "[%s]" % ', '.join(title)
    else:
        value = str(sel)
    return value


def _is_builtin(func):
    mod_name = func.__module__
    return (mod_name.startswith("chimerax.core") or
            mod_name.startswith("chimerax.chem_group"))
