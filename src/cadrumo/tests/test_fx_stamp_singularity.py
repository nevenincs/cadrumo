"""FX-stamp singularity gate: one authority decides the euro-conversion policy.

``resolve_fx_conversion_stamp`` (:mod:`cadrumo.domain.currency.service`) is the
single production answer to "at which date is this record's euro rate taken, and
when is it deliberately left unstamped?". No other production module may reach a
rate provider to decide it.

The distinction this gate protects is between a *value source* and a *policy*,
and it is the reason the duplication survived so long. The rate SOURCE was
already properly centralised: one :class:`ExchangeRateProvider` protocol, one
``EcbReferenceRateProvider`` adapter behind it. What was duplicated was the
decision made AROUND that source — convert at the record's own operation date
(Ley 46/1998 art. 36), skip a euro record, and leave an unresolvable foreign
record unstamped rather than defaulting. That policy was hand-declared in full
at two application call sites, ``_stamp_fx_conversion`` in the rich catalogue's
creation path and ``_resolve_fx_stamp`` in the business-operation invoice
service. They agreed value-for-value on every input including both failure
modes, so nothing was wrong — but neither symbol was referenced outside its own
module, so no parity test existed and neither would have noticed the other
changing.

The unstamped-on-failure half is the load-bearing one. An unstamped record
reports no euro value and is held back from projection, which an operator can
see and correct; a fabricated or assumed rate would flow silently into a filed
euro amount indistinguishable from a real one. A policy with that consequence
should not be a convention held identically in two places by nobody's
enforcement.

Detection is a call-site check over the real ``ast`` module, recomputed every
run against the production tree with NO stored baseline and NO per-violation
allowlist: a production call to ``.get_eur_rate(...)`` outside the sanctioned
modules is a second site deciding the policy.

Two module families are sanctioned, for different reasons. ``domain.currency``
is where the decision lives — both its consumers, the normalization service and
the stamp resolver, legitimately reach the provider. ``adapters.outbound.fx`` is
where the protocol is IMPLEMENTED, and an implementation naming its own method
is not a second policy.

Known limit: a caller that binds the method indirectly (``getattr``, or a stored
reference passed around) is invisible to a static walk, the same residual the
sibling gates document. The gate raises the cost of a third copy; it does not
make one impossible.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The rate-provider method whose call site IS the policy decision.
_PROVIDER_METHOD = "get_eur_rate"

#: Modules permitted to reach a rate provider: the policy's home, and the
#: adapter package that implements the protocol.
_SANCTIONED = (
    Path("src/cadrumo/domain/currency/service.py"),
    Path("src/cadrumo/adapters/outbound/fx"),
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRODUCTION_ROOT = _REPO_ROOT / "src" / "cadrumo"


def _is_sanctioned(path: Path) -> bool:
    """Return whether ``path`` is a sanctioned module or lives under one."""
    relative = path.relative_to(_REPO_ROOT)
    return any(relative == allowed or allowed in relative.parents for allowed in _SANCTIONED)


def _rate_provider_calls(tree: ast.AST) -> list[str]:
    """Return the enclosing function names of every ``.get_eur_rate(...)`` call."""
    callers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == _PROVIDER_METHOD
            ):
                callers.append(node.name)
                break
    return callers


def _production_modules() -> list[Path]:
    """Return every production module, test packages excluded."""
    return [
        path
        for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def test_the_detector_fires_on_the_canonical_policy() -> None:
    """Positive control: the detector sees the sanctioned call sites.

    Without this, a detector matching nothing — a renamed method, a broken walk —
    would report a clean tree forever while the gate below passed vacuously.
    """
    canonical = _REPO_ROOT / Path("src/cadrumo/domain/currency/service.py")
    assert canonical.is_file(), "the currency service moved; retarget _SANCTIONED"

    callers = _rate_provider_calls(ast.parse(canonical.read_text(encoding="utf-8")))
    assert "resolve_fx_conversion_stamp" in callers, (
        "the detector no longer sees the canonical stamp policy reaching the "
        "rate provider; retarget the constants rather than weakening the check"
    )


def test_a_third_copy_would_be_caught() -> None:
    """Prove the discrimination on synthetic source, not on the live tree.

    The control above and the scan below would both pass for a detector that
    only ever matched the module it is pointed at. Parsing a synthetic copy
    proves it catches a NEW one without writing one into the repository.
    """
    a_third_copy = """
def _stamp_it(currency, on_date, provider):
    if currency == "EUR":
        return None
    return provider.get_eur_rate(currency, on_date)
"""
    an_innocent_consumer = """
def _render(stamp):
    return format(stamp.rate, "f") if stamp is not None else ""
"""
    assert _rate_provider_calls(ast.parse(a_third_copy)) == ["_stamp_it"]
    assert _rate_provider_calls(ast.parse(an_innocent_consumer)) == []


def test_only_the_currency_domain_reaches_a_rate_provider() -> None:
    """No production site outside the sanctioned modules decides the FX policy."""
    offenders = {
        path.relative_to(_REPO_ROOT).as_posix(): callers
        for path in _production_modules()
        if not _is_sanctioned(path) and (callers := _rate_provider_calls(ast.parse(path.read_text(encoding="utf-8"))))
    }

    assert not offenders, (
        "these production sites reach a rate provider directly instead of "
        f"calling resolve_fx_conversion_stamp: {offenders}. Two hand-declared "
        "copies of this policy previously agreed with each other by convention "
        "alone, with no parity test between them. Route through the canonical "
        "resolver: leaving a foreign record unstamped when no rate resolves is "
        "what keeps a fabricated rate out of a filed euro amount, and that "
        "decision belongs in one place."
    )
