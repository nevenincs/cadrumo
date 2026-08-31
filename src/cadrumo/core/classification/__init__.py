"""Sensitivity classification primitives for persisted state.

Every persisted record (SQL row, file-backed envelope, blob, secret-store
entry, audit-log entry) declares a :class:`SensitivityClass`. Each class maps to
a default :class:`ClassificationPolicy` resolved by :func:`default_policy_for`;
the policy pins the at-rest treatment (plaintext or ciphertext-required),
retention behaviour, and the redaction rule references that the audit sink and
run-trace path honour. Operator-facing output uses
:class:`OutputSensitivityClass` and :func:`default_output_policy_for` so CLI
public output can be classified without pretending it is a persisted record.

The default policy table is the single point of truth. Per-domain
repositories MAY override the default for an individual record (e.g.
when an operator tags a corpus blob as identity-bearing), but the
default is always available via :func:`default_policy_for`. Redaction
rule references stored as names are resolved to live
:class:`RedactionRule` instances by :mod:`core.redaction`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
