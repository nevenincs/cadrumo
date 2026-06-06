"""Pytest fixtures for split calculation-registry tests."""

pytest_plugins = (
    'aeat.domain.calculations.registry.tests._referential_integrity_support',
    'aeat.domain.calculations.registry.tests._registry_schema_support',
)
