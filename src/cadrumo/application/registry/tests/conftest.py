"""Fixtures shared by every conformance module in this package."""

from ....tests.registry_authority_fixture import bundled_registry_authority_fixture

#: The real validated authority, bound ONCE for this directory.
#:
#: Two modules binding the same factory under the same name are substitutable
#: duplicates, which is a different defect from the aliasing that put the
#: factory in a shared home to begin with; closing one by opening the other is
#: not progress. A conftest rather than an importable module because the name is
#: requested by test parameters only, and an imported fixture shadowed by a
#: parameter of the same name is an unused import to every reader and linter.
registry_authority = bundled_registry_authority_fixture(name="registry_authority")
