"""Payload-contract guard for the declared-unimplemented profile export surface.

The ``_config_payloads.py`` export / import / subject-access-request /
rename payload classes are authored CommandSpec result targets for the
declared-unimplemented keys -- deliberate evidence-keeping of retired
verbs, not live surfaces. This module pins the canonical result type's
strictness so a permissive shell cannot be reintroduced at the payload
boundary.

The roundtrip tests that once lived here exercised the ``export`` /
``import`` verbs; those verbs are unregistered, so the roundtrips cannot
run and are retired rather than rewritten. The schema-registration gates
(``test_verb_input_schema``, ``test_json_schema_conformance``) keep
asserting that the four keys do NOT resolve to live verbs.

No mocks. Real pydantic validation, real enum members.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_config_profile_export_result_refuses_malformed_transport_and_reconcile_row(tmp_path: Path) -> None:
    """The canonical result type -- not a permissive shell -- refuses malformed custody rows.

    ``purpose``/``transport`` are typed as the real
    :class:`~cadrumo.application.user_profile.ProfileBundleExportPurpose` /
    :class:`~cadrumo.application.user_profile.ProfileBundleExportTransport`
    enums, so even a bare string equal to a valid member's *value* is refused:
    only the canonical enum instance the export service already returns
    satisfies the field. A blank reconcile-failure ``journal_id``/``reason``
    is also rejected. A permissive ``str``/``dict`` shell -- the defect this
    finding reported -- would have accepted all of these.
    """
    from ....application.user_profile.bundle_export_contracts import (
        ProfileBundleExportPurpose,
        ProfileBundleExportTransport,
    )
    from .._config_payloads import ConfigProfileExportReconcileFailurePayload, ConfigProfileExportResult

    base_kwargs = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "display_name": "Example",
        "out": str(tmp_path / "bundle.json"),
        "schema_version": 3,
        "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        "transport": ProfileBundleExportTransport.CLEARTEXT_LOCAL,
        "data_categories": ["profile_identity_and_facts"],
        "excluded_data_categories": [],
        "reconcile_failures": [],
    }
    # A valid payload -- built from the real canonical enum members, exactly
    # as the export handler passes them -- round-trips cleanly.
    valid = ConfigProfileExportResult(**base_kwargs)
    assert valid.purpose is ProfileBundleExportPurpose.PORTABLE_TRANSFER
    assert valid.transport is ProfileBundleExportTransport.CLEARTEXT_LOCAL

    # A bare string equal to a valid member's value is still refused: the
    # field demands the canonical enum instance, not a permissive str.
    with pytest.raises(ValidationError):
        ConfigProfileExportResult.model_validate({**base_kwargs, "purpose": "portable_transfer"})
    with pytest.raises(ValidationError):
        ConfigProfileExportResult.model_validate({**base_kwargs, "transport": "cleartext_local"})
    with pytest.raises(ValidationError):
        ConfigProfileExportReconcileFailurePayload(journal_id="", destination=None, reason="SomeError")
    with pytest.raises(ValidationError):
        ConfigProfileExportReconcileFailurePayload(journal_id="j1", destination=None, reason="")

    # A valid reconcile-failure row round-trips.
    row = ConfigProfileExportReconcileFailurePayload(journal_id="j1", destination=None, reason="SomeError")
    assert row.journal_id == "j1"
    assert row.reason == "SomeError"
