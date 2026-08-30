"""The reverse binding-to-casilla join, and the invariant its callers rest on.

``casillas_by_binding`` is the exact dual of ``bound_casilla_binding_ids``:
one answers "which bindings feed this casilla", the other "which casillas does
this binding feed". Defining the second in terms of the first is what makes
disagreement structurally impossible, so the corpus-wide transposition test
below is the load-bearing one - it would fail the moment either direction grew
a predicate the other did not.

The gate at the end is deliberately NOT an assertion that no casilla anywhere
declares a binding while non-BOUND. Fifty do, all in M232's 2018 revision, all
``informational``. An emptiness assertion would therefore red on its first run
and invite an M232 carve-out. What actually matters to the callers is narrower
and is what is asserted: no revision the rate-box derivation reads may contain
such a casilla, because there the dual's drop would silently remove a box's
money from the mapping.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....core.casilla_id import validated_casilla_id
from .....core.aggregation import BindingSourceKind
from ..authority import bundled_authority
from ..bindings import bound_casilla_binding_ids, casillas_by_binding
from ..schema import ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL = ("ley-37-1992:art-91",)
_SOURCE = ("aeat-dr-390-2025",)

# The SAME member ``_ledger_iva_bindings_by_partition_key`` filters on, referenced
# rather than re-derived. A string heuristic over BindingSourceKind resolves to this
# one member today and would silently widen the day a second ledger-IVA kind is added,
# scoping this gate over revisions the rate-box derivation never reads.
_RATE_BOX_SOURCE = BindingSourceKind.LEDGER_IVA_AGGREGATION


def _casilla(
    casilla_id: str,
    *,
    number: str,
    input_kind: str,
    binding: str | None,
    alternate_bindings: tuple[str, ...] = (),
) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        localization_keys=(f"test.schema.casilla.{number}.label",),
        section=("iva", "anual"),
        input_kind=input_kind,
        binding=binding,
        alternate_bindings=alternate_bindings,
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _revision(casillas: tuple[CasillaDefinition, ...]) -> ModeloRevision:
    return ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
        casillas=casillas,
    )


def test_schema_refuses_a_bound_casilla_that_declares_no_binding() -> None:
    """The canonical schema refuses the invalid state before the join can run.

    A BOUND casilla with no binding is a registry declaration error. Keeping the
    proof at model construction exercises the real public boundary instead of
    bypassing Pydantic validation to manufacture an impossible join input.
    """
    with pytest.raises(ValidationError, match="must declare binding"):
        _casilla(
            validated_casilla_id("01", surface="test.dual.bound_without_binding"),
            number="01",
            input_kind="bound",
            binding=None,
        )


def test_a_non_bound_casilla_carrying_a_binding_contributes_nothing() -> None:
    """The documented drop, pinned so it cannot become a silent inclusion.

    Fifty such casillas exist in the corpus (M232 2018, all ``informational``),
    so this is live behaviour and not a hypothetical.
    """
    informational = validated_casilla_id("02", surface="test.dual.informational")
    revision = _revision(
        (_casilla(informational, number="02", input_kind="informational", binding="m232-vinculada-1-nif"),)
    )

    assert casillas_by_binding(revision) == {}


def test_schema_refuses_a_primary_binding_repeated_as_an_alternate() -> None:
    """The reverse join receives only canonical, non-duplicated binding axes."""
    with pytest.raises(ValidationError, match="must not repeat primary binding"):
        _casilla(
            validated_casilla_id("03", surface="test.dual.duplicate"),
            number="03",
            input_kind="bound",
            binding="m390-total",
            alternate_bindings=("m390-total",),
        )


def test_alternate_bindings_reach_the_mapping() -> None:
    """A casilla reached only through an alternate is still that binding's money."""
    casilla_id = validated_casilla_id("04", surface="test.dual.alternate")
    revision = _revision(
        (
            _casilla(
                casilla_id,
                number="04",
                input_kind="bound",
                binding="m390-primary",
                alternate_bindings=("m390-equivalent",),
            ),
        )
    )

    mapping = casillas_by_binding(revision)

    assert mapping == {"m390-primary": (casilla_id,), "m390-equivalent": (casilla_id,)}


def test_the_dual_transposes_the_forward_primitive_across_the_whole_corpus() -> None:
    """The two directions cannot disagree, checked against every bundled revision.

    This is the property the reverse join exists to guarantee, and it is checked
    against registry-authoritative data rather than a fixture, so a predicate
    added to either direction alone reds here.
    """
    authority = bundled_authority()
    checked_revisions = 0
    checked_pairs = 0

    for modelo_id in sorted(_bundled_modelo_ids()):
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            expected: dict[str, list[str]] = {}
            for casilla in revision.casillas:
                for binding_id in bound_casilla_binding_ids(casilla):
                    populated_by = expected.setdefault(binding_id, [])
                    if casilla.id not in populated_by:
                        populated_by.append(casilla.id)
                        checked_pairs += 1

            assert casillas_by_binding(revision) == {
                binding_id: tuple(casilla_ids) for binding_id, casilla_ids in expected.items()
            }, f"M{modelo_id}/{revision.id}: the dual disagrees with the forward primitive"
            checked_revisions += 1

    assert checked_revisions >= 90, (
        f"only {checked_revisions} revisions were compared; the corpus carries 94, so this "
        "assertion passed vacuously over a truncated corpus rather than proving the transposition"
    )
    assert checked_pairs > 0, "no bound casilla was reached at all, so the comparison proved nothing"


def test_no_ledger_iva_revision_declares_a_binding_on_a_non_bound_casilla() -> None:
    """The invariant the rate-box retarget actually rests on.

    ``derive_rate_box_partitions`` and ``rate_box_unscreened_groups`` read only
    ledger-IVA bindings, and they now read the strict dual, which drops any
    non-BOUND casilla carrying a binding. So a casilla that went
    ``informational``-with-a-binding inside a revision those functions reach
    would silently vanish from the mapping and understate a rate box.

    Scoped to the revisions the derivation reads rather than asserted over the
    whole corpus, because the whole-corpus population is not empty: M232's 2018
    revision declares fifty of them. An emptiness assertion would red here on
    its first run and the cheapest repair would be an M232 allowlist.
    """
    authority = bundled_authority()
    offenders: list[str] = []
    ledger_iva_revisions = 0

    for modelo_id in sorted(_bundled_modelo_ids()):
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            if not any(binding.source is _RATE_BOX_SOURCE for binding in revision.bindings):
                continue
            ledger_iva_revisions += 1
            for casilla in revision.casillas:
                declares_binding = casilla.binding is not None or bool(casilla.alternate_bindings)
                if declares_binding and not bound_casilla_binding_ids(casilla):
                    offenders.append(
                        f"M{modelo_id}/{revision.id} casilla {casilla.id!r} "
                        f"input_kind={casilla.input_kind!r} declares a binding"
                    )

    assert not offenders, (
        "a revision the rate-box derivation reads declares a binding on a non-BOUND casilla, "
        "so the canonical join drops it and the rate-box mapping understates: " + "; ".join(offenders)
    )
    assert ledger_iva_revisions > 0, (
        "no revision carrying ledger-IVA bindings was found, so this gate asserted nothing; "
        "the source-kind filter is wrong, not the corpus"
    )


def _bundled_modelo_ids() -> tuple[str, ...]:
    from importlib.resources import files

    root = files("cadrumo._data.registry.aeat.modelos")
    return tuple(entry.name for entry in root.iterdir() if entry.is_dir())
