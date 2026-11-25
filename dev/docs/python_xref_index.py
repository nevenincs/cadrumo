"""Index the Python domain's fuzzy cross-reference search by final name component.

Sphinx resolves a ``refspecific`` Python cross-reference that has no exact
match -- every annotation rendered by the type-hint extensions is one, so a
reference to ``str`` or to a third-party type is the common case -- by scanning
every registered object for a ``.name`` suffix. Over the full API reference
that is a linear scan of the whole object inventory for each such reference,
and it dominates the write phase of a full-scope build.

A name ending in ``.name`` has ``name``'s final component as its own final
component, so grouping the inventory by final component yields exactly the
candidates the scan would test, in the inventory's own order. The domain below
answers the fuzzy branch from that grouping and defers every other lookup to
Sphinx unchanged, so the matches it returns are the matches Sphinx returns.
"""

from __future__ import annotations

from collections.abc import Set
from typing import Any, override

from sphinx.application import Sphinx
from sphinx.domains.python import ObjectEntry, PythonDomain
from sphinx.environment import BuildEnvironment


class IndexedPythonDomain(PythonDomain):
    """The Python domain with its fuzzy suffix search served from an index."""

    _suffix_index: dict[str, list[str]] | None = None
    _indexed_inventory: tuple[int, int] | None = None

    def _candidates(self, name: str) -> list[str]:
        objects = self.objects
        # Every inventory mutation in Sphinx passes through the overrides below;
        # identity and size also guard against a writer that bypasses them.
        inventory = (id(objects), len(objects))
        if self._suffix_index is None or self._indexed_inventory != inventory:
            index: dict[str, list[str]] = {}
            for fullname in objects:
                index.setdefault(fullname.rpartition(".")[2], []).append(fullname)
            self._suffix_index = index
            self._indexed_inventory = inventory
        return self._suffix_index.get(name.rpartition(".")[2], [])

    def _invalidate(self) -> None:
        self._suffix_index = None
        self._indexed_inventory = None

    @override
    def note_object(
        self,
        name: str,
        objtype: str,
        node_id: str,
        aliased: bool = False,
        location: Any = None,
    ) -> None:
        if name not in self.objects:
            self._invalidate()
        super().note_object(name, objtype, node_id, aliased, location)

    @override
    def clear_doc(self, docname: str) -> None:
        self._invalidate()
        super().clear_doc(docname)

    @override
    def merge_domaindata(self, docnames: Set[str], otherdata: dict[str, Any]) -> None:
        self._invalidate()
        super().merge_domaindata(docnames, otherdata)

    @override
    def find_obj(
        self,
        env: BuildEnvironment,
        modname: str,
        classname: str,
        name: str,
        type: str | None,
        searchmode: int = 0,
    ) -> list[tuple[str, ObjectEntry]]:
        bare = name.removesuffix("()")
        if searchmode != 1 or not bare:
            return super().find_obj(env, modname, classname, name, type, searchmode)
        objtypes = list(self.object_types) if type is None else self.objtypes_for_role(type)
        if objtypes is None:
            return []
        objects = self.objects
        if self._has_exact_match(modname, classname, bare, objtypes):
            return super().find_obj(env, modname, classname, name, type, searchmode)
        suffix = f".{bare}"
        return [
            (fullname, objects[fullname])
            for fullname in self._candidates(bare)
            if fullname.endswith(suffix) and objects[fullname].objtype in objtypes
        ]

    def _has_exact_match(self, modname: str, classname: str, bare: str, objtypes: list[str]) -> bool:
        objects = self.objects
        exact = (
            (modname and classname and f"{modname}.{classname}.{bare}"),
            (modname and f"{modname}.{bare}"),
            bare,
        )
        return any(candidate and candidate in objects and objects[candidate].objtype in objtypes for candidate in exact)


def setup(app: Sphinx) -> dict[str, Any]:
    """Replace the Python domain with its indexed equivalent."""
    app.add_domain(IndexedPythonDomain, override=True)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
