"""Vulture whitelist: signature parameters that are intentionally unused.

Each entry below is a *required* parameter that vulture cannot see being
read, because the parameter exists to satisfy a contract rather than to be
consumed in the body:

* ``http`` / ``num_retries`` — part of the ``google-api-python-client``
  ``execute()`` keyword contract on the ``_ExecutableRequest`` Protocol stub
  (:mod:`cadrumo.adapters.outbound.google.api`). The stub body is ``...``; the
  names match the wire client's keyword arguments and cannot be renamed.
* ``protocol`` — the positional argument of the ``__reduce_ex__`` dunder
  override on the decrypted-evidence tripwire
  (:mod:`cadrumo.application.ledger.evidence_input`). The signature is fixed by
  the pickle protocol; the override exists to *refuse* pickling.
* ``source_citation`` — a keyword-only parameter on
  ``dev.docs.terminology_handbook.curation.set_language_field`` kept as part of the public
  curation API signature.
* ``prop`` — the parameter of ``append`` on the ``_CustomDocumentProperties``
  Protocol stub (:mod:`cadrumo.adapters.outbound.workbook.calc_sheets_xlsx`).
  The stub body is ``...``; the parameter is part of the structural type.
Vulture marks a name "used" when it appears in a whitelist file. Referencing
each name once here clears all findings with that name across the scan,
including unrelated definitions. These entries therefore cannot establish
that other occurrences are used. When any parameter is removed at its source,
delete its line here; resolved-import and argument checks provide independent
evidence for the names this lexical scan cannot distinguish.
"""

from __future__ import annotations


def _execute(http: object, num_retries: object) -> tuple[object, object]:
    """Mirror ``_ExecutableRequest.execute`` keyword contract."""
    return http, num_retries


def _reduce_ex(protocol: object) -> object:
    """Mirror ``__reduce_ex__`` pickle-protocol signature."""
    return protocol


def _set_language_field(source_citation: object) -> object:
    """Mirror ``set_language_field`` keyword-only API parameter."""
    return source_citation


def _custom_document_properties_append(prop: object) -> object:
    """Mirror ``_CustomDocumentProperties.append`` structural signature."""
    return prop
