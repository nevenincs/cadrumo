"""Strict pydantic v2 records for the :mod:`dev.sanitizer` subpackage.

Every record in this module is `frozen`, `extra="forbid"`,
`strict=True`. Cleartext PII lives exclusively in
:class:`pydantic.SecretStr` fields so accidental ``repr`` / log
inclusion does not leak the source value. Synthetic replacements
are validated against the same checksum / shape rules the project
applies to live values, so a sanitised fixture round-trips through
production parsers unchanged.

``SecretStr`` is a display/logging guard, not a storage policy. Operator
mapping files that contain real values must remain outside git; committed audit
records should contain only synthetic values, hashes, surface names, and counts.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.identity import validate_spanish_tax_id

from .errors import SanitizerValidationError

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _validate_iban_shape(value: str) -> str:
    """Validate a synthetic IBAN against ISO 13616 mod-97 + ES-prefix shape.

    Args:
        value: The synthetic IBAN string supplied by the operator.

    Returns:
        The uppercased input.

    Raises:
        SanitizerValidationError: If the input is not a 24-character ES-prefixed
            string whose mod-97 check fails.
    """
    candidate = value.replace(" ", "").upper()
    if len(candidate) != 24 or not candidate.startswith("ES"):
        raise SanitizerValidationError("synthetic IBAN must be 24 characters and start with 'ES'")
    rearranged = candidate[4:] + candidate[:4]
    numeric: list[str] = []
    for character in rearranged:
        if character.isdigit():
            numeric.append(character)
        elif character.isalpha():
            numeric.append(str(ord(character) - 55))
        else:
            raise SanitizerValidationError("synthetic IBAN contains non-alphanumeric characters")
    if int("".join(numeric)) % 97 != 1:
        raise SanitizerValidationError("synthetic IBAN fails the ISO 13616 mod-97 check")
    return candidate


def _validate_amount_shape(value: str) -> str:
    """Validate a synthetic IMPORTE in AEAT comma-decimal shape.

    Args:
        value: The synthetic amount string (e.g. ``"1.000,00"``).

    Returns:
        The input verbatim.

    Raises:
        SanitizerValidationError: If the string is not the AEAT
            ``<thousands>,<cents>`` shape.
    """
    if "," not in value:
        raise SanitizerValidationError("synthetic IMPORTE must contain a decimal comma")
    integer_part, decimal_part = value.rsplit(",", 1)
    if len(decimal_part) != 2 or not decimal_part.isdigit():
        raise SanitizerValidationError("synthetic IMPORTE must end with two decimal digits")
    integer_clean = integer_part.replace(".", "").lstrip("-")
    if not integer_clean or not integer_clean.isdigit():
        raise SanitizerValidationError("synthetic IMPORTE integer part must be digits with optional thousands dots")
    return value


_NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=False)]


class _ReplacementBase(BaseModel):
    """Base record for one cleartext-to-synthetic mapping entry.

    Attributes:
        real: The cleartext PII value to match against PDF
            content. Stored as :class:`SecretStr` so accidental
            ``repr`` does not leak it.
        synthetic: The synthetic replacement text that will appear
            in the sanitised output. Logged in cleartext (that's
            the point — the replacement is the visible artefact).
        surface_label: Human-readable label used in the audit
            record (``"taxpayer name"``, ``"NIE"``, ...).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    real: SecretStr
    synthetic: _NonEmptyStr
    surface_label: _NonEmptyStr


class NifReplacement(_ReplacementBase):
    """Replacement entry whose synthetic value must be a valid NIF/NIE."""

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_nif(cls, value: str) -> str:
        return validate_spanish_tax_id(value)


class NameReplacement(_ReplacementBase):
    """Replacement entry for a taxpayer or representative name.

    The synthetic value is constrained to a non-blank uppercased
    string so it round-trips through parsers that expect AEAT's
    ``APELLIDO APELLIDO NOMBRE`` shape.
    """

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_name(cls, value: str) -> str:
        if value != value.upper():
            raise SanitizerValidationError("synthetic name must be uppercase")
        if any(character.isdigit() for character in value):
            raise SanitizerValidationError("synthetic name must not contain digits")
        return value


class AddressReplacement(_ReplacementBase):
    """Replacement entry for a postal address."""


class ExpedienteReplacement(_ReplacementBase):
    """Replacement entry for an AEAT expediente identifier.

    AEAT expedientes are typically opaque 13-19 character
    alphanumeric strings; the synthetic value preserves the
    same length window so width-sensitive layout cues survive.
    """

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_expediente(cls, value: str) -> str:
        if not (4 <= len(value) <= 32):
            raise SanitizerValidationError("synthetic expediente must be 4-32 characters")
        if not value.isalnum():
            raise SanitizerValidationError("synthetic expediente must be alphanumeric")
        return value


class CsvReplacement(_ReplacementBase):
    """Replacement entry for an AEAT Código Seguro de Verificación.

    AEAT CSVs are 16-character base32-like strings. The synthetic
    value preserves the length so downstream parsers that match on
    length-bounded patterns continue to match.
    """

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_csv(cls, value: str) -> str:
        if len(value) != 16:
            raise SanitizerValidationError("synthetic CSV must be exactly 16 characters")
        if not value.isalnum() or value != value.upper():
            raise SanitizerValidationError("synthetic CSV must be uppercase alphanumeric")
        return value


class NrcReplacement(_ReplacementBase):
    """Replacement entry for an AEAT Número de Referencia Completo."""

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_nrc(cls, value: str) -> str:
        if not (16 <= len(value) <= 32):
            raise SanitizerValidationError("synthetic NRC must be 16-32 characters")
        if not value.isalnum():
            raise SanitizerValidationError("synthetic NRC must be alphanumeric")
        return value


class IbanReplacement(_ReplacementBase):
    """Replacement entry for an IBAN (ES- prefixed)."""

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_iban(cls, value: str) -> str:
        return _validate_iban_shape(value)


class ImporteReplacement(_ReplacementBase):
    """Replacement entry for a monetary amount in AEAT comma-decimal shape."""

    @field_validator("synthetic")
    @classmethod
    def _validate_synthetic_amount(cls, value: str) -> str:
        return _validate_amount_shape(value)


class ArbitraryReplacement(_ReplacementBase):
    """Replacement entry with no shape constraint.

    Use sparingly — every arbitrary entry bypasses checksum and
    layout validation, so a poorly chosen synthetic can break a
    deep-extractor regression. Reserve for ad-hoc strings such as
    capture-time fingerprints or one-off identifiers.
    """


class TokenMap(BaseModel):
    """Declarative input mapping for :func:`sanitize_pdf`.

    Each tuple holds zero-or-more replacement records of the
    matching category. Empty tuples are permitted; a TokenMap with
    every category empty is structurally valid but produces a
    no-replacement sanitisation (the metadata + dynamic-surface
    scrub still runs). The real values inside replacement entries are the
    operator-supplied authority for the rewrite; the sanitizer does not run
    probabilistic PII discovery.

    Attributes:
        nif: Replacements for NIF / NIE values.
        name: Replacements for taxpayer / representative names.
        address: Replacements for postal addresses.
        expediente: Replacements for AEAT expediente identifiers.
        csv: Replacements for Código Seguro de Verificación strings.
        nrc: Replacements for Número de Referencia Completo strings.
        iban: Replacements for ES-prefixed IBANs.
        importe: Replacements for AEAT comma-decimal monetary amounts.
        arbitrary: Replacements without shape constraints.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    nif: tuple[NifReplacement, ...] = ()
    name: tuple[NameReplacement, ...] = ()
    address: tuple[AddressReplacement, ...] = ()
    expediente: tuple[ExpedienteReplacement, ...] = ()
    csv: tuple[CsvReplacement, ...] = ()
    nrc: tuple[NrcReplacement, ...] = ()
    iban: tuple[IbanReplacement, ...] = ()
    importe: tuple[ImporteReplacement, ...] = ()
    arbitrary: tuple[ArbitraryReplacement, ...] = ()

    def is_empty(self) -> bool:
        """Returns True when no replacement of any category is set."""
        return not (
            self.nif
            or self.name
            or self.address
            or self.expediente
            or self.csv
            or self.nrc
            or self.iban
            or self.importe
            or self.arbitrary
        )


_SurfaceName = Literal[
    "docinfo_title",
    "docinfo_subject",
    "docinfo_author",
    "docinfo_keywords",
    "docinfo_creator",
    "docinfo_producer",
    "docinfo_creation_date",
    "docinfo_mod_date",
    "docinfo_other",
    "xmp_packet",
    "xmp_dc_title",
    "xmp_dc_description",
    "xmp_dc_creator",
    "xmp_pdf_keywords",
    "xmp_pdfa_claim",
    "content_stream",
    "annotation_contents",
    "annotation_drop",
    "structtree_actualtext",
    "structtree_alt",
    "structtree_dropped",
    "attachments",
    "javascript",
    "open_action",
    "additional_actions",
    "optional_content_groups",
    "acroform_field_value",
    "acroform_dropped",
    "page_thumbnail",
    "outlines",
    "page_labels",
    "incremental_update_history",
]


_EncodingName = Literal[
    "literal",
    "hex",
    "actualtext",
    "docinfo_string",
    "xmp_string",
]


_WarningCode = Literal[
    "unknown_surface_present",
    "encoding_inferred",
    "structtree_dropped_lossy",
    "pdfa_claim_invalidated",
    "digital_signature_present_refusing",
    "incremental_update_history_consolidated",
    "source_sha256_already_in_known_sanitized_set",
    "missing_replacement_target",
]


class Replacement(BaseModel):
    """One token-replace edit recorded in :attr:`SanitizationResult.replacements_applied`.

    Attributes:
        surface: Closed-set surface name (DocInfo key, content-
            stream, structtree text, ...).
        surface_index: Tuple-encoded location within the surface.
            For content streams, ``(page_index, instruction_index)``.
        real_sha256: SHA-256 of the cleartext PII the entry
            matched against. **Never** the cleartext itself —
            committing the cleartext into ``replacements_applied``
            would defeat the entire sanitiser. Treat this hash as
            fixture-review metadata, not as a production de-identification key.
        synthetic: The synthetic replacement text that landed in
            the output. Safe to log.
        encoding: Encoding form in which the operand was rewritten
            (literal string, hex string, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    surface: _SurfaceName
    surface_index: tuple[int, ...]
    real_sha256: str = Field(..., pattern=_SHA256_PATTERN)
    synthetic: _NonEmptyStr
    encoding: _EncodingName


class ScrubbedSurface(BaseModel):
    """Counter for one PII surface that was wiped (vs. token-replaced).

    Attributes:
        surface: Closed-set surface name.
        count: Number of items removed (0 when the surface was
            absent in the source — recorded so callers can audit
            the sanitiser's coverage).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    surface: _SurfaceName
    count: int = Field(..., ge=0)


class SanitizationWarning(BaseModel):
    """One non-fatal warning emitted during sanitisation.

    Attributes:
        code: Closed-set warning identifier.
        detail: Free-form detail string. Must NOT contain
            cleartext PII; the caller is responsible for
            constructing a PII-safe detail.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    code: _WarningCode
    detail: _NonEmptyStr


class DeterminismFlags(BaseModel):
    """Captured save-flag set used to produce byte-stable output.

    Attributes:
        deterministic_id: Whether ``deterministic_id`` was passed
            (true in normal operation).
        static_id: Debug-only ``static_id`` flag (false in normal
            operation).
        object_stream_mode: One of ``"preserve"``, ``"generate"``,
            or ``"disable"``.
        linearize: Whether linearisation was requested.
        recompress_flate: Whether flate streams were recompressed.
        compress_streams: Whether streams were compressed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    deterministic_id: bool
    static_id: bool
    object_stream_mode: Literal["preserve", "generate", "disable"]
    linearize: bool
    recompress_flate: bool
    compress_streams: bool


class SanitizationResult(BaseModel):
    """Outcome of a successful :func:`sanitize_pdf` call.

    The ``output_bytes`` field carries the sanitised PDF; the CLI
    shell writes it to disk. The library function itself never
    touches the filesystem. The result is an audit record for fixture
    preparation, not an application persistence model.

    The OUTPUT facts are derived facts, not declarations, and the model
    enforces that: ``output_sha256`` and ``output_size_bytes`` must be the
    digest and length of the ``output_bytes`` carried alongside them. The
    fields only checked shape before — lowercase hex-64 and non-negative — so
    a result claiming ``output_sha256 = 'b' * 64`` and
    ``output_size_bytes = 999`` for three bytes of content constructed
    happily. That is a sidecar that describes a different artefact from the
    one it ships with, and this record exists to be an audit trail: a
    consumer verifying the digest later cannot tell a sanitiser bug from a
    substituted file.

    The SOURCE facts stay declarations, because the source bytes are
    deliberately not carried here — they are the unsanitised original, and
    :func:`sanitize_pdf` derives both from the real input at the one point
    where it holds them. Binding them would require this record to keep the
    very bytes the sanitiser exists to leave behind.

    Attributes:
        output_bytes: Byte-for-byte sanitised PDF.
        source_sha256: SHA-256 of the input bytes, derived by the pipeline.
        output_sha256: SHA-256 of ``output_bytes``, enforced here.
        source_size_bytes: Size of the input, derived by the pipeline.
        output_size_bytes: Size of ``output_bytes``, enforced here.
        sanitizer_version: Version string of the sanitiser at the
            time of the run.
        determinism_flags: Captured save-flag set.
        replacements_applied: One row per token-replace edit.
        surfaces_scrubbed: One row per PII surface that was wiped.
        warnings: Non-fatal warnings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    output_bytes: bytes
    source_sha256: str = Field(..., pattern=_SHA256_PATTERN)
    output_sha256: str = Field(..., pattern=_SHA256_PATTERN)
    source_size_bytes: int = Field(..., ge=0)
    output_size_bytes: int = Field(..., ge=0)
    sanitizer_version: _NonEmptyStr
    determinism_flags: DeterminismFlags
    replacements_applied: tuple[Replacement, ...]
    surfaces_scrubbed: tuple[ScrubbedSurface, ...]
    warnings: tuple[SanitizationWarning, ...]

    @model_validator(mode="after")
    def _output_facts_describe_the_output_bytes(self) -> SanitizationResult:
        """Refuse a result whose declared output facts do not match its bytes.

        Raises:
            SanitizerValidationError: When the digest or the size disagrees
                with ``output_bytes``.
        """
        actual_sha256 = sha256_hex(self.output_bytes)
        if self.output_sha256 != actual_sha256:
            raise SanitizerValidationError(
                f"output_sha256 does not describe output_bytes: declared {self.output_sha256}, "
                f"bytes hash to {actual_sha256}",
            )
        if self.output_size_bytes != len(self.output_bytes):
            raise SanitizerValidationError(
                f"output_size_bytes does not describe output_bytes: declared {self.output_size_bytes}, "
                f"bytes are {len(self.output_bytes)} long",
            )
        return self
