"""Provenance tokens defined in the application layer are schema-declared.

The registry schema declares the provenance set, and the carrier refuses
a token it does not contain, so a constant defined outside that set is a
write that will be refused at the profile boundary rather than at the
line that names it.

The domain half of this contract checks the constants core publishes. It
cannot check this one: a domain test importing an application constant
would invert the dependency direction in the import graph even though no
production code does it. So the token defined here is checked here,
against the same schema-declared set, which every layer may read.
"""

from __future__ import annotations

import pytest

from ....domain.user_profile import declared_provenance_sources
from ... import user_profile as user_profile_package
from .. import CENSO_SOURCE_TAG

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Naming suffix by which this package publishes a provenance token. The set is
#: derived from the package's own ``__all__`` rather than listed here, because a
#: list is what let ``CENSO_DERIVED_SOURCE_TAG`` be published undeclared while a
#: check naming only its sibling passed.
_PROVENANCE_EXPORT_SUFFIX = "_SOURCE_TAG"


def _published_provenance_tokens() -> dict[str, str]:
    """Return every provenance token this package publishes, by export name."""
    from .. import __all__ as exported

    return {name: getattr(user_profile_package, name) for name in exported if name.endswith(_PROVENANCE_EXPORT_SUFFIX)}


def test_the_scan_finds_the_exports_it_claims_to_check() -> None:
    """A discovery that matched nothing would pass while proving nothing.

    The gate below asserts an empty violation list, which is worthless
    unless the discovery actually reaches the package's provenance
    exports. Renaming the convention without updating the suffix would
    otherwise silently empty the gate.
    """

    published = _published_provenance_tokens()

    assert published, (
        f"no export ending {_PROVENANCE_EXPORT_SUFFIX!r} was found in the package; "
        "the naming convention changed and this gate has stopped checking anything"
    )
    assert CENSO_SOURCE_TAG in published.values()


def test_every_published_provenance_token_is_declared_by_the_schema() -> None:
    """Each token the package publishes must be one the carrier accepts.

    Enumerated rather than named. An earlier version checked one token by
    name and passed while a sibling was published undeclared: no fact
    could carry it, so a surface stamping it manufactured a record the
    strict read path would refuse.
    """

    declared = declared_provenance_sources()
    undeclared = sorted(
        f"{name} = {value!r}" for name, value in _published_provenance_tokens().items() if value not in declared
    )

    assert not undeclared, (
        f"application publishes provenance token(s) the profile schema does not declare: {undeclared}. "
        "Declare the token in provenance.source, or delete it if nothing stamps it; "
        "do not change what shipped code stamps."
    )


def test_the_declared_set_is_read_from_the_schema_not_copied() -> None:
    """Guard against the check degrading into a comparison of two copies.

    If the declared set were ever hand-mirrored in code, this contract
    would pass while the real authority drifted, which is the failure it
    exists to prevent.
    """

    from ....domain.user_profile import load_user_profile_schema

    assert declared_provenance_sources() == frozenset(
        load_user_profile_schema().field("provenance.source").enum_values,
    )
