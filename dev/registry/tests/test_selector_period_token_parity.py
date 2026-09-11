"""Parity gate: registry selector tokens and the accepted period vocabulary agree.

A revision's ``period_selector.periods`` declares the tokens that address it.
Those tokens are typed :data:`RegistrySelectorPeriodCode`, so the registry and
the core period vocabulary have to stay in lock-step in both directions:

* a declared token the production validator refuses is an *orphan declaration* -
  the revision is addressed by a token nothing in the vocabulary admits; and
The gate rejects orphan declarations through the canonical selector validator.

Delegation, not restatement
---------------------------

This gate validates through :data:`RegistrySelectorPeriodCode` itself and
It deliberately does NOT
restate which token families are accepted. Restating them would create a second
authority for "what is a valid period token" that could drift from the validator
while staying green - which is the failure this gate exists to prevent.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.core.period import RegistrySelectorPeriodCode
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_SELECTOR_ADAPTER = TypeAdapter(RegistrySelectorPeriodCode)


def _canonical_selector_form(declared_code: str) -> str:
    """Return the token as the selector field would store it."""
    return str(_SELECTOR_ADAPTER.validate_python(declared_code))


def collect_declared_selector_tokens() -> dict[str, tuple[str, ...]]:
    """Return every declared selector token mapped to its owning revisions."""
    modelos, _catalogues = bundled_registry_tree()
    owners: dict[str, set[str]] = {}
    for modelo in modelos:
        for revision in modelo.revisions.values():
            selector = getattr(revision, "period_selector", None)
            for period in getattr(selector, "periods", ()) or ():
                owners.setdefault(str(period), set()).add(f"{modelo.id}:{revision.id}")
    return {declared_code: tuple(sorted(revisions)) for declared_code, revisions in owners.items()}


def count_revisions_declaring_a_selector() -> int:
    """Return how many revisions declare at least one selector period."""
    modelos, _catalogues = bundled_registry_tree()
    return sum(
        1
        for modelo in modelos
        for revision in modelo.revisions.values()
        if getattr(getattr(revision, "period_selector", None), "periods", ())
    )


def orphan_selector_tokens(declared: Mapping[str, tuple[str, ...]]) -> list[str]:
    """Return declared tokens the production selector validator refuses."""
    orphans: list[str] = []
    for declared_code, owners in sorted(declared.items()):
        try:
            _SELECTOR_ADAPTER.validate_python(declared_code)
        except ValidationError as exc:
            reason = exc.errors()[0]["msg"] if exc.errors() else "refused"
            orphans.append(f"{declared_code!r} declared by {', '.join(owners)}: {reason}")
    return orphans


def non_canonical_selector_tokens(declared: Mapping[str, tuple[str, ...]]) -> list[str]:
    """Return accepted tokens declared in a form the selector would rewrite."""
    drifted: list[str] = []
    for declared_code, owners in sorted(declared.items()):
        try:
            canonical = _canonical_selector_form(declared_code)
        except ValidationError:
            continue  # an orphan; reported by orphan_selector_tokens instead
        if canonical != declared_code:
            drifted.append(f"{declared_code!r} declared by {', '.join(owners)} normalises to {canonical!r}")
    return drifted


def test_every_declared_selector_token_is_accepted() -> None:
    """No revision is addressed by a token the period vocabulary refuses."""
    orphans = orphan_selector_tokens(collect_declared_selector_tokens())
    assert not orphans, (
        "registry period_selector tokens refused by the production validator - "
        "either correct the TOML or widen the accepted vocabulary in core:\n" + "\n".join(orphans)
    )


def test_declared_selector_tokens_are_in_canonical_form() -> None:
    """A declared token reads in the TOML as it is stored after validation."""
    drifted = non_canonical_selector_tokens(collect_declared_selector_tokens())
    assert not drifted, (
        "registry period_selector tokens whose declared spelling differs from the stored form; "
        "rewrite the TOML to the canonical spelling so the file matches the compiled value:\n" + "\n".join(drifted)
    )


def test_the_gate_measured_a_real_corpus() -> None:
    """Pin the corpus so a discovery that stops matching reds instead of passing."""
    declared = collect_declared_selector_tokens()
    revisions = count_revisions_declaring_a_selector()
    assert revisions > 80, f"only {revisions} revisions declare a selector; discovery has stopped matching"
    assert len(declared) > 25, f"only {len(declared)} distinct selector tokens found; the fold collapsed"
    assert all(owners for owners in declared.values()), "a token was recorded with no owning revision"


def test_the_orphan_check_reports_a_token_the_validator_refuses() -> None:
    """Drive a refused token through the real fold to prove it can fail."""
    clean = collect_declared_selector_tokens()
    assert not orphan_selector_tokens(clean)

    poisoned = {**clean, "NOT-A-PERIOD": ("999:synthetic",)}
    orphans = orphan_selector_tokens(poisoned)

    assert len(orphans) == 1
    assert "NOT-A-PERIOD" in orphans[0]
    assert "999:synthetic" in orphans[0]


def test_the_canonical_form_check_reports_a_drifted_spelling() -> None:
    """An accepted token declared in a non-canonical spelling is reported."""
    clean = collect_declared_selector_tokens()
    assert not non_canonical_selector_tokens(clean)

    # The selector lowercases administrative tokens, so an upper-case declaration
    # is accepted but stored differently from how the TOML spells it.
    drifted = non_canonical_selector_tokens({**clean, "ALTA": ("999:synthetic",)})

    assert len(drifted) == 1
    assert "ALTA" in drifted[0]
