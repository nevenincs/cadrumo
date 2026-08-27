"""Real-behavior tests for the named multi-certificate source registry.

Exercises the application service against a real workflow-state
repository (secure-object persisted, encrypted at rest) — no mocks or
fakes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import Settings
from ....tests.profile_storage_root_fixture import bucket_session_storage_fixture
from ....tests.user_profile import register_minimal_profile
from ...wizard import compiler as _wizard  # noqa: F401  (compiler import seeds the ProfileKey registry)
from ...workflow.persistence import workflow_state_repository
from .. import certificate_sources as _certificate_sources_module
from ..certificate_source_operations import (
    list_operator_certificate_sources,
    register_operator_certificate_source,
    remove_operator_certificate_source,
    select_operator_certificate_source,
)
from ..credentials import resolve_active_certificate_credentials
from ..operator import configure_operator_auth, inspect_operator_auth
from ..operator_results import CertificateSourceNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: This module's OWN bucket. A bucket shared with a sibling module makes
#: the two suites' isolation fixtures interchangeable and puts both on one
#: bucket-scoped master-key session in the same run.
_BUCKET_ID = "c0000001-0000-4000-8000-000000000001"
_PROFILE_LABEL = "gestor-multi-cert"


def _register_operator_profile() -> None:
    """Publish the operator profile capsule before anything reads its bucket."""
    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
    )


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)


def test_register_two_sources_are_both_enumerable(tmp_path: Path) -> None:
    """Registering two named certificate sources makes both listable.

    A gestor manages several entities (their own personal certificate
    plus at least one apoderado certificate); the registry must
    enumerate every registered source, not only the most recently
    registered one.
    """
    _register_operator_profile()
    personal = tmp_path / "personal.p12"
    personal.write_bytes(b"placeholder personal cert")
    apoderado = tmp_path / "apoderado-acme.p12"
    apoderado.write_bytes(b"placeholder apoderado cert")

    register_operator_certificate_source(name="personal", certificate_path=personal)
    register_operator_certificate_source(name="apoderado-acme", certificate_path=apoderado, friendly_name="ACME SL")

    report = list_operator_certificate_sources()

    names = {source.name for source in report.sources}
    assert names == {"personal", "apoderado-acme"}, f"both sources must be enumerable — got {names!r}"
    by_name = {source.name: source for source in report.sources}
    assert by_name["personal"].certificate_path == str(personal)
    assert by_name["apoderado-acme"].certificate_path == str(apoderado)
    assert by_name["apoderado-acme"].friendly_name == "ACME SL"


def test_select_one_source_activates_it_and_leaves_the_other_inactive(tmp_path: Path) -> None:
    """Selecting one registered source marks only that source active.

    The other stays registered but inactive: selection is exclusive
    across the registry, and the canonical projection resolves the selected
    record without copying it into the unnamed-credential field.
    """
    _register_operator_profile()
    personal = tmp_path / "personal.p12"
    personal.write_bytes(b"placeholder personal cert")
    apoderado = tmp_path / "apoderado-acme.p12"
    apoderado.write_bytes(b"placeholder apoderado cert")

    configure_operator_auth("certificate")
    register_operator_certificate_source(name="personal", certificate_path=personal)
    register_operator_certificate_source(name="apoderado-acme", certificate_path=apoderado)

    result = select_operator_certificate_source(name="apoderado-acme")

    assert result.name == "apoderado-acme"
    assert result.active is True
    assert result.certificate_path == str(apoderado)

    report = list_operator_certificate_sources()
    by_name = {source.name: source for source in report.sources}
    assert by_name["apoderado-acme"].active is True
    assert by_name["personal"].active is False, "the non-selected source must stay registered but inactive"
    assert report.active_source == "apoderado-acme"

    # `auth status` resolves the selected source through the canonical
    # credential projection.
    status = inspect_operator_auth()
    assert status.certificate_path == str(apoderado)


def test_selecting_a_second_source_switches_the_active_selection(tmp_path: Path) -> None:
    """Selecting a different source moves the active marker, it does not accumulate."""
    _register_operator_profile()
    personal = tmp_path / "personal.p12"
    personal.write_bytes(b"placeholder personal cert")
    apoderado = tmp_path / "apoderado-acme.p12"
    apoderado.write_bytes(b"placeholder apoderado cert")

    register_operator_certificate_source(name="personal", certificate_path=personal)
    register_operator_certificate_source(name="apoderado-acme", certificate_path=apoderado)

    select_operator_certificate_source(name="personal")
    select_operator_certificate_source(name="apoderado-acme")

    report = list_operator_certificate_sources()
    active_names = {source.name for source in report.sources if source.active}
    assert active_names == {"apoderado-acme"}, f"exactly one source must be active — got {active_names!r}"


def test_selecting_an_unregistered_source_refuses(tmp_path: Path) -> None:
    """Selecting a name that was never registered raises a typed refusal, not a silent no-op."""
    _register_operator_profile()

    with pytest.raises(CertificateSourceNotFoundError):
        select_operator_certificate_source(name="does-not-exist")


def test_state_source_refusal_is_the_registered_public_contract() -> None:
    """The state transform raises the sole public auth error, not a parallel KeyError."""
    _register_operator_profile()

    with pytest.raises(CertificateSourceNotFoundError) as refusal:
        _certificate_sources_module.select_certificate_source(
            workflow_state_repository().load(),
            name="does-not-exist",
        )

    assert type(refusal.value) is CertificateSourceNotFoundError
    assert _certificate_sources_module.CertificateSourceNotFoundError is CertificateSourceNotFoundError
    assert CertificateSourceNotFoundError.__module__ == "cadrumo.application.auth.operator_results"


def test_re_registering_an_existing_name_repoints_its_path(tmp_path: Path) -> None:
    """Re-registering a name updates its path in place rather than erroring or duplicating."""
    _register_operator_profile()
    original = tmp_path / "personal-v1.p12"
    original.write_bytes(b"v1")
    renewed = tmp_path / "personal-v2.p12"
    renewed.write_bytes(b"v2")

    register_operator_certificate_source(name="personal", certificate_path=original)
    register_operator_certificate_source(name="personal", certificate_path=renewed)

    report = list_operator_certificate_sources()
    assert len(report.sources) == 1, "re-registering the same name must not duplicate the entry"
    assert report.sources[0].certificate_path == str(renewed)


def test_remove_source_clears_registration_and_active_selection(tmp_path: Path) -> None:
    """Removing the active source makes its certificate path unusable."""
    _register_operator_profile()
    personal = tmp_path / "personal.p12"
    personal.write_bytes(b"placeholder personal cert")

    register_operator_certificate_source(name="personal", certificate_path=personal)
    select_operator_certificate_source(name="personal")

    result = remove_operator_certificate_source(name="personal")

    assert result.removed is True
    report = list_operator_certificate_sources()
    assert report.sources == ()
    assert report.active_source == ""
    reloaded = workflow_state_repository().load()
    assert reloaded.auth.certificate_path is None
    credentials = resolve_active_certificate_credentials(
        settings=Settings(
            cadrumo_certificate_path=None,
            cadrumo_certificate_password_secret=None,
        ),
    )
    assert credentials.certificate_path is None
    assert credentials.source_name is None


def test_remove_unregistered_source_is_a_no_op() -> None:
    """Removing a name that was never registered is a no-op, not an error."""
    _register_operator_profile()

    result = remove_operator_certificate_source(name="never-registered")

    assert result.removed is False


def test_certificate_source_registry_roundtrips_through_encrypted_workflow_state(tmp_path: Path) -> None:
    """The registry survives a save/reload cycle through the real secure-object repository.

    ``register_operator_certificate_source`` persists via the same
    encrypted :class:`adapters.persistence.storage.SecureObjectRepository`
    path ``configure_operator_auth`` uses; a fresh
    ``workflow_state_repository().load()`` must reproduce every
    registered source and the active selection exactly.
    """
    _register_operator_profile()
    personal = tmp_path / "personal.p12"
    personal.write_bytes(b"placeholder personal cert")
    apoderado = tmp_path / "apoderado-acme.p12"
    apoderado.write_bytes(b"placeholder apoderado cert")

    register_operator_certificate_source(name="personal", certificate_path=personal, friendly_name="Yo mismo")
    register_operator_certificate_source(name="apoderado-acme", certificate_path=apoderado)
    select_operator_certificate_source(name="apoderado-acme")

    reloaded = workflow_state_repository().load()

    assert set(reloaded.auth.certificate_sources) == {"personal", "apoderado-acme"}
    assert reloaded.auth.certificate_sources["personal"].certificate_path == str(personal)
    assert reloaded.auth.certificate_sources["personal"].friendly_name == "Yo mismo"
    assert reloaded.auth.certificate_sources["apoderado-acme"].certificate_path == str(apoderado)
    assert reloaded.auth.active_certificate_source == "apoderado-acme"
    assert reloaded.auth.certificate_path is None
