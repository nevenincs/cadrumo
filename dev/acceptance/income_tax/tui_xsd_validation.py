"""Independent local Modelo 100 XSD normalization and validation evidence."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from dev.registry.record_design_xsd_support import repair_xsd_regex_escapes

from .tui_contracts import LocalXsdValidationEvidence

if TYPE_CHECKING:
    pass


_XML_DECLARATION_ENCODING: Final = re.compile(r'encoding="[^"]+"')


_XSD_NORMALIZATION: Final = (
    "canonical record-design preparation replaces the XML declaration encoding "
    "with UTF-8 and removes only illegal escapes from xs:pattern values"
)


def validate_modelo_100_xsd(*, xml_path: Path, xsd_path: Path) -> LocalXsdValidationEvidence:
    """Validate XML with the shared AEAT record-design schema preparation.

    The schema's original bytes and the exact effective prepared bytes are
    both fingerprinted.  The only semantic transformation is delegated to
    the existing record-design repair helper; it removes invalid XSD-regex
    escapes and never rewrites declaration data.
    """
    from lxml import etree

    xml_bytes = xml_path.read_bytes()
    xsd_bytes = xsd_path.read_bytes()
    source_text = xsd_bytes.decode("iso-8859-1")
    prepared_text = _XML_DECLARATION_ENCODING.sub('encoding="UTF-8"', source_text, count=1)
    repaired_text, repair_count = repair_xsd_regex_escapes(prepared_text)
    effective_bytes = repaired_text.encode("utf-8")
    try:
        schema = etree.XMLSchema(etree.fromstring(effective_bytes))
        document = etree.fromstring(xml_bytes)
        xsd_valid = schema.validate(document)
        errors = tuple(
            _schema_error_identity(error.domain_name, error.type_name, error.line) for error in schema.error_log
        )
    except etree.LxmlError as exc:
        # The textual parser message can contain document values.  Keep only
        # the stable exception class in the durable receipt.
        xsd_valid = False
        errors = (f"xsd_validation.{type(exc).__name__}",)
    return LocalXsdValidationEvidence(
        xml_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        xml_size=len(xml_bytes),
        original_schema_sha256=hashlib.sha256(xsd_bytes).hexdigest(),
        original_schema_size=len(xsd_bytes),
        normalization=_XSD_NORMALIZATION,
        normalization_count=repair_count,
        effective_validation_schema_sha256=hashlib.sha256(effective_bytes).hexdigest(),
        effective_validation_schema_size=len(effective_bytes),
        xsd_valid=xsd_valid,
        error_identities=errors,
    )


def _schema_error_identity(domain: str | None, type_name: str | None, line: int) -> str:
    """Return a value-free validation error identity suitable for a receipt."""
    return ":".join((domain or "unknown_domain", type_name or "unknown_type", str(line)))
