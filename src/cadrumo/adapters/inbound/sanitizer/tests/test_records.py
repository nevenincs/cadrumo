"""Unit tests for :mod:`cadrumo.adapters.inbound.sanitizer._records`.

The tests focus on three load-bearing contracts:

* Strict-frozen behaviour — records reject mutation and unknown
  fields, and accept only the declared types under ``strict=True``.
* :class:`pydantic.SecretStr` repr-leak guard — the cleartext
  value of any ``real`` field must never surface through ``repr``,
  ``str``, or ``model_dump`` (with ``mode="json"`` defaults).
* Synthetic-shape validators — the per-replacement subclasses
  enforce shape on the synthetic value so a sanitised fixture
  round-trips through production validators unchanged.
"""

from __future__ import annotations

import re

import pytest
from pydantic import SecretStr, ValidationError

from .....core.identity import IdentityError
from .._records import (
    AddressReplacement,
    ArbitraryReplacement,
    CsvReplacement,
    DeterminismFlags,
    ExpedienteReplacement,
    IbanReplacement,
    ImporteReplacement,
    NameReplacement,
    NifReplacement,
    NrcReplacement,
    Replacement,
    SanitizationResult,
    SanitizationWarning,
    ScrubbedSurface,
    TokenMap,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_SHA = "0" * 64
_REAL_NIE_CANARY = "Y1234567X"
_REAL_NIF_CANARY = "99999999R"
_REAL_NAME_CANARY = "PERSONA PRUEBA UNO"
_SYNTHETIC_NIE = "Y0000001S"
_SYNTHETIC_NIF = "12345678Z"
_SYNTHETIC_NAME = "APELLIDO APELLIDO NOMBRE"

_ReplacementRecordType = type[
    NifReplacement
    | NameReplacement
    | ExpedienteReplacement
    | CsvReplacement
    | NrcReplacement
    | IbanReplacement
    | ImporteReplacement
    | ArbitraryReplacement
    | AddressReplacement
]


def _determinism_flags() -> DeterminismFlags:
    return DeterminismFlags(
        deterministic_id=True,
        static_id=False,
        object_stream_mode="preserve",
        linearize=False,
        recompress_flate=False,
        compress_streams=True,
    )


_VALID_REPLACEMENT_CASES: tuple[tuple[str, _ReplacementRecordType, str, str, str], ...] = (
    ("nif-nie", NifReplacement, _REAL_NIE_CANARY, _SYNTHETIC_NIE, "taxpayer NIE"),
    ("nif-nif", NifReplacement, _REAL_NIF_CANARY, _SYNTHETIC_NIF, "taxpayer NIF"),
    ("name", NameReplacement, _REAL_NAME_CANARY, _SYNTHETIC_NAME, "taxpayer name"),
    ("expediente", ExpedienteReplacement, "ABC2024-0042", "9999202400000001", "expediente id"),
    ("csv", CsvReplacement, "FNBB57PE9KZ5TN4R", "SANITIZED1002021", "csv"),
    ("nrc", NrcReplacement, "ABCDEFGHIJKLMNOP", "0000000000000XXXXXXXXX", "nrc"),
    ("iban", IbanReplacement, "ES7621000418401234567891", "ES8023100001180000012345", "bank account"),
    ("importe-positive", ImporteReplacement, "9.876,54", "1.000,00", "importe"),
    ("importe-negative", ImporteReplacement, "9.876,54", "-1.000,00", "importe"),
    ("arbitrary", ArbitraryReplacement, "opaque-fingerprint", "SANITIZED-OPAQUE", "ad-hoc"),
    (
        "address",
        AddressReplacement,
        "CALLE DEL SOL 12 28010 MADRID",
        "CALLE CALLE 0 0 CIUDAD (PROVINCIA)",
        "address",
    ),
)


_INVALID_REPLACEMENT_CASES: tuple[tuple[str, _ReplacementRecordType, str, str, str, str], ...] = (
    ("nif-blank", NifReplacement, _REAL_NIE_CANARY, "", "taxpayer NIE", r"at least 1 character"),
    ("arbitrary-blank", ArbitraryReplacement, "opaque", "", "ad-hoc", r"at least 1 character"),
    (
        "nif-bad-checksum",
        NifReplacement,
        _REAL_NIE_CANARY,
        "Y0000001Z",
        "taxpayer NIE",
        # The synthetic-shape validator surfaces the identity failure as a
        # localisation key on the wrapped IdentityError, not a raw English
        # literal; assert the key rather than prose so the operator-facing
        # message stays localisable.
        "errors.identity.nie_check_letter_mismatch",
    ),
    (
        "name-mixed-case",
        NameReplacement,
        _REAL_NAME_CANARY,
        "Apellido Nombre",
        "taxpayer name",
        r"synthetic name must be uppercase",
    ),
    (
        "name-digits",
        NameReplacement,
        _REAL_NAME_CANARY,
        "APELLIDO 1",
        "taxpayer name",
        r"synthetic name must not contain digits",
    ),
    (
        "expediente-punctuation",
        ExpedienteReplacement,
        "ABC2024-0042",
        "9999-2024",
        "expediente id",
        r"synthetic expediente must be alphanumeric",
    ),
    (
        "csv-short",
        CsvReplacement,
        "FNBB57PE9KZ5TN4R",
        "TOO_SHORT",
        "csv",
        r"synthetic CSV must be exactly 16 characters",
    ),
    (
        "csv-lowercase",
        CsvReplacement,
        "FNBB57PE9KZ5TN4R",
        "sanitized1002021",
        "csv",
        r"synthetic CSV must be uppercase alphanumeric",
    ),
    (
        "nrc-too-long",
        NrcReplacement,
        "ABCDEFGHIJKLMNOP",
        "X" * 64,
        "nrc",
        r"synthetic NRC must be 16-32 characters",
    ),
    (
        "iban-bad-checksum",
        IbanReplacement,
        "ES7621000418401234567891",
        "ES0000000000000000000000",
        "bank account",
        r"synthetic IBAN fails the ISO 13616 mod-97 check",
    ),
    (
        "importe-dot-decimal",
        ImporteReplacement,
        "9.876,54",
        "1000.00",
        "importe",
        r"synthetic IMPORTE must contain a decimal comma",
    ),
    (
        "importe-one-decimal-digit",
        ImporteReplacement,
        "9.876,54",
        "1.000,5",
        "importe",
        r"synthetic IMPORTE must end with two decimal digits",
    ),
)


def test_replacement_subclasses_accept_valid_synthetic_values() -> None:
    for case_id, replacement_cls, real, synthetic, surface_label in _VALID_REPLACEMENT_CASES:
        replacement = replacement_cls(
            real=SecretStr(real),
            synthetic=synthetic,
            surface_label=surface_label,
        )
        assert replacement.synthetic == synthetic, case_id
        assert replacement.real.get_secret_value() == real, case_id


def test_replacement_subclasses_reject_invalid_synthetic_values() -> None:
    for case_id, replacement_cls, real, synthetic, surface_label, expected_message in _INVALID_REPLACEMENT_CASES:
        with pytest.raises(ValidationError) as exc_info:
            replacement_cls(
                real=SecretStr(real),
                synthetic=synthetic,
                surface_label=surface_label,
            )
        errors = exc_info.value.errors()
        assert errors, case_id
        if expected_message.startswith("errors.identity."):
            wrapped = errors[0]["ctx"]["error"]
            assert isinstance(wrapped, IdentityError), case_id
            assert wrapped.translated_message == expected_message, case_id
        else:
            assert re.search(expected_message, str(exc_info.value)), case_id


class TestTokenMapShape:
    """TokenMap is strict-frozen and supports empty construction."""

    def test_default_construction_is_empty_and_categories_default_to_empty_tuples(self) -> None:
        mapping = TokenMap()
        assert mapping.is_empty()
        for category in ("nif", "name", "address", "expediente", "csv", "nrc", "iban", "importe", "arbitrary"):
            assert getattr(mapping, category) == (), category

    def test_frozen_rejects_mutation(self) -> None:
        mapping = TokenMap()
        with pytest.raises(ValidationError, match=r"frozen"):
            # `frozen=True` causes pydantic to reject this assignment;
            # `setattr` is a generic attribute write so the static type
            # checker does not flag the read-only field.
            attr = "nif"
            setattr(mapping, attr, ())

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            TokenMap.model_validate({"unknown_field": "x"})

    def test_is_empty_returns_false_when_any_category_populated(self) -> None:
        mapping = TokenMap(
            arbitrary=(
                ArbitraryReplacement(
                    real=SecretStr("opaque"),
                    synthetic="X",
                    surface_label="ad-hoc",
                ),
            ),
        )
        assert not mapping.is_empty()


class TestSecretStrRepr:
    """The cleartext ``real`` value must NOT surface through repr/str/dump."""

    _CLEARTEXT_NIF = _REAL_NIE_CANARY
    _CLEARTEXT_NAME = _REAL_NAME_CANARY

    def test_cleartext_real_values_do_not_leak_through_renderings(self) -> None:
        nif_record = NifReplacement(
            real=SecretStr(self._CLEARTEXT_NIF),
            synthetic=_SYNTHETIC_NIE,
            surface_label="taxpayer NIE",
        )
        name_record = NameReplacement(
            real=SecretStr(self._CLEARTEXT_NAME),
            synthetic=_SYNTHETIC_NAME,
            surface_label="taxpayer name",
        )
        mapping = TokenMap(
            nif=(nif_record,),
            name=(name_record,),
        )

        renderings = (
            repr(nif_record),
            str(name_record),
            # mode="python" default returns SecretStr objects, not raw values.
            str(nif_record.model_dump()),
            str(nif_record.model_dump(mode="json")),
            nif_record.model_dump_json(),
            repr(mapping),
        )
        for rendering in renderings:
            assert self._CLEARTEXT_NIF not in rendering
            assert self._CLEARTEXT_NAME not in rendering


class TestReplacementShape:
    """Replacement audit row records hashes, never cleartext."""

    def test_accepts_canonical_row(self) -> None:
        record = Replacement(
            surface="content_stream",
            surface_index=(2, 17),
            real_sha256=_SHA,
            synthetic="Y0000001S",
            encoding="literal",
        )
        assert record.surface == "content_stream"

    def test_rejects_invalid_sha(self) -> None:
        with pytest.raises(ValidationError, match=r"real_sha256"):
            Replacement(
                surface="content_stream",
                surface_index=(0,),
                real_sha256="not-a-hash",
                synthetic="X",
                encoding="literal",
            )

    def test_rejects_unknown_enum_fields(self) -> None:
        payloads: tuple[tuple[str, dict[str, object]], ...] = (
            (
                "surface",
                {
                    "surface": "unknown_surface_kind",
                    "surface_index": (0,),
                    "real_sha256": _SHA,
                    "synthetic": "X",
                    "encoding": "literal",
                },
            ),
            (
                "encoding",
                {
                    "surface": "content_stream",
                    "surface_index": (0,),
                    "real_sha256": _SHA,
                    "synthetic": "X",
                    "encoding": "bogus",
                },
            ),
        )
        for case_id, payload in payloads:
            try:
                with pytest.raises(ValidationError, match=r"Input should be"):
                    Replacement.model_validate(payload)
            except AssertionError as exc:
                raise AssertionError(f"unknown enum payload was accepted: {case_id}") from exc


class TestScrubbedSurfaceShape:
    """ScrubbedSurface records non-negative counts."""

    def test_accepts_zero_count(self) -> None:
        record = ScrubbedSurface(surface="attachments", count=0)
        assert record.count == 0

    def test_rejects_negative_count(self) -> None:
        negative: int = -1
        with pytest.raises(ValidationError, match=r"greater than or equal to 0"):
            ScrubbedSurface(surface="attachments", count=negative)


class TestSanitizationWarningShape:
    """SanitizationWarning enforces the closed warning-code set."""

    def test_accepts_known_code(self) -> None:
        record = SanitizationWarning(
            code="structtree_dropped_lossy",
            detail="Dropped /StructTreeRoot defensively.",
        )
        assert record.code == "structtree_dropped_lossy"

    def test_rejects_unknown_code(self) -> None:
        with pytest.raises(ValidationError, match=r"Input should be"):
            SanitizationWarning.model_validate(
                {"code": "unknown_warning_kind", "detail": "—"},
            )


class TestDeterminismFlagsShape:
    """DeterminismFlags exposes the captured save-flag set."""

    def test_accepts_canonical_flags(self) -> None:
        flags = _determinism_flags()
        assert flags.object_stream_mode == "preserve"

    def test_rejects_unknown_object_stream_mode(self) -> None:
        with pytest.raises(ValidationError, match=r"Input should be"):
            DeterminismFlags.model_validate(
                {
                    "deterministic_id": True,
                    "static_id": False,
                    "object_stream_mode": "rebuild",
                    "linearize": False,
                    "recompress_flate": False,
                    "compress_streams": True,
                },
            )


class TestSanitizationResultShape:
    """SanitizationResult assembles the typed outcome of a sanitisation run."""

    def test_accepts_canonical_result(self) -> None:
        flags = _determinism_flags()
        result = SanitizationResult(
            output_bytes=b"%PDF-1.4\n",
            source_sha256="a" * 64,
            output_sha256="b" * 64,
            source_size_bytes=10,
            output_size_bytes=10,
            sanitizer_version="0.1.0",
            determinism_flags=flags,
            replacements_applied=(),
            surfaces_scrubbed=(),
            warnings=(),
        )
        assert result.sanitizer_version == "0.1.0"

    def test_rejects_invalid_source_sha(self) -> None:
        flags = _determinism_flags()
        with pytest.raises(ValidationError, match=r"source_sha256"):
            SanitizationResult(
                output_bytes=b"%PDF-1.4\n",
                source_sha256="not-a-hash",
                output_sha256="b" * 64,
                source_size_bytes=10,
                output_size_bytes=10,
                sanitizer_version="0.1.0",
                determinism_flags=flags,
                replacements_applied=(),
                surfaces_scrubbed=(),
                warnings=(),
            )

    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            SanitizationResult.model_validate(
                {
                    "output_bytes": b"%PDF-1.4\n",
                    "source_sha256": "a" * 64,
                    "output_sha256": "b" * 64,
                    "source_size_bytes": 10,
                    "output_size_bytes": 10,
                    "sanitizer_version": "0.1.0",
                    "determinism_flags": {
                        "deterministic_id": True,
                        "static_id": False,
                        "object_stream_mode": "preserve",
                        "linearize": False,
                        "recompress_flate": False,
                        "compress_streams": True,
                    },
                    "replacements_applied": (),
                    "surfaces_scrubbed": (),
                    "warnings": (),
                    "bonus_field": "x",
                },
            )
