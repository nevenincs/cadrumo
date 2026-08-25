"""Reading the taxpayer a registered certificate names, before any session.

An FNMT *persona física* certificate carries its holder's NIF or NIE in
the subject, and the live session already reads it to decide whether the
certificate belongs to the active profile. Nothing exposed it EARLIER
than that, so an operator who set a certificate up first met setup
surfaces that could not tell who they were — and learned the profile and
the certificate disagreed only when a login refused.

:func:`~application.auth.certificate_source_tax_id` closes that by
answering the same question before a session exists. Because its only
job is to SUGGEST a value the operator may always type themselves, every
ordinary reason the read cannot happen must answer ``""`` rather than
raise: a setup page must not become unreachable because a certificate is
unreadable.

Real self-signed PKCS#12 bundles are generated at runtime, so the read
goes through the real decode rather than a stand-in for it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.outbound.aeat.auth.certificate import read_certificate_subject_nif
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.certificates import CERTIFICATE_BUNDLE_PASSPHRASE, build_pkcs12_bundle
from ...wizard import compiler as _wizard  # noqa: F401  (compiler import seeds the ProfileKey registry)
from ..certificate_source_operations import (
    certificate_source_tax_id,
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_PROFILE_LABEL = "cert-identity-read"
_HOLDER_NIF = "00000000T"
_OTHER_NIF = "00000001R"
_WRONGCERTIFICATE_BUNDLE_PASSPHRASE = "not-the-passphrase"  # noqa: S105 - synthetic wrong passphrase, not a secret


_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_BUCKET_ID, display_name=_PROFILE_LABEL)


def _bundle(tmp_path: Path, *, name: str, subject_cn: str) -> Path:
    now = datetime.now(UTC)
    return build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=200),
        name=name,
        subject_cn=subject_cn,
    )


def _registered(tmp_path: Path, *, name: str, nif: str, secret: str = CERTIFICATE_BUNDLE_PASSPHRASE) -> None:
    path = _bundle(tmp_path, name=name, subject_cn=f"TEST HOLDER - {nif}")
    register_operator_certificate_source(name=name, certificate_path=path)
    set_operator_certificate_source_secret(name=name, secret=SecretStr(secret))


def test_the_selected_certificate_names_its_holder(tmp_path: Path) -> None:
    """The read this exists for: who does the active certificate belong to."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF)
    select_operator_certificate_source(name="personal")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == _HOLDER_NIF


def test_a_named_source_is_read_over_the_selected_one(tmp_path: Path) -> None:
    """A gestor holds several certificates, so the caller may name one."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF)
    _registered(tmp_path, name="work", nif=_OTHER_NIF)
    select_operator_certificate_source(name="personal")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif, name="work") == _OTHER_NIF


def test_nothing_registered_answers_empty_rather_than_raising() -> None:
    """The common case on a fresh profile, and it must not be an error."""
    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_a_registered_but_unselected_source_answers_empty(tmp_path: Path) -> None:
    """Registering does not select, so an unnamed read has nothing to read."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF)

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_an_unknown_name_answers_empty_rather_than_raising(tmp_path: Path) -> None:
    """A seeding read reports "nothing to suggest", never a refusal."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF)
    select_operator_certificate_source(name="personal")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif, name="absent") == ""


def test_a_source_with_no_stored_passphrase_answers_empty(tmp_path: Path) -> None:
    """The bundle cannot be decoded, so there is no identifier to offer."""
    path = _bundle(tmp_path, name="personal", subject_cn=f"TEST HOLDER - {_HOLDER_NIF}")
    register_operator_certificate_source(name="personal", certificate_path=path)
    select_operator_certificate_source(name="personal")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_a_wrong_passphrase_answers_empty(tmp_path: Path) -> None:
    """A decode failure is the health probe's verdict to report, not this read's."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF, secret=_WRONGCERTIFICATE_BUNDLE_PASSPHRASE)
    select_operator_certificate_source(name="personal")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_a_missing_certificate_file_answers_empty(tmp_path: Path) -> None:
    """A moved or deleted bundle degrades to no suggestion."""
    path = _bundle(tmp_path, name="personal", subject_cn=f"TEST HOLDER - {_HOLDER_NIF}")
    register_operator_certificate_source(name="personal", certificate_path=path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="personal")
    path.unlink()

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_a_subject_carrying_no_individual_identifier_answers_empty(tmp_path: Path) -> None:
    """An organisation certificate names no persona física to suggest.

    The certificate reader refuses this rather than guessing an identity,
    and that refusal must reach a seeding caller as "nothing to offer".
    """
    path = _bundle(tmp_path, name="entity", subject_cn="ACME SOCIEDAD LIMITADA")
    register_operator_certificate_source(name="entity", certificate_path=path)
    set_operator_certificate_source_secret(name="entity", secret=SecretStr(CERTIFICATE_BUNDLE_PASSPHRASE))
    select_operator_certificate_source(name="entity")

    assert certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif) == ""


def test_the_read_is_pure_and_leaves_the_registry_untouched(tmp_path: Path) -> None:
    """Suggesting must not become a mutation the operator never asked for."""
    _registered(tmp_path, name="personal", nif=_HOLDER_NIF)
    select_operator_certificate_source(name="personal")
    before = workflow_state_repository().load().auth

    certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif)

    assert workflow_state_repository().load().auth == before
