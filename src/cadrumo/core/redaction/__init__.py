"""Redaction-rule registry and the :func:`redact` helper family.

The :class:`core.classification.RedactionRule` shape lives in
:mod:`core.classification` so the :class:`SensitivityClass` policy
table can reference rule names without a circular import. This module ships:

* a small in-memory registry of default
  :class:`core.classification.RedactionRule` instances keyed by
  name (NIF, URL, OAuth bearer token, opaque bearer token);
* :func:`redact`, the flat-string helper that applies a tuple of
  rules in declared order;
* :func:`redact_structured`, the recursive variant that walks dict /
  list / tuple containers and redacts every string leaf in place;
* :func:`redact_for_log`, the convenience wrapper for log lines and
  exception messages;
* :func:`redact_for_cli_output` and
  :func:`redact_structured_for_cli_output`, the public CLI success-output
  profile for rendered text and JSON-shaped payloads;
* :func:`default_rules_for` and :func:`default_rules_for_class`, the
  resolvers that turn rule names stored on a
  :class:`core.classification.ClassificationPolicy` into the
  underlying :class:`core.classification.RedactionRule`
  instances.

The redaction strategies, defined in
:class:`core.classification.RedactionStrategy`, are:

``SHA256_PREFIX``
    Replace the matched span with ``sha256:<first-8-hex>`` of its
    SHA-256 digest. Used for the personal identity shapes (NIF / NIE),
    which are matched on shape alone.

``SHA256_PREFIX_IF_IDENTITY``
    As ``SHA256_PREFIX``, but only when the matched span parses as a real
    Spanish tax identity. Used for the CIF shape, whose letter-led form
    collides with ordinary document references; the check character is
    what tells the two apart.

``SHA256_PREFIX_IF_IBAN``
    As ``SHA256_PREFIX``, but only when the matched span passes the ISO
    13616 mod-97 check. Used for bank accounts, by an operator decision
    that deliberately reaches past this module's stated tax-identity
    must-handle list. A BOE citation is the standing negative control: it
    must keep passing through untouched, and a pattern that starts eating
    one is too wide.

``HOST_ONLY``
    For URL-shaped values, retain only ``<scheme>://<host>``;
    everything else (path, query, fragment) is dropped.

``FINGERPRINT``
    Bearer- / token-shaped values rewrite to
    ``token:sha256:<first-8-hex>``.

``ELLIPSIS``
    Replace the matched span with three ASCII full stops.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
