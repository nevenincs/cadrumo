"""Hermetic storage and profile setup for documentation sequences."""

from __future__ import annotations

import os
import shutil
from base64 import b64encode
from collections.abc import Generator, Sequence
from contextlib import chdir, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import keyring
import keyring.backends.null
import keyring.core

from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.profile_persistence_composition import (
    composed_profile_persistence_ports,
)
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    derive_test_bucket_key,
    open_test_profile_session,
    profile_authority_contexts,
    upsert_test_profile_facts,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession
from cadrumo.application.user_profile.custody_ports import create_profile_custody_registration_material
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from dev._paths import REPO_ROOT
from dev.temporary_output import prepare_temp_root

from .errors import SequenceExecutionError
from .receipt_fixture import requires_persistent_sign_in, sequence_receipt_store
from .runtime_fixture import SANDBOX_INSTANT, sequence_runtime

#: The deterministic injected profile identity (a fixed valid UUIDv4 shape,
#: distinct from the shared test-fixture bucket ids). With the clock frozen and
#: this identity injected, only the substrate's declared surrogate keys should
#: still flap across runs (``GOLDEN_MASK_FIELDS``).
SANDBOX_PROFILE_ID: str = "99999999-9999-4999-8999-999999999999"

#: The sandbox profile's display label (a decoupled label, no role in any key).
SANDBOX_PROFILE_LABEL: str = "docs-sequence-sandbox"

#: An existing alternative for the documented selected-profile deletion journey.
SANDBOX_REPLACEMENT_PROFILE_ID = "f6a2ae44-2493-4c98-b856-ea071ff26dea"
SANDBOX_REPLACEMENT_PROFILE_LABEL = "docs-sequence-replacement"

#: Synthetic profile facts for the injected sandbox identity, mirroring the
#: fact paths the workspace-initialization service persists. All values are
#: synthetic; richer fixture state is built by ``@setup`` frames.
_SANDBOX_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Docs"),
    UserProfileFact(path="identity.surnames", value="Sandbox"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    # Required by the profile schema: the territorial regime is declared
    # explicitly rather than inferred. The sandbox declares the common regime,
    # since the foral branch is the unsupported one and no documented sequence
    # exercises it.
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="documentation examples"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    # Declaring an IVA regime claims the IVA block, which requires the Modelo
    # 303 composition to be stated explicitly rather than inferred from it.
    # ``general`` is the arm matching the regime above.
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    # The IVA block also requires each optional-regime enrolment to be declared
    # rather than assumed absent, so a taxpayer is never silently treated as
    # outside a regime nobody asked about. The sandbox is a plain general-regime
    # filer enrolled in none of them.
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
)


@dataclass(frozen=True)
class SequenceSandbox:
    """The open hermetic sandbox a sequence executes inside."""

    storage_root: Path
    workdir: Path
    profile_id: str
    frozen_instant: datetime


def default_fixtures_root() -> Path:
    """Return the committed ``docs/_sequences/fixtures/`` synthetic-input tree.

    Resolved relative to this module so the engine finds fixtures regardless of
    the process working directory (the same anchoring as the seed recipes).
    """
    repo_root = REPO_ROOT
    return repo_root / "docs" / "_sequences" / "fixtures"


#: Periods for which a documented sequence calculates Modelo 303. Calculation
#: refuses without a complete typed filing-evidence document, so the sandbox
#: seeds one per period rather than asking every page to carry the argument.
#:
#: The four 2025 quarters are here for the shared ``iva-year-2025`` seed recipe,
#: which files a whole year of Modelo 303 so the annual Modelo 390 page has
#: quarters to fold in. A seed drives calculation exactly as a page frame does,
#: so a period reachable only through a recipe still needs its document.
_M303_EVIDENCE_PERIODS: tuple[tuple[int, str], ...] = (
    (2025, "1T"),
    (2025, "2T"),
    (2025, "3T"),
    (2025, "4T"),
    (2026, "1T"),
)


def _seed_m303_filing_evidence(fixtures_dir: Path) -> None:
    """Generate the Modelo 303 filing-evidence documents the sequences pass.

    Generated per run rather than committed. The document embeds the registry
    snapshot for its period, so a committed copy would be invalidated by any
    Modelo 303 registry change and would red the docs build until someone
    noticed it was a stale fixture rather than a real regression. Building it
    from the shared evidence helper binds it to the live snapshot every time,
    and keeps a six-figure-byte blob out of the tree.
    """
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    for name, text in _m303_filing_evidence_documents():
        (fixtures_dir / name).write_text(text, encoding="utf-8", newline="\n")


#: The generated documents per authority generation. A gate worker runs many
#: sequences against one published generation, and each document is a pure
#: function of it, so it is built once rather than once per sandbox.
_M303_EVIDENCE_BY_GENERATION: dict[str, tuple[tuple[str, str], ...]] = {}


def _m303_filing_evidence_documents() -> tuple[tuple[str, str], ...]:
    """Return ``(fixture name, JSON text)`` for every seeded period, built once per generation."""
    from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
    from cadrumo.core.period import Period
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        generation = str(operation.generation)
        documents = _M303_EVIDENCE_BY_GENERATION.get(generation)
        if documents is None:
            built: list[tuple[str, str]] = []
            for filing_year, code in _M303_EVIDENCE_PERIODS:
                period = Period(filing_year=filing_year, code=code)
                evidence = general_m303_filing_evidence(
                    period,
                    reference=f"docs:sequence-sandbox:m303-general:{filing_year}-{code}",
                    operation=operation,
                )
                name = m303_filing_evidence_fixture_name(filing_year, code)
                built.append((name, evidence.model_dump_json(indent=2) + "\n"))
            documents = tuple(built)
            _M303_EVIDENCE_BY_GENERATION[generation] = documents
    return documents


def m303_filing_evidence_fixture_name(filing_year: int, code: str) -> str:
    """Return the sandbox-relative filename a sequence passes for one period."""
    return f"m303-filing-evidence-{filing_year}-{code}.json"


def _refuse_live_opt_in(sequence_id: str) -> None:
    """Refuse to open a sandbox while the live-test opt-in is set."""
    if load_settings().live_tests_enabled:
        raise SequenceExecutionError(
            sequence_id,
            "the live-test opt-in (CADRUMO_LIVE_TESTS_ENABLED) is set; the docs "
            "sequence sandbox never runs against live AEAT — unset it and re-run",
        )


def _publish_sandbox_profile(*, profile_id: str, label: str) -> None:
    """Create and select one real synthetic capsule without authenticating it."""
    identity = UUID(profile_id)
    dek = derive_test_bucket_key(profile_id, purpose="dek")
    material = create_profile_custody_registration_material(
        profile_id=identity,
        password=load_settings().cadrumo_dev_test_database_password.get_secret_value(),
        dek=dek,
        dek_epoch=b64encode(derive_test_bucket_key(profile_id, purpose="dek-epoch")[:16]).decode("ascii"),
        salt=derive_test_bucket_key(profile_id, purpose="password-salt")[:16],
    )
    create_context, decode_context = profile_authority_contexts()
    initial = create_user_profile_record(
        context=create_context,
        profile_id=profile_id,
        setup_state=ProfileSetupState.INCOMPLETE,
    )
    session = ProfileRecordSession.from_envelope(
        envelope=material.envelope, dek=dek, profile_decode_context=decode_context
    )
    try:
        ProfileCapsuleLifecycle().create(
            label=label,
            profile_id=identity,
            password_envelope=material.envelope,
            sentinel=material.sentinel,
            data_files={},
            initial_record=initial,
            record_session=session,
        )
    finally:
        session.close()


def _publish_replacement_sandbox_profile() -> None:
    """Publish the replacement, then restore the original documented login target."""
    _publish_sandbox_profile(profile_id=SANDBOX_REPLACEMENT_PROFILE_ID, label=SANDBOX_REPLACEMENT_PROFILE_LABEL)
    # Canonical capsule creation selects its new capsule. The first documented
    # logout still belongs to the original profile's real persisted receipt.
    ProfileCapsuleLifecycle().select(SANDBOX_PROFILE_ID)


@contextmanager
def _provisioned_sandbox_profile(*, published: bool = False) -> Generator[None]:
    """Publish the deterministic sandbox profile and hold its custody span open.

    Mirrors production exactly, so the sandbox introduces no parallel write
    path: a bucket root comes into existence only through capsule
    publication's atomic no-replace rename, and the facts are merged onto that
    published record through the same production writer. The injected fixed
    ``profile_id`` is what makes every profile-derived identifier in a frame's
    output deterministic across runs.

    Password custody is minted by the public custody owner using the existing
    synthetic dev-test password. The deterministic test DEK remains compatible
    with the shared session fixture; the real envelope can also authenticate a
    separately owned runtime worker. The session stays open for the whole
    current in-process sandbox span rather than just the facts merge.

    ``published`` is set when the storage root is a clone of a sandbox that
    already went through exactly this publication (:func:`_sandbox_template`):
    the profile exists on disk, so only its session is opened.
    """
    if published:
        with open_test_profile_session(SANDBOX_PROFILE_ID):
            yield
        return
    _publish_sandbox_profile(profile_id=SANDBOX_PROFILE_ID, label=SANDBOX_PROFILE_LABEL)
    # A settings override provides a route; it does not publish the durable
    # CLI default whose logout/delete walkthroughs observe real transitions.
    ProfileCapsuleLifecycle().select(SANDBOX_PROFILE_ID)
    with open_test_profile_session(SANDBOX_PROFILE_ID):
        from cadrumo.application.evidence.profile_legal_hold import LegalHoldCaseAuthority
        from cadrumo.application.filing.retention import try_record_filing_retention_snapshot

        record = upsert_test_profile_facts(SANDBOX_PROFILE_ID, _SANDBOX_PROFILE_FACTS)
        with bound_test_profile_record(SANDBOX_PROFILE_ID) as repository:
            repository.complete_setup(
                SANDBOX_PROFILE_ID,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
            )
        # A production registration records the empty filing catalogue. The
        # synthetic docs taxpayer also has an explicit empty legal-case
        # observation so its deletion walkthrough can exercise the real
        # fail-closed preflight without fabricating a hold bypass.
        observed_at = datetime.now(UTC)
        try_record_filing_retention_snapshot(
            bucket_id=SANDBOX_PROFILE_ID,
            records=(),
            observed_at=observed_at,
        )
        LegalHoldCaseAuthority().record_open_case_snapshot(
            profile_id=UUID(SANDBOX_PROFILE_ID),
            open_case_ids=(),
            observed_at=observed_at,
        )
        yield


#: The provisioned-at-rest sandbox state each later sandbox in this process is
#: cloned from, keyed by authority, synthetic password and temporary-root lifetime.
#: Neither the password nor its digest is exposed in transcripts or diagnostics.
_SANDBOX_TEMPLATES: dict[tuple[str, str, Path], Path] = {}
_SANDBOX_TEMPLATE_HOLDER: list[TemporaryDirectory[str]] = []


def _sandbox_template() -> Path:
    """Return a sandbox state directory with the profile already published.

    Publishing the sandbox profile (capsule, facts, setup, retention and
    legal-hold observations) is the same work for every sequence and was most
    of each sandbox's cost. It is done once per process and per authority
    generation and effective synthetic password, through the production writers,
    then closed so every file is at rest before it is copied. The shared test
    DEK depends only on the fixed profile identity, so it adds no settings input
    to this cache identity.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        generation = str(operation.generation)
    # Resolve under the same environment boundary as provisioning; an ambient
    # operator password must never enter the template identity or its custody.
    with _neutralized_ambient_env():
        password_digest = sha256_hex(load_settings().cadrumo_dev_test_database_password.get_secret_value().encode())
    temporary_root = prepare_temp_root().resolve()
    identity = (generation, password_digest, temporary_root)
    template = _SANDBOX_TEMPLATES.get(identity)
    if template is not None and template.is_dir():
        return template
    # A caller may end its temporary-root scope before this process ends.
    # Rebuild an absent owned template through the same capsule publication;
    # failures copying a present template still propagate normally.
    _SANDBOX_TEMPLATES.pop(identity, None)
    holder = TemporaryDirectory(prefix="cadrumo-docs-sandbox-template-", dir=temporary_root)
    _SANDBOX_TEMPLATE_HOLDER.append(holder)
    template = Path(holder.name)
    dispose_engine()
    close_active_bucket_session()
    with (
        _neutralized_ambient_env(),
        _isolated_external_tool_env(template),
        _absent_credential_vault(),
        override_settings(
            cadrumo_output_language="en",
        ),
        isolated_profile_storage_root(tmp_path=template),
        composed_profile_persistence_ports(),
        _isolated_diagnostic_log(),
        frozen_clock(SANDBOX_INSTANT),
        _provisioned_sandbox_profile(),
    ):
        pass
    close_active_bucket_session()
    dispose_engine()
    _SANDBOX_TEMPLATES[identity] = template
    return template


#: Environment prefixes scrubbed from the process environment for the whole
#: sandbox scope: the operator's ambient ``CADRUMO_*`` / ``AEAT_*`` machine
#: state (auth credentials, Cl@ve identifiers, live opt-ins, machine-local
#: paths) must never be observable by a docs sequence execution — both a
#: privacy boundary (``sensitive-financial-data``) and a determinism one.
_SCRUBBED_ENV_PREFIXES: tuple[str, ...] = ("CADRUMO_", "AEAT_")

#: Deliberate pins that survive the scrub. ``CADRUMO_LOCAL_STORAGE_ROOT`` is
#: the process-level isolation seam itself (``ensure_isolated_storage_root``);
#: removing it would UNPIN the guard that keeps import-time settings resolution
#: off the operator's real product state. The English output pin rides
#: ``override_settings``, not the environment, so it needs no entry here.
_ENV_SCRUB_ALLOWLIST: frozenset[str] = frozenset({"CADRUMO_LOCAL_STORAGE_ROOT"})


@contextmanager
def _neutralized_ambient_env() -> Generator[None]:
    """Remove ambient ``CADRUMO_*`` / ``AEAT_*`` env vars for the scope.

    Settings resolution inside the sandbox re-reads the process environment on
    every :class:`Settings` instantiation, so any operator-exported variable
    would otherwise flow straight into sandboxed frame executions. Everything
    removed is restored verbatim on exit. This is now the SOLE operator-state
    channel this sandbox must close: production :class:`~cadrumo.core.config.Settings`
    carries no dotenv source of its own (``settings_customise_sources`` never
    returns one), so the only remaining route for a development ``env/.env``
    value to reach a test process is the repo-root ``conftest.py`` bridge
    (:func:`~cadrumo.tests.env_loader.bridge_env_file_into_environ`), which
    applies each pair to ``os.environ`` via ``setdefault`` at collection time.
    By the time this scope runs, a bridged value is byte-for-byte
    indistinguishable from a real ambient ``CADRUMO_*`` / ``AEAT_*`` variable —
    so scrubbing the ambient environment here closes that route too.
    """
    removed: dict[str, str] = {}
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(_SCRUBBED_ENV_PREFIXES) and upper not in _ENV_SCRUB_ALLOWLIST:
            removed[key] = os.environ.pop(key)
    try:
        yield
    finally:
        os.environ.update(removed)


@contextmanager
def _isolated_external_tool_env(sandbox_root: Path) -> Generator[None]:
    """Pin external-tool discovery to empty sandbox-owned directories.

    ``PATH`` and the Playwright browser cache are workstation state just as
    surely as ``CADRUMO_*`` settings are. Sequence execution must not discover
    a contributor's provider CLIs or browser installation, so real probes see
    stable absence with their real remediation while the process environment
    is restored verbatim afterwards.
    """
    # Keep these beneath the sequence workdir so the existing golden path
    # normaliser rewrites their per-run root to ``<sandbox-workdir>``.
    empty_bin = sandbox_root / "workdir" / ".external-tools"
    empty_browsers = sandbox_root / "workdir" / ".playwright-browsers"
    empty_bin.mkdir(parents=True, exist_ok=True)
    empty_browsers.mkdir(parents=True, exist_ok=True)
    # The product resolves its managed browser root from its own setting rather
    # than Playwright's variable, so both are pinned to the same empty directory.
    pins = {
        "PATH": str(empty_bin),
        "PLAYWRIGHT_BROWSERS_PATH": str(empty_browsers),
        "CADRUMO_PLAYWRIGHT_BROWSERS_DIR": str(empty_browsers),
    }
    previous = {key: os.environ.get(key) for key in pins}
    os.environ.update(pins)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _isolated_diagnostic_log() -> Generator[None]:
    """Bind diagnostic file logging to THIS sequence's own storage root.

    Mirrors :func:`dev.docs.build.ensure_private_diagnostic_log`'s reasoning one
    level down: that function re-points the shared handler once per PROCESS so
    concurrent processes cannot contend for one file. It never runs again per
    sequence, so every sequence sharing a process (a full docs build, or a
    multi-sequence ``--page`` check) still funnels DEBUG records into whichever
    file the FIRST sequence in that process happened to bind — the module
    docstring's "sequences never share state" claim was false for the log
    channel alone. A ``config repair logs`` frame then tails a file carrying
    other sequences' temp paths and timestamps, which no golden can pin.

    Must be entered AFTER :func:`~cadrumo.adapters.persistence.storage.tests.secure_sql.isolated_profile_storage_root`
    so the derived path below is rooted under THIS sequence's own storage root,
    not the process default.

    An explicit ``override_settings(cadrumo_log_dir=...)`` here, not reliance on
    ``cadrumo_local_storage_root``'s automatic re-derivation
    (:data:`~cadrumo.core.storage_taxonomy_locations.ROOT_DERIVED_STORAGE_FIELDS`):
    :func:`dev.docs.build.ensure_private_diagnostic_log` already set
    ``CADRUMO_LOG_DIR`` explicitly at PROCESS start, so the process-wide
    :class:`~cadrumo.core.config.Settings` carries ``cadrumo_log_dir`` in its
    own ``model_fields_set`` — and ``override_settings`` preserves a field
    already marked explicit through every later override precisely because
    that is the correct behaviour for a genuine operator override. It cannot
    distinguish that case from this one, so the field must be re-set
    explicitly here rather than left to re-derive. Rebinding through the
    ``CADRUMO_LOG_DIR`` environment variable has no effect inside the sandbox:
    :func:`~cadrumo.core.config.load_settings` returns the frozen override
    object regardless of environment changes.
    """
    from cadrumo.core.logging import configure_logging

    from ..logging_rebind import allow_logging_reconfiguration

    log_dir = Path(load_settings().cadrumo_local_storage_root) / "logs"
    settings_context = override_settings(cadrumo_log_dir=str(log_dir))
    settings_context.__enter__()
    allow_logging_reconfiguration()
    configure_logging()
    try:
        yield
    finally:
        settings_context.__exit__(None, None, None)
        # Release the latch and leave it unconfigured rather than eagerly
        # rebinding: this sequence's temporary directory is about to be torn
        # down, and the next sequence's own entry reconfigures fresh against
        # its own root. Nothing logs in the gap between sequences.
        allow_logging_reconfiguration()


@contextmanager
def _absent_credential_vault() -> Generator[None]:
    """Pin the OS credential vault to a stable absence for the scope.

    The host's credential vault is workstation state exactly as ``PATH`` and the
    Playwright cache are (:func:`_isolated_external_tool_env`), and it is the one
    such channel that reaches OPERATOR-VISIBLE OUTPUT: ``config login`` custodies
    its session key through :mod:`keyring`, so on a vault-bearing host the login
    envelope carries ``session_persisted: true``, while on a headless CI runner
    the same frame emits the ``config.login.session_not_persisted`` warning and a
    ``warning`` spine status. A golden built from either side is therefore
    unstable BY CONSTRUCTION — it encodes the capturing machine, and flips as
    soon as a differently-postured machine runs the gate.

    Pinning absence resolves that without blocking ordinary frames: every host now
    executes the documented path a machine with no usable vault takes, so the
    frames stay executed truth and the golden is a property of the sandbox rather
    than of the contributor's workstation. Absence is the default: a native vault-bearing path
    WRITES a real wrapped session key into the operator's own credential store
    (measured: a ``cadrumo:profile-session`` entry under a per-run sandbox bucket
    id, surviving the run), which a hermetic docs sandbox must never do. The
    explicit sign-out journeys layer an ephemeral synthetic shared receipt store
    over this default; they never select the workstation's credential provider.

    Both resolution channels are closed, because both are live: the environment
    variable covers the subprocess execution paths, and
    :func:`keyring.set_keyring` covers the in-process one — :mod:`keyring` caches
    its detected backend in a module global, so the environment variable ALONE is
    a no-op once anything in the process has already resolved a backend. The
    previous backend is restored verbatim on exit; ``None`` restores the
    not-yet-detected state so the next detection re-runs normally.
    """
    pins = {"PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring"}
    previous_env = {key: os.environ.get(key) for key in pins}
    previous_backend = keyring.core._keyring_backend
    os.environ.update(pins)
    keyring.set_keyring(keyring.backends.null.Keyring())
    try:
        yield
    finally:
        keyring.core._keyring_backend = previous_backend
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def sequence_sandbox(
    *,
    sequence_id: str,
    sandbox_root: Path,
    fixtures_root: Path | None = None,
    enrolled_sequence_ids: Sequence[str] | None = None,
) -> Generator[SequenceSandbox]:
    """Open one hermetic per-sequence sandbox under ``sandbox_root``.

    Inside the scope: an isolated real-crypto storage root, the frozen
    :data:`SANDBOX_INSTANT`, the deterministic :data:`SANDBOX_PROFILE_ID`
    registered and active, ``cadrumo_output_language`` pinned to English, the
    operator's ambient ``CADRUMO_*`` / ``AEAT_*`` environment scrubbed for the
    whole scope (restored on exit; the storage-root isolation pin survives), the
    OS credential vault pinned absent so a ``config login`` frame's output is a
    property of the sandbox rather than of the host machine
    (:func:`_absent_credential_vault`),
    and the process working directory moved to a scratch ``workdir`` seeded
    with a copy of the committed synthetic fixtures — so a frame's relative
    ``fixtures/...`` input reads the committed artifact's copy and a frame's
    relative ``--output`` lands inside the sandbox, never in the repository.

    Any bound bucket session is evicted on BOTH edges of the scope, so a
    ``config login`` frame's deliberately unscoped session binding cannot
    outlive the sandbox that opened it and poison the next one.

    Args:
        sequence_id: The owning sequence id, for failure messages.
        sandbox_root: An empty per-sequence directory the sandbox owns.
        fixtures_root: The committed fixtures tree to copy into the workdir;
            defaults to :func:`default_fixtures_root` (skipped when absent).
        enrolled_sequence_ids: Executable scenarios sharing a cumulative page
            sandbox. Their explicit sign-out enrollment selects receipt custody
            before the worker starts; omitted for an isolated sequence.

    Yields:
        The open :class:`SequenceSandbox`.
    """
    # Importing the application resolves the product storage root; a machine
    # carrying retired product state must never red (or leak into) a docs
    # sequence run, so pin the process-level scratch root first — exactly the
    # docs-build isolation seam. Deferred import: ``dev.docs.build`` is a CLI
    # tool module, not an engine dependency.
    from ..build import ensure_isolated_storage_root

    ensure_isolated_storage_root()
    _refuse_live_opt_in(sequence_id)
    persistent_sign_in = requires_persistent_sign_in(
        (sequence_id,) if enrolled_sequence_ids is None else enrolled_sequence_ids
    )
    workdir = sandbox_root / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    fixtures = fixtures_root if fixtures_root is not None else default_fixtures_root()
    if fixtures.is_dir():
        shutil.copytree(fixtures, workdir / "fixtures", dirs_exist_ok=True)
    _seed_m303_filing_evidence(workdir / "fixtures")
    shutil.copytree(_sandbox_template(), sandbox_root, dirs_exist_ok=True)

    dispose_engine()
    # A login frame binds its BucketSession UNSCOPED (``bind_active_bucket_session``)
    # so the session outlives the CLI call — correct for a real operator, whose
    # every command is its own process. This engine invokes the CLI IN-PROCESS, so
    # without an explicit eviction that binding survives sandbox teardown: the next
    # sandbox's root callback short-circuits on ``has_active_bucket_session()``
    # instead of resuming for its own bucket, and the storage runtime then
    # (correctly) refuses every profile-bound verb because the route bucket (this
    # sandbox's pointer) is not the session bucket (the previous sandbox's). The
    # stale session also holds an engine handle on the torn-down sandbox's
    # database. Evicting on BOTH edges also covers a sandbox that raised.
    close_active_bucket_session()
    with (
        _neutralized_ambient_env(),
        _isolated_external_tool_env(sandbox_root),
        _absent_credential_vault(),
        # The docs sandbox runs genuinely zero-auth: per the operator ruling,
        # auth-provider readiness binds only live/AEAT-touching purposes, never
        # the local build/calculate/verify/file/export flow the sequences drive.
        # A taxpayer with no auth provider configured completes the whole local
        # artefact flow, and the docs gates prove that ruled behaviour in CI.
        override_settings(
            cadrumo_output_language="en",
        ),
        isolated_profile_storage_root(tmp_path=sandbox_root),
        composed_profile_persistence_ports(),
        # This engine invokes the Click command directly, so it is the host that
        # must compose what the ``aeat`` console script composes. Conversions
        # read the RECORDED ECB answers rather than the live provider the
        # console script binds: a sandbox that reached the network would make
        # every golden depend on the day's reference rates.
        bind_exchange_rate_provider_factory(recorded_ecb_rate_provider),
        _isolated_diagnostic_log(),
        frozen_clock(SANDBOX_INSTANT),
        chdir(workdir),
        _provisioned_sandbox_profile(published=True),
        sequence_receipt_store(Path(load_settings().cadrumo_local_storage_root), enabled=persistent_sign_in),
    ):
        if enrolled_sequence_ids is None and sequence_id == "profile-setup-delete":
            _publish_replacement_sandbox_profile()
        with sequence_runtime(
            Path(load_settings().cadrumo_local_storage_root),
            signed_in_profile=UUID(SANDBOX_PROFILE_ID) if persistent_sign_in else None,
        ):
            effective_settings = load_settings()
            try:
                yield SequenceSandbox(
                    storage_root=Path(effective_settings.cadrumo_local_storage_root),
                    workdir=workdir.resolve(),
                    profile_id=SANDBOX_PROFILE_ID,
                    frozen_instant=SANDBOX_INSTANT,
                )
            finally:
                close_active_bucket_session()
