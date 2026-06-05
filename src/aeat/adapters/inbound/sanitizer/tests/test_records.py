"""Unit tests for :mod:`aeat.adapters.inbound.sanitizer._records`.

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

import pytest
from pydantic import SecretStr, ValidationError

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


class TestNifReplacement:
    """Synthetic NIF/NIE values must pass the AEAT checksum."""

    def test_accepts_valid_synthetic_nie(self) -> None:
        replacement = NifReplacement(
            real=SecretStr(_REAL_NIE_CANARY),
            synthetic=_SYNTHETIC_NIE,
            surface_label="taxpayer NIE",
        )
        # A silent-acceptance regression would still match "no exception
        # raised"; pinning the synthetic and real fields catches a
        # validator that wrongly normalises (trim, lowercase) the input.
        assert replacement.synthetic == _SYNTHETIC_NIE
        assert replacement.real.get_secret_value() == _REAL_NIE_CANARY

    def test_accepts_valid_synthetic_nif(self) -> None:
        # 12345678 % 23 == 14 → letter Z
        replacement = NifReplacement(
            real=SecretStr(_REAL_NIF_CANARY),
            synthetic=_SYNTHETIC_NIF,
            surface_label="taxpayer NIF",
        )
        assert replacement.synthetic == _SYNTHETIC_NIF
        assert replacement.real.get_secret_value() == _REAL_NIF_CANARY

    def test_rejects_synthetic_with_bad_checksum(self) -> None:
        # IdentityError now inherits from ValueError so pydantic wraps
        # it as ValidationError at the @field_validator boundary. The
        # original IdentityError message is preserved in the wrapped
        # error's text.
        with pytest.raises(ValidationError, match=r"NIE checksum letter is invalid"):
            NifReplacement(
                real=SecretStr(_REAL_NIE_CANARY),
                synthetic="Y0000001Z",  # wrong checksum letter
                surface_label="taxpayer NIE",
            )

    def test_rejects_blank_synthetic(self) -> None:
        # Blank synthetic is rejected by the _NonEmptyStr field-type
        # constraint (min_length=1) BEFORE the custom field_validator
        # runs — pydantic surfaces this through ValidationError.
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            NifReplacement(
                real=SecretStr(_REAL_NIE_CANARY),
                synthetic="",
                surface_label="taxpayer NIE",
            )


class TestNameReplacement:
    """Synthetic names must be uppercase and digit-free."""

    def test_accepts_uppercased_name(self) -> None:
        replacement = NameReplacement(
            real=SecretStr(_REAL_NAME_CANARY),
            synthetic=_SYNTHETIC_NAME,
            surface_label="taxpayer name",
        )
        assert replacement.synthetic == _SYNTHETIC_NAME

    def test_rejects_mixed_case(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic name must be uppercase"):
            NameReplacement(
                real=SecretStr(_REAL_NAME_CANARY),
                synthetic="Apellido Nombre",
                surface_label="taxpayer name",
            )

    def test_rejects_digits(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic name must not contain digits"):
            NameReplacement(
                real=SecretStr(_REAL_NAME_CANARY),
                synthetic="APELLIDO 1",
                surface_label="taxpayer name",
            )


class TestExpedienteReplacement:
    """Expediente synthetic must be alphanumeric and length-bounded."""

    def test_accepts_alphanumeric(self) -> None:
        replacement = ExpedienteReplacement(
            real=SecretStr("ABC2024-0042"),
            synthetic="9999202400000001",
            surface_label="expediente id",
        )
        assert replacement.synthetic == "9999202400000001"

    def test_rejects_with_punctuation(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic expediente must be alphanumeric"):
            ExpedienteReplacement(
                real=SecretStr("ABC2024-0042"),
                synthetic="9999-2024",
                surface_label="expediente id",
            )


class TestCsvReplacement:
    """Synthetic CSV must be exactly 16 chars uppercase alphanumeric."""

    def test_accepts_canonical_shape(self) -> None:
        replacement = CsvReplacement(
            real=SecretStr("FNBB57PE9KZ5TN4R"),
            synthetic="SANITIZED1002021",
            surface_label="csv",
        )
        assert replacement.synthetic == "SANITIZED1002021"
        assert len(replacement.synthetic) == 16

    def test_rejects_short(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic CSV must be exactly 16 characters"):
            CsvReplacement(
                real=SecretStr("FNBB57PE9KZ5TN4R"),
                synthetic="TOO_SHORT",
                surface_label="csv",
            )

    def test_rejects_lowercase(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic CSV must be uppercase alphanumeric"):
            CsvReplacement(
                real=SecretStr("FNBB57PE9KZ5TN4R"),
                synthetic="sanitized1002021",
                surface_label="csv",
            )


class TestNrcReplacement:
    """NRC synthetic must be 16-32 alphanumeric."""

    def test_accepts_pad_pattern(self) -> None:
        replacement = NrcReplacement(
            real=SecretStr("ABCDEFGHIJKLMNOP"),
            synthetic="0000000000000XXXXXXXXX",
            surface_label="nrc",
        )
        assert replacement.synthetic == "0000000000000XXXXXXXXX"
        assert 16 <= len(replacement.synthetic) <= 32

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic NRC must be 16-32 characters"):
            NrcReplacement(
                real=SecretStr("ABCDEFGHIJKLMNOP"),
                synthetic="X" * 64,
                surface_label="nrc",
            )


class TestIbanReplacement:
    """IBAN synthetic must pass ISO 13616 mod-97."""

    def test_accepts_valid_es_iban(self) -> None:
        # ES80 2310 0001 1800 0001 2345 — known-valid mod-97 sample.
        replacement = IbanReplacement(
            real=SecretStr("ES7621000418401234567891"),
            synthetic="ES8023100001180000012345",
            surface_label="bank account",
        )
        assert replacement.synthetic == "ES8023100001180000012345"
        assert replacement.synthetic.startswith("ES")

    def test_rejects_bad_checksum(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic IBAN fails the ISO 13616 mod-97 check"):
            IbanReplacement(
                real=SecretStr("ES7621000418401234567891"),
                synthetic="ES0000000000000000000000",
                surface_label="bank account",
            )


class TestImporteReplacement:
    """Synthetic IMPORTE must follow AEAT comma-decimal shape."""

    def test_accepts_thousands_dotted(self) -> None:
        replacement = ImporteReplacement(
            real=SecretStr("9.876,54"),
            synthetic="1.000,00",
            surface_label="importe",
        )
        assert replacement.synthetic == "1.000,00"
        assert "," in replacement.synthetic, "AEAT comma-decimal shape must be preserved"

    def test_accepts_negative(self) -> None:
        replacement = ImporteReplacement(
            real=SecretStr("9.876,54"),
            synthetic="-1.000,00",
            surface_label="importe",
        )
        assert replacement.synthetic == "-1.000,00"
        assert replacement.synthetic.startswith("-")

    def test_rejects_dot_decimal(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic IMPORTE must contain a decimal comma"):
            ImporteReplacement(
                real=SecretStr("9.876,54"),
                synthetic="1000.00",
                surface_label="importe",
            )

    def test_rejects_one_decimal_digit(self) -> None:
        with pytest.raises(ValidationError, match=r"synthetic IMPORTE must end with two decimal digits"):
            ImporteReplacement(
                real=SecretStr("9.876,54"),
                synthetic="1.000,5",
                surface_label="importe",
            )


class TestArbitraryReplacement:
    """Arbitrary entries pass through any non-empty synthetic."""

    def test_accepts_any_non_empty(self) -> None:
        replacement = ArbitraryReplacement(
            real=SecretStr("opaque-fingerprint"),
            synthetic="SANITIZED-OPAQUE",
            surface_label="ad-hoc",
        )
        assert replacement.synthetic == "SANITIZED-OPAQUE"
        assert replacement.synthetic, "non-empty synthetic must survive validation"

    def test_rejects_blank(self) -> None:
        # Same _NonEmptyStr field-type constraint as NifReplacement —
        # pydantic rejects min_length violation with the stock message.
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            ArbitraryReplacement(
                real=SecretStr("opaque"),
                synthetic="",
                surface_label="ad-hoc",
            )


class TestAddressReplacement:
    """Address replacement has no shape constraint beyond non-empty."""

    def test_accepts_canonical_synthetic(self) -> None:
        replacement = AddressReplacement(
            real=SecretStr("CALLE DEL SOL 12 28010 MADRID"),
            synthetic="CALLE CALLE 0 0 CIUDAD (PROVINCIA)",
            surface_label="address",
        )
        assert replacement.synthetic == "CALLE CALLE 0 0 CIUDAD (PROVINCIA)"
        assert replacement.real.get_secret_value() == "CALLE DEL SOL 12 28010 MADRID"


class TestTokenMapShape:
    """TokenMap is strict-frozen and supports empty construction."""

    def test_default_construction_is_empty(self) -> None:
        mapping = TokenMap()
        assert mapping.is_empty()

    def test_categories_default_to_empty_tuples(self) -> None:
        mapping = TokenMap()
        assert mapping.nif == ()
        assert mapping.name == ()
        assert mapping.address == ()
        assert mapping.expediente == ()
        assert mapping.csv == ()
        assert mapping.nrc == ()
        assert mapping.iban == ()
        assert mapping.importe == ()
        assert mapping.arbitrary == ()

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

    def test_repr_does_not_leak_cleartext_nif(self) -> None:
        record = NifReplacement(
            real=SecretStr(self._CLEARTEXT_NIF),
            synthetic=_SYNTHETIC_NIE,
            surface_label="taxpayer NIE",
        )
        rendering = repr(record)
        assert self._CLEARTEXT_NIF not in rendering

    def test_str_does_not_leak_cleartext_name(self) -> None:
        record = NameReplacement(
            real=SecretStr(self._CLEARTEXT_NAME),
            synthetic=_SYNTHETIC_NAME,
            surface_label="taxpayer name",
        )
        assert self._CLEARTEXT_NAME not in str(record)

    def test_model_dump_default_does_not_leak_cleartext(self) -> None:
        record = NifReplacement(
            real=SecretStr(self._CLEARTEXT_NIF),
            synthetic=_SYNTHETIC_NIE,
            surface_label="taxpayer NIE",
        )
        # mode="python" default returns SecretStr objects, not raw values.
        # Their str()/repr() do not include the cleartext.
        dumped = record.model_dump()
        assert self._CLEARTEXT_NIF not in str(dumped)

    def test_model_dump_json_does_not_leak_cleartext(self) -> None:
        # The CLI sidecar (`aeat sanitize pdf --report`) calls
        # ``model_dump(mode="json")`` on the SanitizationResult,
        # which transitively serialises every Replacement (NEVER
        # the TokenMap) — but a future caller that sidecars the
        # mapping would hit this code path. Verify both ``mode=
        # "json"`` and ``model_dump_json`` mask the cleartext.
        record = NifReplacement(
            real=SecretStr(self._CLEARTEXT_NIF),
            synthetic=_SYNTHETIC_NIE,
            surface_label="taxpayer NIE",
        )
        json_dump = record.model_dump(mode="json")
        json_str = record.model_dump_json()
        assert self._CLEARTEXT_NIF not in str(json_dump)
        assert self._CLEARTEXT_NIF not in json_str

    def test_token_map_repr_does_not_leak_any_real_value(self) -> None:
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(self._CLEARTEXT_NIF),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
            name=(
                NameReplacement(
                    real=SecretStr(self._CLEARTEXT_NAME),
                    synthetic=_SYNTHETIC_NAME,
                    surface_label="taxpayer name",
                ),
            ),
        )
        rendering = repr(mapping)
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

    def test_rejects_unknown_surface(self) -> None:
        with pytest.raises(ValidationError, match=r"Input should be"):
            Replacement.model_validate(
                {
                    "surface": "unknown_surface_kind",
                    "surface_index": (0,),
                    "real_sha256": _SHA,
                    "synthetic": "X",
                    "encoding": "literal",
                },
            )

    def test_rejects_unknown_encoding(self) -> None:
        with pytest.raises(ValidationError, match=r"Input should be"):
            Replacement.model_validate(
                {
                    "surface": "content_stream",
                    "surface_index": (0,),
                    "real_sha256": _SHA,
                    "synthetic": "X",
                    "encoding": "bogus",
                },
            )


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
        flags = DeterminismFlags(
            deterministic_id=True,
            static_id=False,
            object_stream_mode="preserve",
            linearize=False,
            recompress_flate=False,
            compress_streams=True,
        )
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
        flags = DeterminismFlags(
            deterministic_id=True,
            static_id=False,
            object_stream_mode="preserve",
            linearize=False,
            recompress_flate=False,
            compress_streams=True,
        )
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
        flags = DeterminismFlags(
            deterministic_id=True,
            static_id=False,
            object_stream_mode="preserve",
            linearize=False,
            recompress_flate=False,
            compress_streams=True,
        )
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
