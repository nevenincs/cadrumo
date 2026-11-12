"""Tests for the :class:`IvaExemptionArticle` discriminator on
:class:`IvaClassificationResult`.

Authority: ``iva-exemption-article-design``. The discriminator
is optional; ``None`` preserves today's collapsed
``DOMESTIC_EXEMPT`` behaviour. A stamped value is only valid when the
category is ``DOMESTIC_EXEMPT``; pairing it with any other category is
rejected at construction time so a stamped-but-unreachable
discriminator cannot reach the calculation chain.
"""

from __future__ import annotations

import re
from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.iva_legal_vocabulary import resolve_iva_exemption_article_catalogue
from ...calculations.registry.prorrata_volume_catalogue import resolve_prorrata_volume_catalogue
from ..classification import IvaClassificationResult
from ..schema import IvaCategory, IvaExemptionArticle

_ON_DATE = date(filing_year_envelope().horizon, 6, 15)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_classification_result_accepts_no_exemption_article_by_default() -> None:
    """The discriminator is optional; absence is the canonical default."""
    result = IvaClassificationResult(
        category=IvaCategory("domestic_exempt"),
        matched_rule_id="R04_immovable_property_exempt",
        effective_date=_ON_DATE,
    )

    assert result.exemption_article is None


def test_classification_result_stamps_exemption_article_when_domestic_exempt() -> None:
    """Stamping the discriminator on a DOMESTIC_EXEMPT result is accepted."""
    result = IvaClassificationResult(
        category=IvaCategory("domestic_exempt"),
        matched_rule_id="R20_uno_8_asistencia_social",
        exemption_article=IvaExemptionArticle("art_20_uno_8"),
        effective_date=_ON_DATE,
    )

    assert result.exemption_article == IvaExemptionArticle("art_20_uno_8")


def test_classification_result_rejects_exemption_article_on_non_exempt_category() -> None:
    """The validator rejects a discriminator paired with any non-DOMESTIC_EXEMPT category."""
    # Pydantic v2 wraps validator-raised exceptions in ValidationError;
    # the inner IvaValidationError message reaches the rendered output.
    for non_exempt_category in (
        IvaCategory("domestic_general"),
        IvaCategory("domestic_reduced"),
        IvaCategory("intra_community_supply"),
        IvaCategory("export_third_country_zero_rated"),
        IvaCategory("export_assimilated_zero_rated"),
        IvaCategory("operacion_no_sujeta"),
    ):
        with pytest.raises(ValidationError) as exc:
            IvaClassificationResult(
                category=non_exempt_category,
                matched_rule_id="R_test",
                exemption_article=IvaExemptionArticle("art_20_uno_8"),
                effective_date=_ON_DATE,
            )

        message = str(exc.value)
        assert "exemption_article" in message, non_exempt_category
        assert "DOMESTIC_EXEMPT" in message, non_exempt_category
        assert non_exempt_category.value in message


def test_exemption_article_catalogue_membership_matches_accepted_correction(
    operation: PinnedAuthorityOperation,
) -> None:
    """The vocabulary carries the decided art. 20.Uno members and the catch-all.

    This test fails when the removed Article 20.Uno.26 route is
    reintroduced without an approved contract change.
    """
    expected = {f"art_20_uno_{number}" for number in (1, 3, 5, 8, 9, 10, 12, 14, 16, 18, 22, 23)} | {"art_20_other"}
    catalogue = resolve_iva_exemption_article_catalogue(effective_date=_ON_DATE, authority=operation)
    actual = {member.value for member in catalogue.all_articles}
    assert actual == expected


def _bundled_liva_text(corpus_ref: str) -> str:
    """Return the bundled extracted text a ``corpus/...html#anchor`` reference names."""
    *directories, name = corpus_ref.split("#", 1)[0].removeprefix("corpus/").split("/")
    return bundled_path("corpus", *directories, f"{name}.extracted.md").read_text(encoding="utf-8")


def _art_20_uno_paragraphs(text: str) -> dict[int, str]:
    """Split apartado Uno of LIVA art. 20 into its numbered paragraphs.

    A number restarting below the last one seen belongs to a nested list (the
    rehabilitation requirements of 22.º), so it stays inside its paragraph.
    """
    uno = text[text.index("Uno. Estarán exentas") : text.index("\nDos. ")]
    paragraphs: dict[int, list[str]] = {}
    current = 0
    for line in uno.splitlines():
        match = re.match(r"(\d+)\.º", line)
        if match is not None and int(match.group(1)) > current:
            current = int(match.group(1))
            paragraphs[current] = []
        if current:
            paragraphs[current].append(line)
    return {number: "\n".join(lines) for number, lines in paragraphs.items()}


def test_each_numbered_member_cites_the_liva_art_20_uno_paragraph_its_token_names(
    operation: PinnedAuthorityOperation,
) -> None:
    """A token ``art_20_uno_N`` cites apartado Uno, número N, and that paragraph's own text."""
    catalogue = resolve_iva_exemption_article_catalogue(effective_date=_ON_DATE, authority=operation)
    numbered = [item for item in catalogue.definitions if item.token != IvaExemptionArticle("art_20_other")]
    assert numbered
    for definition in numbered:
        number = int(definition.token.value.removeprefix("art_20_uno_"))
        anchor = f"ley-37-1992:art-20-uno-{number}"
        assert anchor in definition.legal_refs, definition.token
        reference = operation.legal_reference(anchor)
        assert reference.article == f"20.Uno.{number}"
        paragraph = _art_20_uno_paragraphs(_bundled_liva_text(reference.corpus_ref))[number]
        assert all(text in paragraph for text in reference.required_text), definition.token
        assert reference.required_text[0].startswith(f"{number}.º"), definition.token
        assert f"art. 20.Uno.{number}.º" in definition.description, definition.token


def test_the_prorrata_counts_without_deduction_every_member_art_94_does_not_make_deductible(
    operation: PinnedAuthorityOperation,
) -> None:
    """LIVA art. 94.Uno.3.º alone lets an art. 20.Uno exemption deduct, and only for 16.º and 18.º.

    Those two depend on where the recipient is established, so the prorrata
    leaves them unresolved; every other numbered member is without deduction
    (art. 104.Dos.2.º counts it in the denominator only).
    """
    art_94 = _bundled_liva_text(operation.legal_reference("ley-37-1992:art-94").corpus_ref)
    conditional = re.search(r"apartado uno, números (\d+)\.º y (\d+)\.º", art_94)
    assert conditional is not None
    deductible_when_abroad = {f"art_20_uno_{number}" for number in conditional.groups()}
    exemptions = resolve_iva_exemption_article_catalogue(effective_date=_ON_DATE, authority=operation)
    numbered = {item.value for item in exemptions.all_articles} - {"art_20_other"}
    prorrata = resolve_prorrata_volume_catalogue(effective_date=_ON_DATE, authority=operation)

    assert {item.value for item in prorrata.sin_derecho_exemption_articles} == numbered - deductible_when_abroad
