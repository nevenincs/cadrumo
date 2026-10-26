"""Deterministic MCP and CLI conformance scenarios for the Cadrumo operator surface.

Golden scenarios declare the expected tool trajectory and provenance for one
workflow. The runner resolves each trajectory against the live command surface,
checks the declared Modelo lifecycle order, and checks the registry grounding
and verification contract of the revision the scenario resolves to. It
recalculates no tax value and executes no agent.

The evaluator consumes core wire records, application-owned action and
precondition contracts, shared client command declarations and the public tax
and runtime command surfaces. Resolved recovery actions use their owning
executable's graph and entrypoint. Agent, provider and model policy belongs to
the products that execute them; runtime and session acceptance belongs to its
own test domain.

This initialiser is an inert namespace marker and forwards no symbols.
"""

from __future__ import annotations
