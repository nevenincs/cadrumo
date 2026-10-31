"""Drive a live command through the real CLI with synthetic arguments and observe it.

The command-graph probes share one way of reaching a command: its operator path
comes from the graph's parent chain, each required parameter gets a synthetic
value derived from its declared type, and a seeded natural-person profile gives
profile-bound commands something to open. ``sys.monitoring`` then watches the
command's own behavior target, so a probe can prove its command actually ran.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.operator import configure_operator_auth
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.login_session import publish_created_profile_session
from cadrumo.application.user_profile.profile_record_repository import close_active_profile_record_session
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle
from cadrumo_client.commands.tests.command_drive_support import PROBE_PROFILE_LABEL, PROBE_PROFILE_TAX_ID

from .portable_human_cli_runtime import PortableHumanCliRuntime, portable_human_cli_runtime

_STORAGE_DIRNAME = "cadrumo-storage"


@dataclass(frozen=True, slots=True)
class _RegisteredProbeProfile:
    """One registered, completed probe profile's storage root and the synthetic key it unlocked."""

    storage_root: Path
    profile_id: UUID
    dek: bytes


_REGISTERED_PROBE_PROFILES: dict[tuple[UserProfileFact, ...], _RegisteredProbeProfile] = {}


def _remove_registered_probe_profiles() -> None:
    for template in _REGISTERED_PROBE_PROFILES.values():
        shutil.rmtree(template.storage_root.parent, ignore_errors=True)
    _REGISTERED_PROBE_PROFILES.clear()


def _registered_probe_profile(extra_facts: tuple[UserProfileFact, ...]) -> _RegisteredProbeProfile:
    """Register and complete the probe profile once per worker and fact set.

    Registration and setup completion cost seconds and are identical for every
    probe. The stored root holds no absolute path and no session, so a copy is
    the same registered profile in a new place; the selected-profile pointer
    registration wrote is kept, and only the process's sessions are closed.
    """
    template = _REGISTERED_PROBE_PROFILES.get(extra_facts)
    if template is not None:
        return template
    if not _REGISTERED_PROBE_PROFILES:
        atexit.register(_remove_registered_probe_profiles)
    base = Path(tempfile.mkdtemp(prefix="probe-profile-template-"))
    with portable_password_custody(), isolated_profile_storage_root(tmp_path=base) as root:
        try:
            profile_id = register_cli_profile(
                label=PROBE_PROFILE_LABEL,
                facts={
                    "identity.name": "Ana",
                    "identity.surnames": "Perez",
                    "identity.tax_id": PROBE_PROFILE_TAX_ID,
                    "taxpayer_type.entity_type": "natural_person",
                    "provenance.source": "manual_cli",
                    **{fact.path: str(fact.value) for fact in extra_facts},
                },
                log_in=False,
            )
            live = current_active_bucket_session()
            assert live is not None and live.bucket_id == profile_id
            dek = bytes(live.dek)
        finally:
            close_active_bucket_session()
            close_active_profile_record_session()
    template = _RegisteredProbeProfile(storage_root=root, profile_id=UUID(profile_id), dek=dek)
    _REGISTERED_PROBE_PROFILES[extra_facts] = template
    return template


@contextmanager
def seeded_probe_runtime(
    tmp_path: Path,
    *,
    extra_facts: tuple[UserProfileFact, ...] = (),
    certificate_path: Path | None = None,
    client_native_store: AutomationSecretStore | None = None,
) -> Generator[PortableHumanCliRuntime]:
    """Register real password custody and own admitted, observable CLI execution.

    Registration's governed-fact lease ends before the joined runtime captures
    its context. No fixture-level governed-fact scope is lent to a handler.
    Each case receives its own copy of the profile registered once per worker
    and is unlocked by the publication registration itself performs.
    """
    template = _registered_probe_profile(extra_facts)
    tmp_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template.storage_root, tmp_path / _STORAGE_DIRNAME)
    with portable_password_custody(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        assert root == tmp_path / _STORAGE_DIRNAME
        profile_id = str(template.profile_id)
        with bundled_indexed_authority().operation() as operation:
            publish_created_profile_session(
                bucket_id=profile_id, dek=template.dek, profile_decode_context=operation.profile_decode_context()
            )
        if certificate_path is not None:
            with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
                configure_operator_auth(
                    "certificate",
                    certificate_path=certificate_path,
                    operator_scope_ports=build_operator_scope_ports(),
                    operation=operation,
                )
        with portable_human_cli_runtime(
            storage_root=root,
            profile_id=UUID(profile_id),
            label=PROBE_PROFILE_LABEL,
            client_native_store=client_native_store,
        ) as runtime:
            yield runtime


@contextmanager
def synthetic_aeat_credentials(workdir: Path) -> Generator[Path]:
    """Configure a real, self-signed certificate naming the seeded profile's taxpayer.

    A session-gated AEAT flow refuses at credential loading when nothing is
    configured, before it ever builds a Sede session. With this certificate the
    flow loads its credentials and reaches the Sede client, where a sealed run
    stops at the browser launch. The bundle is synthetic and never leaves the
    test's directory.
    """
    now = datetime.now(UTC)
    bundle = build_pkcs12_bundle(
        workdir,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=365),
        name="probe-certificate",
        subject_cn=f"PROBE HOLDER - {PROBE_PROFILE_TAX_ID}",
    )
    with override_settings(
        cadrumo_certificate_path=bundle,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ):
        yield bundle
