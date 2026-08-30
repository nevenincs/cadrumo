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

import pytest
from pydantic import ValidationError

from ..classification import IvaClassificationResult
from ..schema import IvaCategory, IvaExemptionArticle

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_classification_result_accepts_no_exemption_article_by_default() -> None:
    """The discriminator is optional; absence is the canonical default."""
    result = IvaClassificationResult(
        category=IvaCategory.DOMESTIC_EXEMPT,
        matched_rule_id="R04_immovable_property_exempt",
    )

    assert result.exemption_article is None


def test_classification_result_stamps_exemption_article_when_domestic_exempt() -> None:
    """Stamping the discriminator on a DOMESTIC_EXEMPT result is accepted."""
    result = IvaClassificationResult(
        category=IvaCategory.DOMESTIC_EXEMPT,
        matched_rule_id="R20_uno_8_education",
        exemption_article=IvaExemptionArticle.ART_20_UNO_8,
    )

    assert result.exemption_article is IvaExemptionArticle.ART_20_UNO_8


def test_classification_result_rejects_exemption_article_on_non_exempt_category() -> None:
    """The validator rejects a discriminator paired with any non-DOMESTIC_EXEMPT category."""
    # Pydantic v2 wraps validator-raised exceptions in ValidationError;
    # the inner IvaValidationError message reaches the rendered output.
    for non_exempt_category in (
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.DOMESTIC_REDUCED,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        IvaCategory.OPERACION_NO_SUJETA,
    ):
        with pytest.raises(ValidationError) as exc:
            IvaClassificationResult(
                category=non_exempt_category,
                matched_rule_id="R_test",
                exemption_article=IvaExemptionArticle.ART_20_UNO_8,
            )

        message = str(exc.value)
        assert "exemption_article" in message, non_exempt_category
        assert "DOMESTIC_EXEMPT" in message, non_exempt_category
        assert non_exempt_category.value in message


def test_exemption_article_enum_membership_matches_accepted_correction() -> None:
    """The closed enum carries only the accepted generic-exemption slots.

    This test fails when the removed Article 20.Uno.26 route is
    reintroduced without an approved contract change.
    """
    expected = {
        IvaExemptionArticle.ART_20_UNO_8.value,
        IvaExemptionArticle.ART_20_UNO_14.value,
        IvaExemptionArticle.ART_20_OTHER.value,
    }
    actual = {member.value for member in IvaExemptionArticle}
    assert actual == expected
