"""Every production site that mints an IVA observation states the rate it carried.

Modelo 303 and Modelo 390 bindings select on ``applied_rate`` wherever a box is
rate-specific, because a tier stopped identifying a rate the moment the 2023-2024
transitional rates began coexisting with their tier's ordinary one. A producer
that omits the field therefore mints rows that reach no rate-specific box, and
the amount leaves the declared total silently.

That has already been mistaken for a live under-declaration once, and the
diagnosis turned on enumerating the producers rather than reasoning about the two
everyone remembered. This gate is that enumeration, kept honest: it walks the
production tree for the construction itself, so a NEW producer is caught by
existing, not by anyone repeating the sweep.

The second half is the one that matters longest. ``IvaLedgerCandidate`` cannot
express a rate at all, so wiring it would reintroduce the defect wholesale. It is
unwired today, which is the only reason that is safe, and this asserts the
unwiring rather than trusting it -- a gate that bites on WIRING survives whoever
wires it not having read why they should not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRODUCTION_ROOT = Path(__file__).resolve().parent.parent

#: Sites permitted to omit ``applied_rate``, keyed by (module stem, enclosing
#: function) and never by line number, each with the reason it is exempt. An
#: entry that no longer matches a real site fails below, so a stale exemption
#: cannot outlive the code it excused.
_EXEMPT: dict[tuple[str, str], str] = {
    (
        "_iva_ledger",
        "validate_iva_ledger_observation",
    ): (
        "Projects an IvaLedgerCandidate, which carries no applied_rate field, so this "
        "site CANNOT state one -- the omission is upstream in the candidate type. Safe "
        "only while that type has no production consumer, which "
        "test_the_rate_blind_candidate_type_stays_unwired asserts: wiring it reds there "
        "rather than silently minting rate-less rows here."
    ),
}

#: The candidate type that cannot express a rate. Listed by name because the
#: point is to notice if it acquires a production consumer, not to import it.
_RATE_BLIND_CONSTRUCTORS = ("IvaLedgerCandidate",)


def _production_files() -> list[Path]:
    return [
        path
        for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "_data" not in path.parts
    ]


def _enclosing_function(tree: ast.Module, target: ast.Call) -> str:
    best = "<module>"
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.lineno <= target.lineno and target.lineno <= (node.end_lineno or node.lineno):
            best = node.name
    return best


def _observation_constructions() -> list[tuple[Path, str, ast.Call]]:
    found: list[tuple[Path, str, ast.Call]] = []
    for path in _production_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparseable peer WIP
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "id", getattr(node.func, "attr", "")) != "IvaLedgerObservation":
                continue
            # The class statement itself is not a construction.
            found.append((path, _enclosing_function(tree, node), node))
    return found


def test_every_production_construction_states_the_applied_rate() -> None:
    """A producer that omits the rate mints rows no rate-specific box can take."""
    constructions = _observation_constructions()
    assert constructions, "found no IvaLedgerObservation construction at all -- the scanner is broken"

    offenders: list[str] = []
    for path, function, call in constructions:
        if any(keyword.arg == "applied_rate" for keyword in call.keywords):
            continue
        key = (path.stem, function)
        if key in _EXEMPT:
            continue
        offenders.append(f"{path.relative_to(_PRODUCTION_ROOT)}::{function} (line {call.lineno})")

    assert not offenders, (
        "these production sites mint an IvaLedgerObservation without stating applied_rate, "
        "so their rows reach no rate-specific binding: " + ", ".join(sorted(offenders))
    )


def test_no_exemption_outlives_the_site_it_excused() -> None:
    """A stale exemption is worse than none: it silently permits a new omission."""
    live = {(path.stem, function) for path, function, _ in _observation_constructions()}
    stale = sorted(f"{stem}::{function}" for stem, function in _EXEMPT if (stem, function) not in live)

    assert not stale, f"exemptions naming sites that no longer exist: {stale}"


def test_the_rate_blind_candidate_type_stays_unwired() -> None:
    """Wiring a constructor that cannot express a rate must red, not ship.

    ``IvaLedgerCandidate`` carries no ``applied_rate`` field, so every observation
    built from one is rate-less. It has no production consumer today and that is
    the only reason the narrowed bindings are safe. If someone wires it, this
    fails and points at the field that has to exist first.
    """
    consumers: list[str] = []
    for path in _production_files():
        if path.name == "_iva_ledger.py":
            # Its owning module defines the type and its validators; definition
            # is not consumption.
            continue
        if path.name == "__init__.py":
            # A facade re-export makes the name reachable, not used.
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(name in text for name in _RATE_BLIND_CONSTRUCTORS):
            consumers.append(str(path.relative_to(_PRODUCTION_ROOT)))

    assert not consumers, (
        "IvaLedgerCandidate cannot express applied_rate, so wiring it mints rate-less "
        f"observations that rate-specific bindings drop. Wired at: {sorted(consumers)}. "
        "Give the candidate an applied_rate field before consuming it."
    )
