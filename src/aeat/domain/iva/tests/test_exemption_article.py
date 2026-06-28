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

from .. import IvaCategory, IvaClassificationResult, IvaExemptionArticle

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
        matched_rule_id="R20_uno_26_artistic_services",
        exemption_article=IvaExemptionArticle.ART_20_UNO_26,
    )

    assert result.exemption_article is IvaExemptionArticle.ART_20_UNO_26


@pytest.mark.parametrize(
    "non_exempt_category",
    [
        IvaCategory.DOMESTIC_GENERAL_21,
        IvaCategory.DOMESTIC_REDUCED_10,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.OPERACION_NO_SUJETA,
    ],
)
def test_classification_result_rejects_exemption_article_on_non_exempt_category(
    non_exempt_category: IvaCategory,
) -> None:
    """The validator rejects a discriminator paired with any non-DOMESTIC_EXEMPT category."""
    # Pydantic v2 wraps validator-raised exceptions in ValidationError;
    # the inner IvaValidationError message reaches the rendered output.
    with pytest.raises(ValidationError) as exc:
        IvaClassificationResult(
            category=non_exempt_category,
            matched_rule_id="R_test",
            exemption_article=IvaExemptionArticle.ART_20_UNO_8,
        )

    message = str(exc.value)
    assert "exemption_article" in message
    assert "DOMESTIC_EXEMPT" in message
    assert non_exempt_category.value in message


def test_exemption_article_enum_membership_matches_baseline_set() -> None:
    """The closed enum carries exactly the four MVP slots named in the baseline contract.

    Authority: ``iva-exemption-article-design`` Implementation
    section locks the initial set as ART_20_UNO_8 / ART_20_UNO_14 /
    ART_20_UNO_26 / ART_20_OTHER. This test fires when a new value is
    added without a contract update.
    """
    expected = {
        IvaExemptionArticle.ART_20_UNO_8.value,
        IvaExemptionArticle.ART_20_UNO_14.value,
        IvaExemptionArticle.ART_20_UNO_26.value,
        IvaExemptionArticle.ART_20_OTHER.value,
    }
    actual = {member.value for member in IvaExemptionArticle}
    assert actual == expected
