"""Scaffolding for a new AEAT modelo's registry authoring tree.

Generates the standard directory skeleton a new modelo revision needs
(``manifest.toml``, ``revisions/<revision-id>/{revision.toml, casillas/,
formulas/, bindings/, completeness_manifest/, verification_expectations/,
export_layouts/, extraction_profiles/, application_links/}``) and
surfaces the contributor checklist for taking the scaffold calc-grade.

Run via ``python -m dev.registry.newmodelo scaffold <modelo_id> <revision_id>``
(add ``--check`` to preview drift without writing, ``--force`` to overwrite
existing placeholder files) or ``python -m dev.registry.newmodelo checklist``
to print the checklist alone.

Major declarations:

* :class:`~dev.registry.newmodelo.manager.NewModeloScaffoldManager` — plans,
  writes, and checks the skeleton directory tree.
* :data:`~dev.registry.newmodelo.checklist.CHECKLIST` — the
  contributor checklist.
"""
