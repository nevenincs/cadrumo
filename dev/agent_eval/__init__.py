"""Operator golden-task eval: trajectory + provenance assertions over the harness.

The operator-side counterpart of the persona testimonial gate. A golden scenario
declares the expected tool trajectory for a workflow and the provenance the result
must carry; the runner asserts the trajectory resolves against the live CLI
surface, follows the modelo lifecycle order, is consistent with the shipped skill
playbook, and that the modelo's casillas carry their legal grounding in the
registry. It reuses the scenario methodology of the persona testimonials without
inheriting their knowledge-withholding brief, and it never hand-computes a tax
value (that would be a tautological calculation test).

What the package imports from the product, as of this writing. No import-linter
contract enforces it; it is a description to keep true, not a boundary:

- ``cadrumo.core`` defining modules: the envelope status enum, the encoding
  constant, hashing, atomic writes, TOML parsing and the operator-action enums.
- ``cadrumo.application`` operator-action and operator-surface modules and the
  modelo precondition profiles (``_action_coverage``, ``_models``, ``_runner``),
  the catalogue and manifest the coverage and suggestion checks read.
- ``cadrumo.entrypoints.cli`` command-graph, parameter-contract and Typer app
  modules (``_runner``, ``_action_coverage``), so a scenario is resolved and run
  against the live command tree in process.
- ``cadrumo_harness.resources`` for the shipped skill documents.

Nothing in the scoring modules imports ``cadrumo``'s adapters or domain layers
or the MCP server layer. The tests under ``tests/`` are not held to this list:
they import adapters, application modules, ``cadrumo_harness`` and other
``dev`` packages freely.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
