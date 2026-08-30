"""Inbound parser for the Certificado de Situación Censal (G313) artefact.

STRUCTURE-ONLY, extraction deliberately unpinned: the certificate's issued
PDF layout has never been observed against a real specimen (none is
obtainable today — no certificate and no usable Clave credentials exist),
so this adapter refuses every document loudly and instructively instead of
guessing a layout and silently mis-extracting censal facts. The target
shape and the profile-fact projection are fully typed and tested in
:mod:`cadrumo.domain.censo`; the day a specimen arrives (through the
encrypted evidence path), the extraction lands here behind the same
signature and the refusal narrows to genuinely unrecognised documents.

The bytes route mirrors :func:`parse_justificante_bytes`: secure-storage
flows hold decrypted bytes in memory and must never materialise a
plaintext temporary file.
"""

from __future__ import annotations

from ....domain.censo.certificado import CertificadoCensalParseError, CertificadoSituacionCensal

_PDF_MAGIC = b"%PDF-"


def parse_certificado_censal_bytes(data: bytes) -> CertificadoSituacionCensal:
    """Parse certificate bytes into a :class:`CertificadoSituacionCensal`.

    Raises:
        CertificadoCensalParseError: Always, today. A non-PDF payload is
            refused as an unrecognised document; a PDF payload is refused
            because the issued-certificate layout extraction is unpinned
            pending a real specimen. Both refusals carry a distinct locale key
            so the flow degrades honestly.
    """
    if not data.startswith(_PDF_MAGIC):
        raise CertificadoCensalParseError(
            translated_message="errors.censo.certificado_not_a_pdf",
        )
    raise CertificadoCensalParseError(
        translated_message="errors.censo.certificado_extraction_unpinned",
    )


__all__ = ["parse_certificado_censal_bytes"]
