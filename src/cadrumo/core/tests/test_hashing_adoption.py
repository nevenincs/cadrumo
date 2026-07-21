"""Recurrence gate: no NEW reducible one-shot SHA-256 body lands in production.

`core.hashing.sha256_hex` is the canonical one-shot bytes->hex digest. Per the
`cli-authority-verb-conformance` decision the existing reducible bodies are NOT
rewritten (low-value churn against a service that already exists); the durable
value is this AST recurrence gate, which prevents a NEW reducible
``sha256(<data>).hexdigest()`` body from landing while allowing the
non-substitutable cryptographic uses it must never block: incremental/streaming
hashing, keyed HMAC, key derivation (HKDF), X509 fingerprints, and raw
digest-byte uses.

Two tests: the gate itself (a per-module additions ratchet against a
grandfathered baseline) and a discrimination proof that the detector actually
flags a new reducible body and never flags the allowed uses — so the gate cannot
silently pass green while its detector is broken.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# __file__ = src/cadrumo/core/tests/test_hashing_adoption.py
#   parents[0] = tests, [1] = core, [2] = cadrumo
_CADRUMO_ROOT = Path(__file__).resolve().parents[2]

#: The canonical helper module is where the one-shot reduction TARGET lives: it
#: legitimately contains the ``sha256(...).hexdigest()`` body every caller
#: delegates to, so it is excluded from the recurrence scan.
_CANONICAL_HELPER = "core/hashing.py"

#: Grandfathered reducible ``sha256(<data>).hexdigest()`` bodies per module,
#: captured at gate introduction. That decision does not rewrite these. The gate
#: ratchets in the reducing direction only: a module may carry FEWER over time
#: (delegate a body to ``sha256_hex`` and, optionally, lower or drop its entry),
#: but a new module or a higher count is a NEW reducible body and fails.
_REDUCIBLE_ONE_SHOT_BASELINE: dict[str, int] = {
    "adapters/inbound/declaracion/_parser.py": 1,
    "adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py": 1,
    "adapters/outbound/aeat/auth/_clave_movil_support.py": 1,
    "adapters/outbound/llm/_cache.py": 1,
    "adapters/persistence/storage/_rotation.py": 1,
    "adapters/persistence/storage/sql/engine.py": 1,
    "agent/_workspace.py": 1,
    "agent/eval/_flywheel.py": 1,
    "application/aggregation/_percepciones_observations_repository.py": 1,
    "application/aggregation/_retencion_observations_repository.py": 1,
    "application/auth/_certificate_sources_operator.py": 1,
    "application/auth/_operator.py": 1,
    "application/calculations/_observations_repository.py": 2,
    "application/filing/_import.py": 1,
    "application/modelo/_m145_communication_records.py": 1,
    "application/modelo/_review_package_recipient_registry.py": 1,
    "application/storage/calc_sheets/_engine.py": 1,
    "application/workflow/_models.py": 1,
    "domain/calculations/registry/_compiled_cache.py": 1,
    "domain/calculations/registry/_validate_evidence.py": 1,
    "domain/calculations/registry/_validate_verdict.py": 1,
    "domain/submission/_models.py": 1,
    "entrypoints/mcp/_telemetry.py": 1,
}


def _is_sha256_constructor(func: ast.expr) -> bool:
    """Whether ``func`` names the sha256 hash constructor (``hashlib.sha256`` or ``sha256``)."""
    if isinstance(func, ast.Attribute):
        return func.attr == "sha256"
    if isinstance(func, ast.Name):
        return func.id == "sha256"
    return False


def _reducible_one_shot_sites(tree: ast.AST, relpath: str) -> list[tuple[str, int]]:
    """Return ``(relpath, lineno)`` for every reducible one-shot sha256 body in ``tree``.

    A reducible body is ``sha256(<data>).hexdigest()``: a one-shot construction
    with at least one positional argument, immediately hex-digested in the same
    expression — exactly what ``core.hashing.sha256_hex`` replaces (a trailing
    slice such as ``[:16]`` is still reducible, the projection stays at the call
    site). NOT reducible, and never returned: an argument-free ``sha256()`` fed
    incrementally through ``.update()``; a ``.digest()`` wanting raw bytes;
    ``hmac.new(..., sha256)`` and other keyed/derived constructors; and any
    construction not directly hex-digested in the same expression.
    """
    sites: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "hexdigest"):
            continue
        inner = node.func.value
        if isinstance(inner, ast.Call) and _is_sha256_constructor(inner.func) and inner.args:
            sites.append((relpath, node.lineno))
    return sites


def _production_reducible_counts() -> dict[str, int]:
    """Count reducible one-shot sha256 bodies per production module (tests + helper excluded)."""
    counts: Counter[str] = Counter()
    for path in _CADRUMO_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        relpath = path.relative_to(_CADRUMO_ROOT).as_posix()
        if relpath == _CANONICAL_HELPER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for site_rel, _line in _reducible_one_shot_sites(tree, relpath):
            counts[site_rel] += 1
    return dict(counts)


def test_no_new_reducible_one_shot_sha256_body_lands() -> None:
    """No new production module, and no grandfathered module, gains a reducible one-shot body.

    Delegating an existing body to ``core.hashing.sha256_hex`` (which lowers a
    count) is always allowed; introducing a new ``sha256(<data>).hexdigest()``
    body is the recurrence this gate bars.
    """
    observed = _production_reducible_counts()

    new_modules = sorted(set(observed) - set(_REDUCIBLE_ONE_SHOT_BASELINE))
    assert not new_modules, (
        "new module(s) introduced a reducible one-shot sha256(<data>).hexdigest() body; "
        "delegate to core.hashing.sha256_hex (keep any truncation/projection at the call site), "
        f"or if the use is genuinely non-substitutable route it through a distinct primitive: {new_modules}"
    )

    regressions = {
        module: {"observed": observed[module], "baseline": _REDUCIBLE_ONE_SHOT_BASELINE[module]}
        for module in observed
        if observed[module] > _REDUCIBLE_ONE_SHOT_BASELINE[module]
    }
    assert not regressions, (
        "module(s) gained additional reducible one-shot sha256(<data>).hexdigest() bodies beyond "
        f"their grandfathered baseline; delegate the new body to core.hashing.sha256_hex: {regressions}"
    )


def test_recurrence_gate_flags_a_new_reducible_body_and_allows_legitimate_uses() -> None:
    """Discrimination proof: the detector flags a reducible body and never the allowed uses.

    Runs the gate's own ``_reducible_one_shot_sites`` detector over synthetic
    sources so a broken detector cannot let the gate pass green. Every reducible
    shape is caught; every non-substitutable cryptographic use the gate protects
    (streaming, digest-byte, HMAC, HKDF, X509) is left untouched.
    """
    reducible_sources = (
        "sha256(payload).hexdigest()",
        "hashlib.sha256(text.encode('utf-8')).hexdigest()",
        "hashlib.sha256(payload).hexdigest()[:16]",  # a trailing slice is still reducible
    )
    for source in reducible_sources:
        assert _reducible_one_shot_sites(ast.parse(source), "probe.py"), (
            f"recurrence detector FAILED to flag a reducible one-shot body: {source!r}"
        )

    allowed_sources = (
        # Incremental / streaming: an argument-free constructor fed via .update().
        "h = hashlib.sha256()\nh.update(chunk)\nout = h.hexdigest()",
        # Raw digest bytes (not hex): e.g. a BIP39-style checksum byte.
        "checksum = hashlib.sha256(entropy).digest()[0]",
        # Keyed HMAC over sha256 — a different, non-substitutable primitive.
        "mac = hmac.new(sub_key, material, sha256).hexdigest()",
        # Key derivation (HKDF) — not a one-shot digest.
        "key = HKDF(algorithm=SHA256(), length=32).derive(secret)",
        # X509 certificate fingerprint — not a hashlib one-shot body.
        "fp = certificate.fingerprint(hashes.SHA256())",
    )
    for source in allowed_sources:
        assert not _reducible_one_shot_sites(ast.parse(source), "probe.py"), (
            f"recurrence detector FALSE-flagged a legitimate non-substitutable use: {source!r}"
        )


def test_recurrence_baseline_is_grounded_in_real_sites() -> None:
    """The grandfathered baseline names real, currently-present reducible bodies.

    Guards the additions ratchet against a fabricated or fully-stale baseline
    that would silently mask a recurrence: every baseline module must still host
    at least one reducible body today (a module reduced to zero must be dropped).
    Bodies REDUCED below a module's recorded count are allowed and do not fail —
    only a baseline entry that no longer matches ANY real body is a grounding
    defect, since the ratchet would then never fire for that module.
    """
    observed = _production_reducible_counts()
    ungrounded = sorted(module for module in _REDUCIBLE_ONE_SHOT_BASELINE if observed.get(module, 0) == 0)
    assert not ungrounded, (
        "baseline module(s) no longer host any reducible one-shot body (fully reduced); "
        f"drop these stale entries so the ratchet stays grounded: {ungrounded}"
    )
