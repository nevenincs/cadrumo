"""Scaffolding for a new AEAT modelo's registry authoring tree.

Generates the standard directory skeleton a new modelo revision needs
(``manifest.toml``, ``revisions/<revision-id>/{revision.toml, casillas/,
formulas/, bindings/, completeness_manifest/, verification_expectations/,
extraction_profiles/, application_links/}``) in edition-delta shape, and
surfaces the contributor checklist for taking the scaffold calc-grade.

Run via ``python -m dev.registry.newmodelo scaffold`` for a new modelo,
``new-edition`` for a preserving existing-modelo delta, or ``checklist`` for
hydrated coverage guidance.

Major declarations:

* :class:`~dev.registry.newmodelo.manager.NewModeloScaffoldManager` — plans and
  writes the selected authoring route.
* :data:`~dev.registry.newmodelo.checklist.CHECKLIST` — the
  contributor checklist.
"""
