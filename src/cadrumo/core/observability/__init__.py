"""Run-trace observability: run_id propagation, JSONL audit logging, replay.

Inert namespace. Each contract is reached at its own defining module:
:mod:`~cadrumo.core.observability.context` for the contextvars boundary
that mints a ``run_id``, ``recorder`` for the single emit primitive,
``models`` for the strict record types written to JSONL, ``replay`` for
deterministic re-entry behind its corpus-drift refusal, ``store`` for the
read-only accessors over persisted traces, and ``capture``, ``fingerprint``,
``golden``, ``sink``, ``redaction_rules`` and ``errors`` for the rest.

This package re-exported sixty-one names through those eleven modules. The
map is retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
