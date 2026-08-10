"""Reason-bearing acceptance list for complexity hotspots.

The committed baseline (``complexity_baseline.json``) is a bare
``key -> score`` mapping with nowhere to say WHY a row is tolerated, and it is
regenerated wholesale by ``--write-baseline``, which accepts everything
currently failing in one move. Neither property suits a reviewed decision: the
first loses the judgement, and the second cannot distinguish "this is a flat
guard chain and fine at any length" from "this function got worse".

This file is the reviewed half. Every entry names the score it was accepted AT
and states its reason, so:

* a row that grows FURTHER still fails, because acceptance is pinned to the
  value reviewed rather than to the key;
* the reason is committed beside the acceptance, which is what makes the list
  auditable instead of a mute button (``aeat-quality-gates``: allowlists are
  where the judgement moves, so require every entry to state its reason);
* a regression is never grandfathered silently -- accepting a row whose score
  ROSE is a deliberate act with a reason that has to say so.

Shape mirrors the two reason-bearing allowlists this repository already keeps:
``src/cadrumo/locales/_intentional_identical.json`` (key -> reason prose) and
the ``_ALLOWLIST`` in ``src/cadrumo/core/tests/test_modelo_string_usage.py``
(keyed tuple -> reason prose), with the accepted score added because a
complexity row, unlike a locale string, has a magnitude that can drift.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ALLOWLIST_PATH: Final[Path] = Path(__file__).with_name("complexity_allowlist.json")

_METRICS: Final[tuple[str, ...]] = ("cyclomatic", "maintainability", "cognitive")


class ComplexityAllowlistError(RuntimeError):
    """Raised when the allowlist is malformed or an entry states no reason."""


@dataclass(frozen=True)
class AllowedHotspot:
    """One reviewed acceptance: the score it was accepted at, and why."""

    score: float
    reason: str


@dataclass(frozen=True)
class Allowlist:
    """Reviewed acceptances for one scope, keyed the same way the baseline is."""

    cyclomatic: dict[str, AllowedHotspot]
    maintainability: dict[str, AllowedHotspot]
    cognitive: dict[str, AllowedHotspot]

    def ceilings(self, metric: str) -> dict[str, float]:
        """Return ``key -> accepted score`` for merging into a baseline mapping."""
        return {key: entry.score for key, entry in getattr(self, metric).items()}


def _entries(raw: object, *, scope: str, metric: str) -> dict[str, AllowedHotspot]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ComplexityAllowlistError(f"{scope}.{metric} must be an object")
    entries: dict[str, AllowedHotspot] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            raise ComplexityAllowlistError(f"{scope}.{metric}[{key!r}] must be an object with score and reason")
        score = value.get("score")
        reason = value.get("reason")
        if not isinstance(score, int | float):
            raise ComplexityAllowlistError(f"{scope}.{metric}[{key!r}] must state the numeric score it was accepted at")
        # The load-bearing check. An entry with no reason is a mute button, and
        # the whole point of this file is that the judgement is written down.
        if not isinstance(reason, str) or not reason.strip():
            raise ComplexityAllowlistError(f"{scope}.{metric}[{key!r}] must state a non-empty reason")
        entries[str(key)] = AllowedHotspot(score=float(score), reason=reason.strip())
    return entries


def load_allowlist(is_test_run: bool, path: Path = ALLOWLIST_PATH) -> Allowlist:
    """Load the reviewed acceptances for one scope, refusing a reasonless entry."""
    if not path.exists():
        return Allowlist(cyclomatic={}, maintainability={}, cognitive={})
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ComplexityAllowlistError(f"{path.name} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ComplexityAllowlistError(f"{path.name} must contain an object")
    scope = "tests" if is_test_run else "production"
    payload = document.get(scope) or {}
    if not isinstance(payload, dict):
        raise ComplexityAllowlistError(f"{path.name}: {scope} must be an object")
    return Allowlist(**{metric: _entries(payload.get(metric), scope=scope, metric=metric) for metric in _METRICS})
