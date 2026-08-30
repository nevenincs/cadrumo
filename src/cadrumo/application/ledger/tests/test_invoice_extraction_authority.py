"""The reading prompt's numbers come from this layer, and only from it.

Three properties, each with its own failure mode:

**The resolver follows the authority.** Change what the rate table says and the
resolved values change with it. A resolver holding a literal list satisfies
nothing here.

**The renderer cannot reach around what it is handed.** Rendering from fabricated
values must produce a prompt carrying the fabricated figures and NOT the real
registered ones. This is the property that survives a future edit: a renderer
that re-acquires a helpful "correct" rate for itself fails, no matter how
plausible the helper looks in review.

**The production read path supplies them.** A compiler nothing calls is the
defect this work exists to close. Asserted two ways, because neither alone is
enough: behaviourally, that values handed to the reader's own entry point reach
the prompt bytes a model would receive; and structurally against the router's
AST, that the routing path resolves them and passes them on. The behavioural half
cannot run the router itself without live inference, and the structural half
cannot tell a wired call from an inert one -- together they cover both.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....domain import iva as _iva_module
from ....domain.iva import EUMemberState, IvaCategory, load_iva_rate_table
from ....tests.attribute_scope import scoped_attribute
from ..invoice_extraction_authority import (
    InvoiceExtractionAuthorityValues,
    default_invoice_extraction_period,
    resolve_invoice_extraction_authority_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")

# A percentage no Spanish IVA tier carries, so its appearance in a rendered
# prompt can only have come through the argument under test.
_FABRICATED_PCT = Decimal("37.25")
_FABRICATED_RETENCION_PCT = Decimal("41.75")


def _fabricated_values() -> InvoiceExtractionAuthorityValues:
    """Return values that share no figure with the real registry."""
    return InvoiceExtractionAuthorityValues(
        period=_ANNUAL_2026,
        iva_rate_pcts=(_FABRICATED_PCT,),
        retencion_rate_pcts=(_FABRICATED_RETENCION_PCT,),
        no_printed_tax_categories=(IvaCategory.DOMESTIC_EXEMPT,),
        regime_legend_phrases=("regimen inventado a efectos de prueba",),
    )


class TestTheResolverFollowsTheRateAuthority:
    """Direction one: move the authority, and the resolved values move."""

    def test_a_planted_rate_reaches_the_resolved_values(self) -> None:
        """The mutation is applied at RUNTIME, so no tracked file changes.

        A concurrent sweep therefore cannot commit it, and a crashed run leaves
        no residue -- the shared-tree-safe form of a mutation proof.
        """
        baseline = resolve_invoice_extraction_authority_values(period=_ANNUAL_2026)
        assert _FABRICATED_PCT not in baseline.iva_rate_pcts, (
            "positive control: pick a percentage the registry does not already carry"
        )

        real_table = load_iva_rate_table()
        spain = real_table[EUMemberState.ES]
        planted = spain[0].model_copy(
            update={
                "pct": _FABRICATED_PCT,
                "effective_from": _ANNUAL_2026.start_date,
                "effective_until": None,
            },
        )
        with scoped_attribute(
            _iva_module,
            "load_iva_rate_table",
            lambda: dict(real_table) | {EUMemberState.ES: (*spain, planted)},
        ):
            after = resolve_invoice_extraction_authority_values(period=_ANNUAL_2026)

        assert _FABRICATED_PCT in after.iva_rate_pcts, (
            "the resolver read a snapshot instead of the authority; a registry change would not reach a reader"
        )

    def test_a_narrower_period_resolves_a_narrower_enumeration(self) -> None:
        """A period is a span, and the enumeration is period-dependent.

        Asserted as a SUBSET relation rather than against copied figures: the
        claim is that the annual window unions what a quarter inside it carries,
        which stays true when the registry moves. Hand-copied percentages would
        pass over a resolver that ignored the period entirely.
        """
        annual = resolve_invoice_extraction_authority_values(period=Period.from_year_and_code(2024, "0A"))
        quarter = resolve_invoice_extraction_authority_values(period=Period.from_year_and_code(2024, "3T"))

        assert set(quarter.iva_rate_pcts) < set(annual.iva_rate_pcts), (
            "2024 stepped the reducido tiers mid-year, so an annual window must union what Q3 alone carries"
        )

    def test_the_no_printed_tax_vocabulary_is_the_registry_closed_set(self) -> None:
        """Members, not rendered prose, and drawn from the canonical closed set."""
        resolved = resolve_invoice_extraction_authority_values(period=_ANNUAL_2026)

        assert all(isinstance(member, IvaCategory) for member in resolved.no_printed_tax_categories)

    def test_the_fallback_period_spans_a_whole_civil_year(self) -> None:
        """An unbound document is read against the widest honest window."""
        fallback = default_invoice_extraction_period()

        assert fallback.code == "0A"
        assert fallback.start_date.month == 1
        assert fallback.end_date.month == 12


class TestTheRendererCannotReachAroundItsArgument:
    """Direction two: the prompt carries what it was handed, and nothing else."""

    def test_fabricated_values_reach_the_text_and_the_real_ones_do_not(self) -> None:
        """The assertion that a re-added lookup cannot satisfy.

        Both halves matter. That the fabricated figure APPEARS proves the
        argument is used; that the real registered figures are ABSENT proves it
        is the only source. A renderer that helpfully merged its own lookup with
        the argument would pass the first half alone.
        """
        from ....llm.invoice_extraction_prompt import render_invoice_extraction_prompt

        real = resolve_invoice_extraction_authority_values(period=_ANNUAL_2026)
        rendered = render_invoice_extraction_prompt(values=_fabricated_values())

        assert "37.25" in rendered.text
        assert "41.75" in rendered.text
        assert "regimen inventado a efectos de prueba" in rendered.text
        for pct in real.iva_rate_pcts:
            assert f"{pct.normalize():f}%" not in rendered.text
        for phrase in real.regime_legend_phrases:
            assert phrase not in rendered.text, (
                "the renderer reached the legal vocabulary itself instead of substituting what it was given"
            )

    def test_the_compiled_artefact_reports_the_values_it_rendered(self) -> None:
        """The stamp must describe the read that happened, not a re-resolution."""
        from ....llm.invoice_extraction_prompt import render_invoice_extraction_prompt

        rendered = render_invoice_extraction_prompt(values=_fabricated_values())

        assert rendered.iva_rate_pcts == (_FABRICATED_PCT,)
        assert rendered.period == _ANNUAL_2026


class TestTheProductionReadPathSuppliesTheValues:
    """Direction three: the compiler has a caller on the live reading path."""

    def test_values_passed_to_the_reader_entry_point_reach_the_dispatched_prompt(self) -> None:
        """The reader's own entry point honours supplied values end to end.

        Behavioural rather than structural: it exercises the exact function the
        router calls to build what a model receives, so a parameter that is
        accepted and then ignored fails here. It stops short of dispatching a
        request, because doing so would need live inference this gate must not
        perform.
        """
        from ....llm.evidence_draft_text import build_text_field_extraction_prompt

        prompt = build_text_field_extraction_prompt("Factura 1", values=_fabricated_values())

        assert "37.25" in prompt
        assert "Factura 1" in prompt

    def test_the_router_resolves_before_reading(self) -> None:
        """The resolver is reached from the routing module, not left unwired.

        Asserted against the router's AST so a name inside a comment or
        docstring cannot satisfy it -- the failure mode a source slice has.
        """
        import ast
        from pathlib import Path

        router = Path(__file__).parents[1] / "evidence_draft.py"
        tree = ast.parse(router.read_text(encoding="utf-8"))
        called = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "resolve_invoice_extraction_authority_values" in called, (
            "the read path must resolve the regulatory values it hands the reader"
        )

    def test_the_reader_receives_them_as_a_keyword(self) -> None:
        """And they are passed on, rather than resolved and dropped."""
        import ast
        from pathlib import Path

        router = Path(__file__).parents[1] / "evidence_draft.py"
        tree = ast.parse(router.read_text(encoding="utf-8"))
        keywords = {keyword.arg for node in ast.walk(tree) if isinstance(node, ast.Call) for keyword in node.keywords}

        assert "authority_values" in keywords
