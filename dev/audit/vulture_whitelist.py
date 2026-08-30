"""Vulture whitelist: signature parameters that are intentionally unused.

Each entry below is a *required* parameter that vulture cannot see being
read, because the parameter exists to satisfy a contract rather than to be
consumed in the body:

* ``http`` / ``num_retries`` — part of the ``google-api-python-client``
  ``execute()`` keyword contract on the ``_ExecutableRequest`` Protocol stub
  (:mod:`cadrumo.adapters.outbound.google.api`). The stub body is ``...``; the
  names match the wire client's keyword arguments and cannot be renamed.
* ``fileId`` — the Drive ``get_media`` keyword on the ``_DriveFilesResource``
  Protocol stub (:mod:`cadrumo.adapters.outbound.google.document_link_resolver`).
  The name is the google API's keyword and is part of the structural type.
* ``q`` / ``pageSize`` / ``pageToken`` — the Drive ``files().list`` keyword
  contract on the same ``_DriveFilesResource`` Protocol stub. The names are the
  google API's keywords and are part of the structural type.
* ``protocol`` — the positional argument of the ``__reduce_ex__`` dunder
  override on the decrypted-evidence tripwire
  (:mod:`cadrumo.application.ledger.evidence_input`). The signature is fixed by
  the pickle protocol; the override exists to *refuse* pickling.
* ``source_citation`` — a keyword-only parameter on
  ``dev.docs.terminology_handbook._curation.set_language_field`` kept as part of the public
  curation API signature.
* ``cache_discovery`` — the ``googleapiclient.discovery.build`` keyword
  contract on the ``_SheetsDiscoveryBuilder`` Protocol stub
  (:mod:`cadrumo.application.storage.calc_sheets.parity_harness`). The name is
  the google API client's keyword and is part of the structural type.

Vulture marks a name "used" when it appears in a whitelist file. Referencing
each name once here clears the false positive while leaving every other
occurrence of an unused name still subject to detection — this file lists
only these specific, individually-justified names, so it cannot mask genuinely
dead code elsewhere. When any of these parameters is removed at its source,
delete its line here so the audit re-detects a stale whitelist entry.
"""

from __future__ import annotations


def _execute(http: object, num_retries: object) -> None:
    """Mirror ``_ExecutableRequest.execute`` keyword contract."""
    http  # noqa: B018
    num_retries  # noqa: B018


def _get_media(fileId: object) -> None:  # noqa: N803
    """Mirror ``_DriveFilesResource.get_media`` keyword contract."""
    fileId  # noqa: B018


def _list_files(q: object, pageSize: object, pageToken: object) -> None:  # noqa: N803
    """Mirror ``_DriveFilesResource.list`` keyword contract."""
    q  # noqa: B018
    pageSize  # noqa: B018
    pageToken  # noqa: B018


def _reduce_ex(protocol: object) -> None:
    """Mirror ``__reduce_ex__`` pickle-protocol signature."""
    protocol  # noqa: B018


def _set_language_field(source_citation: object) -> None:
    """Mirror ``set_language_field`` keyword-only API parameter."""
    source_citation  # noqa: B018


def _sheets_discovery_build(cache_discovery: object) -> None:
    """Mirror ``_SheetsDiscoveryBuilder.__call__`` keyword contract."""
    cache_discovery  # noqa: B018
