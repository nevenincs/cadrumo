"""Shared synthetic inputs and operator-scope ports for conformance scenarios."""

from ...adapters.persistence.storage.operator_scope import build_operator_scope_ports

OPERATOR_SCOPE_PORTS = build_operator_scope_ports()
CREDENTIAL_INPUT = "s45-registered-executor-passphrase"
ROTATED_CREDENTIAL_INPUT = "s45-registered-executor-rotated-passphrase"
LEDGER_LIST_PRIVATE_FILTER_SENTINEL = "private-ledger-list-filter-sentinel-6d7c"
OWN_ACCOUNT_SYNTHETIC_IBAN = "ES9121000418450200051332"
