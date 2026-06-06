"""Pytest fixtures for split adapter tests."""

pytest_plugins = (
    'aeat.adapters.inbound.declaracion.tests._parser_boundary_support',
    'aeat.adapters.inbound.declaracion.tests._verification_chain_support',
)
