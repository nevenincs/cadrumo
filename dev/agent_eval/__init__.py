"""Operator golden-task eval: trajectory + provenance assertions over the harness.

The operator-side counterpart of the persona testimonial gate. A golden scenario
declares the expected tool trajectory for a workflow and the provenance the result
must carry; the runner asserts the trajectory resolves against the live CLI
surface, follows the modelo lifecycle order, is consistent with the shipped skill
playbook, and that the modelo's casillas carry their legal grounding in the
registry. It reuses the scenario methodology of the persona testimonials without
inheriting their knowledge-withholding brief, and it never hand-computes a tax
value (that would be a tautological calculation test).

Boundary posture: this is dev tooling built ON TOP of the shipped surfaces, not
beside them. Harness-owned material — skills, personas, operator rules, workspace
materialisation — comes from the ``cadrumo_harness`` distribution's public facade;
taxpayer and application state comes from the real ``aeat`` CLI / ``cadrumo-mcp``
dispatch the caller performs and hands in as decoded envelope data; and the only
``cadrumo`` imports here are its public ``cadrumo.core`` primitives (the envelope
status enum, the encoding constant, the hashing helper, and the registry authority
facade for the two registry-shaped dimensions no CLI verb projects). Nothing in
this package imports ``cadrumo``'s adapters, application, domain or entrypoints
layers, and nothing imports the MCP server layer.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
