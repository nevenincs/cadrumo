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
from .. import CENSO_SOURCE_TAG

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_censo_read_token_is_declared_by_the_schema() -> None:
    """The censal-read provenance must be a token the carrier accepts.

    Were it not declared, every fact the censal sync writes would be
    refused at construction, and the failure would surface as a broken
    pull rather than as the undeclared constant it really is.
    """

    assert CENSO_SOURCE_TAG in declared_provenance_sources(), (
        f"application defines provenance token {CENSO_SOURCE_TAG!r} which the profile schema does not declare. "
        "Add it to provenance.source in the schema; do not change what the shipped code stamps."
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
