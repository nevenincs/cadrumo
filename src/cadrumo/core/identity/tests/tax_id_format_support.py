"""Test-only Spanish tax-ID format declarations for the pure core kernel."""

from ..documents import SpanishTaxIdFormat

SPANISH_TAX_ID_FORMAT = SpanishTaxIdFormat(
    width=9,
    country_prefix="ES",
    country_prefixed_width=11,
    country_prefix_strip_width=2,
    prefixed_nif_leaders="KLM",
    nie_leaders="XYZ",
    cif_leaders="ABCDEFGHJNPQRSUVW",
    nif_letters="TRWAGMYFPDXBNJZSQVHLCKE",
    nie_prefix_substitutions=(("X", "0"), ("Y", "1"), ("Z", "2")),
    cif_digit_only_kinds="ABEH",
    cif_letter_only_kinds="PQRSNW",
    cif_letter_table="JABCDEFGHI",
)
