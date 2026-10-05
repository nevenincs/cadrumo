"""Real-behaviour tests for the per-sequence hermetic sandbox runner.

Runtime journeys drive the REAL Cadrumo CLI in-process against a fresh
real-crypto sandbox (genuine ``bucket-dek-v1`` bucket, encrypted SQLite,
frozen clock, injected deterministic profile id). The worked chain is the Modelo 130 lifecycle: ``work
create`` → ``work calculate`` (with real registry bindings) → ``work verify``,
whose verify gate genuinely refuses without clean cross-period evidence, so the
terminal ``@result`` frame exercises a real declared non-zero exit.

Determinism observation (formalised by this anti-tautology gate): two
executions of the chain in fresh sandboxes produced ZERO pre-mask differing
JSON paths and byte-identical raw outputs — with the clock frozen and the
profile id injected, the work-unit and calculation-revision ids are
content-addressed and every timestamp is pinned, so the residual
non-deterministic surface of this chain is empty (trivially within the central
``GOLDEN_MASK_FIELDS``). The test pins that observation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import JsonValue, SecretStr

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession, ProfileRecordStore
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from cadrumo.core.bucket_pointer import read_pointer_selection
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER, redact_structured_for_cli_output
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.env_scope import scoped_env_var
from cadrumo.tests.golden_comparison import GOLDEN_MASK_FIELDS, differing_field_names, differing_paths

from ..errors import SequenceExecutionError
from ..parser import parse_sequence
from ..runner import SANDBOX_PROFILE_ID, SequenceTranscript, execute_page_sequences, execute_sequence, sequence_sandbox
from ..runtime_fixture import SANDBOX_INSTANT
from ..schema import FrameKind, ParsedSequence

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_FAKE_SESSION_ENV_NAME = "AEAT_FAKE_SESSION_TOKEN"

#: A real create → calculate → verify chain over Modelo 130 2025 1T. The verify
#: gate refuses (cross-period evidence is absent in a fresh sandbox), so the
#: result frame declares the non-zero exit and asserts the refusal semantically.
_CHAIN_BODY = "\n".join(
    [
        "aeat --format json app modelo work create --modelo 130 --year 2025 --period 1T",
        "@capture work_unit_id result.work_unit_id",
        "aeat --format json app modelo work calculate {work_unit_id}"
        " --binding irpf.previous_year_economic_activity_net_income=13000"
        " --binding modelo-130-resultados-negativos-anteriores=0",
        "@capture calculation_revision_id result.calculation_revision_id",
        "@result aeat --format json app modelo work verify {calculation_revision_id}",
        "@expect result.granted_verificado_completo == false",
        "@expect exit_code == 1",
    ],
)


def _envelope_result(envelope: dict[str, JsonValue] | None) -> dict[str, JsonValue]:
    """Return one envelope's ``result`` object, proving the envelope carries one.

    An envelope is typed as free JSON, so ``result`` is an object only once
    something checks. Checking here names the wrong shape instead of indexing
    into whatever the frame happened to carry.
    """
    if envelope is None:
        raise AssertionError("frame carries no JSON envelope")
    result = envelope["result"]
    if not isinstance(result, dict):
        raise AssertionError("envelope result is not an object")
    return result


def _chain_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="runner-m130-chain",
        options={"verify": "Verify the calculation before exporting."},
        body=_CHAIN_BODY,
    )


def _result_sequence(body: str, *, sequence_id: str = "runner-refusal-case") -> ParsedSequence:
    """Parse a minimal structurally-valid sequence around ``body``'s frames."""
    return parse_sequence(
        sequence_id=sequence_id,
        options={"verify": "Verify the command completed."},
        body=body,
    )


def _profile_seed_sequence(
    seeds_root: Path,
    sequence_id: str,
    *,
    seed: str = "active-profile",
) -> ParsedSequence:
    """Build one real read-only body around a seed capture used by its argv."""
    return parse_sequence(
        sequence_id=sequence_id,
        options={"verify": "Verify the seeded profile is readable.", "seed": seed},
        body=('@result aeat --format json config profile history {profile_label}\n@expect status == "success"\n'),
        seeds_root=seeds_root,
    )


def test_sandbox_publishes_a_profile_capsule(tmp_path: Path) -> None:
    """The docs sandbox publishes a usable isolated profile capsule."""
    with sequence_sandbox(sequence_id="canonical-capsule-runtime", sandbox_root=tmp_path / "scope") as sandbox:
        assert sandbox.profile_id == SANDBOX_PROFILE_ID
        assert (sandbox.storage_root / "buckets" / SANDBOX_PROFILE_ID).is_dir()
        assert read_pointer_selection(sandbox.storage_root).bucket_id == SANDBOX_PROFILE_ID


def test_sandbox_password_custody_authenticates_and_decrypts_each_template_clone(tmp_path: Path) -> None:
    """The fixed fixture identity has genuine password custody in every cloned root."""
    records: list[UserProfileRecord] = []
    roots: list[Path] = []
    envelope_digests: list[str] = []
    for name in ("first", "second"):
        with sequence_sandbox(sequence_id=f"password-custody-{name}", sandbox_root=tmp_path / name) as sandbox:
            roots.append(sandbox.storage_root)
            material = load_profile_custody_password_material(UUID(SANDBOX_PROFILE_ID), root=sandbox.storage_root)
            password = load_settings().cadrumo_dev_test_database_password.get_secret_value()
            with pytest.raises(ProfileCustodyPasswordError):
                unlock_profile_custody_password(material, password=f"{password}-incorrect")
            unlocked = unlock_profile_custody_password(material, password=password)
            assert unlocked.profile_id == UUID(SANDBOX_PROFILE_ID)
            assert unlocked.envelope_digest == material.envelope.self_digest
            _, decode_context = profile_authority_contexts()
            session = ProfileRecordSession.from_envelope(
                envelope=material.envelope, dek=unlocked.dek, profile_decode_context=decode_context
            )
            try:
                record = ProfileRecordStore(session=session, root=sandbox.storage_root).load().record
                assert record.profile_id == SANDBOX_PROFILE_ID
                assert record.setup_state is ProfileSetupState.COMPLETE
                facts = {fact.path: fact.value for fact in record.facts}
                assert facts["identity.tax_id"] == "12345678Z"
                assert facts["tax_residence.jurisdiction_scope"] == "common_regime"
                assert facts["iva.regime"] == "GENERAL"
                records.append(record)
                envelope_digests.append(material.envelope.self_digest)
            finally:
                session.close()
            assert session.closed
    assert roots[0] != roots[1]
    assert records[0] == records[1]
    assert envelope_digests[0] == envelope_digests[1]


def test_sandbox_runtime_admits_fresh_password_and_releases_real_profile_view(tmp_path: Path) -> None:
    """The installed opener reaches an encrypted worker with the fixture's clock."""
    # An incorrect proof creates a canonical login-throttle record. Keep that
    # negative case in its own root: the positive scope has the same frozen
    # instant, and must not bypass or artificially expire that record.
    with sequence_sandbox(sequence_id="native-password-refusal", sandbox_root=tmp_path / "refusal"):
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(SANDBOX_PROFILE_ID), frontend=OperationFrontendProjection.CLI)
        )
        incorrect = bytearray(
            (load_settings().cadrumo_dev_test_database_password.get_secret_value() + "-incorrect").encode()
        )
        try:
            with pytest.raises(RuntimeFrontendRefusedError) as refused:
                client.login_password(incorrect)
            assert refused.value.reason == AutomationCustodyCode.CREDENTIAL_REJECTED.value
            assert incorrect == bytearray(len(incorrect))
        finally:
            client.close()

    with sequence_sandbox(sequence_id="native-profile-view", sandbox_root=tmp_path / "native"):
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(SANDBOX_PROFILE_ID), frontend=OperationFrontendProjection.CLI)
        )
        proof = bytearray(load_settings().cadrumo_dev_test_database_password.get_secret_value().encode())
        try:
            admitted = client.login_password(proof)
            assert admitted.status.profile_id == UUID(SANDBOX_PROFILE_ID)
            assert admitted.status.credential_authenticated
            assert admitted.human_login is not None
            assert admitted.human_login.authenticated_at == SANDBOX_INSTANT
            assert not admitted.human_login.session_persisted
            assert not admitted.human_login.resumed
            assert proof == bytearray(len(proof))
            # These canonical pages are executed and decrypted in the child,
            # rather than reading the runner's bootstrap bucket session.
            from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind

            view = client.read_profile_view((ProfileViewPageKind.FACTS,))
            facts = {
                item.path: item.value
                for item in view.items(ProfileViewPageKind.FACTS)
                if isinstance(item, ProfileViewFactItem)
            }
            assert facts["identity.tax_id"] == "12345678Z"
            assert facts["tax_residence.jurisdiction_scope"] == "common_regime"
        finally:
            client.close()


def test_sequence_profile_view_uses_fresh_runtime_proof_and_exact_profile(tmp_path: Path) -> None:
    """An authored CLI frame gets its canonical profile projection from the worker."""
    sequence = _result_sequence(
        "@result aeat --format json config profile view\n"
        f'@expect result.profile_id == "{SANDBOX_PROFILE_ID}"\n'
        '@expect result.setup_state == "complete"\n'
        "@expect exit_code == 0\n",
        sequence_id="runtime-cli-profile-view",
    )
    transcript = execute_sequence(sequence, sandbox_root=tmp_path / "runtime-cli")
    result = _envelope_result(transcript.frames[0].envelope)
    facts = result["facts"]
    assert isinstance(facts, list)
    # Public CLI output applies canonical personal-identifier redaction. Derive
    # the expected fact from the known fixture, never from captured output.
    expected_fact = redact_structured_for_cli_output({"path": "identity.tax_id", "value": "12345678Z"})
    assert expected_fact["value"] != "12345678Z"
    assert expected_fact in facts


def test_sandbox_template_tracks_current_scoped_password_and_rejects_previous_password(tmp_path: Path) -> None:
    """A prior cached template cannot silently impose its password on a later scope."""
    first = f"docs-fixture-first-{tmp_path.name}"
    second = f"docs-fixture-second-{tmp_path.name}"
    records: list[UserProfileRecord] = []
    envelope_digests: list[str] = []
    for index, (password, previous) in enumerate(((first, second), (second, first), (first, second))):
        with (
            override_settings(cadrumo_dev_test_database_password=SecretStr(password)),
            sequence_sandbox(sequence_id=f"scoped-password-{index}", sandbox_root=tmp_path / str(index)) as sandbox,
        ):
            material = load_profile_custody_password_material(UUID(SANDBOX_PROFILE_ID), root=sandbox.storage_root)
            with pytest.raises(ProfileCustodyPasswordError):
                unlock_profile_custody_password(material, password=previous)
            unlocked = unlock_profile_custody_password(material, password=password)
            assert unlocked.profile_id == UUID(SANDBOX_PROFILE_ID)
            _, decode_context = profile_authority_contexts()
            session = ProfileRecordSession.from_envelope(
                envelope=material.envelope, dek=unlocked.dek, profile_decode_context=decode_context
            )
            try:
                record = ProfileRecordStore(session=session, root=sandbox.storage_root).load().record
                assert record.profile_id == SANDBOX_PROFILE_ID
                assert record.setup_state is ProfileSetupState.COMPLETE
                assert UserProfileFact(path="identity.tax_id", value="12345678Z") in record.facts
                records.append(record)
                envelope_digests.append(material.envelope.self_digest)
            finally:
                session.close()
            assert session.closed
    assert records[0] == records[1] == records[2]
    assert envelope_digests[0] != envelope_digests[1]
    assert envelope_digests[0] == envelope_digests[2]


def test_logout_then_delete_uses_durable_pointer_not_the_sandbox_override(tmp_path: Path) -> None:
    """The exact delete leaf can remove only the logged-out synthetic profile."""
    sequence = _result_sequence(
        "aeat --format json config logout\n"
        '@expect status == "success"\n'
        "@result aeat --format json config profile delete docs-sequence-sandbox --yes\n"
        "@expect result.deleted == true\n"
        "@expect exit_code == 0\n",
        sequence_id="runner-logout-delete",
    )

    transcript = execute_sequence(sequence, sandbox_root=tmp_path / "delete")

    assert _envelope_result(transcript.frames[0].envelope)["logged_out_profile"] == CLI_PROFILE_ID_PLACEHOLDER
    assert _envelope_result(transcript.frames[0].envelope)["already_logged_out"] is False
    assert _envelope_result(transcript.result_frame.envelope)["deleted"] is True
    assert read_pointer_selection(Path(transcript.storage_root)).bucket_id is None
    assert not (Path(transcript.storage_root) / "buckets" / SANDBOX_PROFILE_ID).exists()


class TestPageSeedLifecycle:
    """Named setup executes once per page while isolated runs stay self-contained."""

    @staticmethod
    def _write_seed(seeds_root: Path) -> None:
        seeds_root.mkdir(parents=True)
        (seeds_root / "active-profile.seq").write_text(
            "@setup aeat --format json config profile list\n@capture profile_label result.active_profile\n",
            encoding="utf-8",
        )

    def test_page_reuses_equivalent_seed_execution_and_capture(self, tmp_path: Path) -> None:
        seeds_root = tmp_path / "seeds"
        self._write_seed(seeds_root)
        first = _profile_seed_sequence(seeds_root, "page-seed-first")
        second = _profile_seed_sequence(seeds_root, "page-seed-second")

        with pytest.warns(UserWarning, match="would replay seed 'active-profile'.*immutable captures"):
            transcripts = execute_page_sequences(
                (first, second),
                label="how-to/page-seed",
                sandbox_root=tmp_path / "page",
            )

        assert len(transcripts) == 2
        assert transcripts[0].frames[0] == transcripts[1].frames[0]
        assert transcripts[0].captures["profile_label"] == "docs-sequence-sandbox"
        assert transcripts[1].captures["profile_label"] == "docs-sequence-sandbox"
        assert "docs-sequence-sandbox" in transcripts[1].result_frame.argv

    def test_isolated_execution_still_runs_its_own_seed(self, tmp_path: Path) -> None:
        seeds_root = tmp_path / "seeds"
        self._write_seed(seeds_root)
        sequence = _profile_seed_sequence(seeds_root, "isolated-seed")

        first = execute_sequence(sequence, sandbox_root=tmp_path / "isolated-a")
        second = execute_sequence(sequence, sandbox_root=tmp_path / "isolated-b")

        assert first.frames[0].kind is FrameKind.SETUP
        assert second.frames[0].kind is FrameKind.SETUP
        assert first.captures == second.captures == {"profile_label": "docs-sequence-sandbox"}

    def test_differently_named_execution_equivalent_seed_reuses_state(self, tmp_path: Path) -> None:
        seeds_root = tmp_path / "seeds"
        self._write_seed(seeds_root)
        (seeds_root / "active-profile-alias.seq").write_text(
            "@step Inspect the already active profile.\n"
            "@setup aeat --format json config profile list\n"
            "@capture profile_label result.active_profile\n",
            encoding="utf-8",
        )
        first = _profile_seed_sequence(seeds_root, "seed-canonical")
        alias = _profile_seed_sequence(seeds_root, "seed-equivalent-alias", seed="active-profile-alias")

        with pytest.warns(UserWarning, match="execution-equivalent.*instead of replaying side effects"):
            transcripts = execute_page_sequences(
                (first, alias),
                label="how-to/seed-alias",
                sandbox_root=tmp_path / "page",
            )

        assert transcripts[0].frames[0] == transcripts[1].frames[0]
        assert transcripts[1].captures["profile_label"] == "docs-sequence-sandbox"

    def test_same_seed_identity_with_divergent_definition_warns_and_refuses(self, tmp_path: Path) -> None:
        seeds_root = tmp_path / "seeds"
        self._write_seed(seeds_root)
        first = _profile_seed_sequence(seeds_root, "divergent-seed-first")
        second = _profile_seed_sequence(seeds_root, "divergent-seed-second")
        changed_seed = second.frames[0].model_copy(
            update={
                "command_line": "aeat --format json config profile show",
                "argv": ("aeat", "--format", "json", "config", "profile", "show"),
            },
        )
        divergent = second.model_copy(update={"frames": (changed_seed, *second.frames[1:])})

        with (
            pytest.warns(UserWarning, match="divergent definition"),
            pytest.raises(SequenceExecutionError, match=r"new seed identity.*structurally equivalent"),
        ):
            execute_page_sequences(
                (first, divergent),
                label="how-to/divergent-seed",
                sandbox_root=tmp_path / "divergent",
            )

    def test_seed_identity_without_inlined_state_warns_and_refuses(self, tmp_path: Path) -> None:
        body_only = _result_sequence(
            '@result aeat --format json config profile list\n@expect status == "success"\n',
            sequence_id="missing-seed-state",
        ).model_copy(update={"seed": "missing-state"})

        with (
            pytest.warns(UserWarning, match="no inlined seed frames are available"),
            pytest.raises(SequenceExecutionError, match="reparse the sequence from its contract"),
        ):
            execute_page_sequences(
                (body_only,),
                label="how-to/missing-seed-state",
                sandbox_root=tmp_path / "missing",
            )

    def test_page_seed_context_never_leaks_to_another_page(self, tmp_path: Path) -> None:
        seeds_root = tmp_path / "seeds"
        self._write_seed(seeds_root)
        sequence = _profile_seed_sequence(seeds_root, "page-local-seed")

        first_page = execute_page_sequences(
            (sequence,),
            label="how-to/page-a",
            sandbox_root=tmp_path / "page-a",
        )
        second_page = execute_page_sequences(
            (sequence,),
            label="how-to/page-b",
            sandbox_root=tmp_path / "page-b",
        )

        assert first_page[0].frames[0].kind is FrameKind.SETUP
        assert second_page[0].frames[0].kind is FrameKind.SETUP
        assert first_page[0].storage_root != second_page[0].storage_root


@pytest.fixture(scope="module")
def chain_transcript(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real chain execution shared by the inspection tests below."""
    root = tmp_path_factory.mktemp("chain-run-a")
    return execute_sequence(_chain_sequence(), sandbox_root=root)


class TestHermeticChainExecution:
    def test_chain_executes_all_frames_in_order(self, chain_transcript: SequenceTranscript) -> None:
        kinds = [frame.kind for frame in chain_transcript.frames]
        assert kinds == [FrameKind.COMMAND, FrameKind.COMMAND, FrameKind.RESULT]
        assert chain_transcript.profile_id == SANDBOX_PROFILE_ID
        assert chain_transcript.frames[0].exit_code == 0
        assert chain_transcript.frames[1].exit_code == 0

    def test_every_json_frame_records_its_envelope(self, chain_transcript: SequenceTranscript) -> None:
        for frame in chain_transcript.frames:
            assert frame.envelope is not None, frame.output
            # The recorded document is the real shared envelope spine.
            assert {"command", "status", "schema_version", "result", "notices"} <= set(frame.envelope)

    def test_captures_thread_real_ids_into_later_frames(self, chain_transcript: SequenceTranscript) -> None:
        create, calculate, verify = chain_transcript.frames

        work_unit_id = chain_transcript.captures["work_unit_id"]
        revision_id = chain_transcript.captures["calculation_revision_id"]

        # The captured values are the REAL ids the create/calculate envelopes carry.
        assert create.envelope is not None and calculate.envelope is not None
        create_result = create.envelope["result"]
        calculate_result = calculate.envelope["result"]
        assert isinstance(create_result, dict) and isinstance(calculate_result, dict)
        assert create_result["work_unit_id"] == work_unit_id
        assert calculate_result["calculation_revision_id"] == revision_id

        # ... and the later frames executed with those ids interpolated in argv.
        assert work_unit_id in calculate.argv
        assert revision_id in verify.argv
        # The authored line keeps its placeholder; only the executed argv resolves.
        assert "{work_unit_id}" in calculate.command_line
        assert "{calculation_revision_id}" in verify.command_line

    def test_declared_nonzero_exit_is_captured_not_fatal(self, chain_transcript: SequenceTranscript) -> None:
        verify = chain_transcript.result_frame
        assert verify.exit_code == 1  # declared via '@expect exit_code == 1'
        assert verify.envelope is not None
        result = verify.envelope["result"]
        assert isinstance(result, dict)
        assert result["granted_verificado_completo"] is False


#: The chain sequence executes three frames per run; both transcripts are
#: zipped and every determinism claim lives inside that zip.
_MINIMUM_CHAIN_FRAMES = 3


class TestSandboxIsolationAndDeterminism:
    def test_second_run_is_isolated_and_byte_deterministic(
        self,
        chain_transcript: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """A rerun in a fresh sandbox neither sees the first run's state nor drifts.

        Isolation and determinism are one assertion here: if any state leaked
        between the sandboxes, the second ``work create`` would resolve to the
        first run's existing unit as an idempotent no-op with an extra notice —
        a pre-mask envelope difference this comparison would surface.
        """
        rerun = execute_sequence(_chain_sequence(), sandbox_root=tmp_path / "chain-run-b")

        assert rerun.storage_root != chain_transcript.storage_root

        residual_paths: set[str] = set()
        residual_names: set[str] = set()
        # zip(..., strict=True) refuses a LENGTH MISMATCH, never two empty
        # sides: a run that produced no frame zips to zero iterations, the three
        # per-frame assertions never execute, and both residual sets stay empty.
        # Pinning ``residual_paths == frozenset()`` is the strong claim the
        # comment below describes, but frozenset() is exactly what an empty
        # transcript yields, and ``set() <= GOLDEN_MASK_FIELDS`` is always true.
        # Live: the chain executes three frames per run.
        assert len(chain_transcript.frames) >= _MINIMUM_CHAIN_FRAMES, (
            f"the first chain run produced {len(chain_transcript.frames)} frame(s); "
            "every determinism claim below is over the zipped pair and holds at zero"
        )
        assert len(rerun.frames) >= _MINIMUM_CHAIN_FRAMES, (
            f"the second chain run produced {len(rerun.frames)} frame(s); a rerun that "
            "executed nothing is not evidence of isolation or determinism"
        )
        for first, second in zip(chain_transcript.frames, rerun.frames, strict=True):
            assert first.envelope is not None and second.envelope is not None
            residual_paths |= differing_paths(first.envelope, second.envelope)
            residual_names |= differing_field_names(first.envelope, second.envelope)
            assert first.exit_code == second.exit_code
            # The raw outputs are byte-identical for this chain (observed and
            # pinned; this gate formalises the mask-honesty proof).
            assert first.output == second.output

        assert residual_paths == frozenset(), sorted(residual_paths)
        # Trivially within the central mask; pinned so a new residual field is
        # a loud, named regression rather than silent golden churn.
        assert residual_names <= GOLDEN_MASK_FIELDS

        assert rerun.captures == chain_transcript.captures


class TestSandboxEvictsBoundBucketSession:
    """A fixture's local bootstrap-session binding must not outlive its sandbox.

    The fixture
    :func:`~cadrumo.adapters.persistence.profile.tests.profile_registration.register_cli_profile`
    registers through ``register_profile_with_credentials`` and calls
    ``login_profile`` directly. Its unscoped local bucket session can survive
    that helper call, so sandbox teardown must evict it before the next fixture
    uses a different storage root. These assertions cover bootstrap fixture
    isolation; current CLI admission and runtime lease cleanup have separate
    native owning tests.
    """

    def test_fixture_bootstrap_binding_is_evicted_at_teardown(self, tmp_path: Path) -> None:
        """A real fixture session is bound inside and evicted outside the sandbox."""
        from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
        from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session

        assert current_active_bucket_session() is None, "a prior test leaked a bucket session"

        with sequence_sandbox(sequence_id="runner-session-leak", sandbox_root=tmp_path / "login"):
            register_cli_profile(label="me")

            # Anti-vacuity: the fixture really bound a session, and for a bucket
            # that is NOT this sandbox's injected profile — exactly the binding
            # that used to poison the next sandbox. Without this assertion the
            # post-teardown check below would pass on a run where nothing bound.
            bound = current_active_bucket_session()
            assert bound is not None
            assert bound.bucket_id != SANDBOX_PROFILE_ID

        assert current_active_bucket_session() is None

    def test_follower_sequence_serves_after_bootstrap_fixture_sandbox(self, tmp_path: Path) -> None:
        """A follower sequence still executes after the bootstrap fixture exits.

        The first sandbox binds a real local session for a different profile.
        The follower checks that this fixture state cannot prevent its command
        from completing in a fresh sandbox.
        """
        from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
        from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session

        with sequence_sandbox(sequence_id="runner-session-leak-a", sandbox_root=tmp_path / "leak-a"):
            register_cli_profile(label="me")
            leaked = current_active_bucket_session()
            assert leaked is not None
            assert leaked.bucket_id != SANDBOX_PROFILE_ID

        follower = execute_sequence(
            _result_sequence(
                "@result aeat --format json config auth diagnostics list\n@expect exit_code == 0\n",
                sequence_id="runner-session-leak-b",
            ),
            sandbox_root=tmp_path / "leak-b",
        )

        result_frame = follower.result_frame
        assert result_frame.exit_code == 0
        assert result_frame.envelope is not None
        assert result_frame.envelope["status"] == "success"


class TestLiveAeatRefusal:
    @pytest.mark.parametrize(
        "live_line",
        [
            "@setup aeat app live filed pull",
            "aeat app live iva-wallet pull-history",
            "aeat --format json app modelo reconcile pull some-work-unit",
        ],
    )
    def test_live_frames_are_refused_before_any_execution(self, live_line: str, tmp_path: Path) -> None:
        sequence = _result_sequence(
            f"{live_line}\n@result aeat config profile list\n@expect exit_code == 0\n",
            sequence_id="runner-live-refusal",
        )
        sandbox_root = tmp_path / "never-created"

        with pytest.raises(SequenceExecutionError, match="live-AEAT"):
            execute_sequence(sequence, sandbox_root=sandbox_root)

        # The refusal precedes the sandbox: nothing was provisioned or executed.
        assert not sandbox_root.exists()

    def test_option_value_spelled_like_a_pull_verb_is_not_flagged(self) -> None:
        """The scan skips option VALUES: '--file pull-history.csv' is a local
        file input, not a live verb (the reviewer-named false positive)."""
        from ..runner import live_aeat_tokens

        benign = _result_sequence(
            "@setup aeat app ledger import --file pull-history.csv\n"
            "@result aeat --format json config profile list\n"
            '@expect status == "success"\n',
            sequence_id="runner-option-value-scan",
        )
        assert live_aeat_tokens(benign.frames[0]) == ()


class TestStderrErrorDocument:
    def test_declared_refusal_records_the_stderr_error_envelope(self, tmp_path: Path) -> None:
        """A frame that fails via the stderr error-document path is a
        first-class transcript artifact: the error envelope (which shares the
        success spine) parses from stderr, ``envelope_source`` names the
        stream, and ``@expect`` json-paths evaluate against it."""
        missing_id = "deadbeef" * 8
        sequence = _result_sequence(
            f"aeat --format json app modelo work calculate {missing_id}\n"
            "@expect exit_code == 2\n"
            '@expect error.code == "REFUSED_CLI_BOUNDARY"\n'
            "@result aeat --format json config profile list\n"
            '@expect status == "success"\n',
            sequence_id="runner-stderr-envelope",
        )
        transcript = execute_sequence(sequence, sandbox_root=tmp_path / "stderr-envelope")

        refusal = transcript.frames[0]
        assert refusal.exit_code == 2
        assert refusal.stderr, "the refusal must carry the stderr error document"
        assert refusal.envelope is not None
        assert refusal.envelope_source == "stderr"
        error = refusal.envelope["error"]
        assert isinstance(error, dict)
        assert error["code"] == "REFUSED_CLI_BOUNDARY"

        success = transcript.result_frame
        assert success.envelope_source == "stdout"
        assert success.stderr == ""


class TestCaptureFailureDiagnostics:
    def test_capture_against_text_output_names_the_json_requirement(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat config profile list\n"
            "@capture profile_id result.profiles[0].profile_id\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-text-capture",
        )
        with pytest.raises(SequenceExecutionError, match="--format json"):
            execute_sequence(sequence, sandbox_root=tmp_path / "text-capture")

    def test_capture_path_missing_from_envelope_is_instructive(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat --format json config profile list\n"
            "@capture nope result.no_such_field\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-missing-path",
        )
        with pytest.raises(SequenceExecutionError, match=r"result\.no_such_field"):
            execute_sequence(sequence, sandbox_root=tmp_path / "missing-path")

    def test_undeclared_nonzero_exit_fails_fast_with_argv_and_output(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat --format json app modelo work create --modelo 130 --year 2025 --period 9T\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-undeclared-exit",
        )
        with pytest.raises(SequenceExecutionError, match="expected 0") as excinfo:
            execute_sequence(sequence, sandbox_root=tmp_path / "undeclared-exit")

        message = str(excinfo.value)
        assert "app modelo work create" in message  # the resolved argv
        assert "@expect exit_code ==" in message  # the instructive remedy


class TestNumericJsonPathResolution:
    """The digit-segment resolution rule of the json-path evaluator.

    An all-digit DOTTED segment is a string object key first (casilla numbers
    are JSON object keys) and a list index only when the node is a list; the
    bracketed form stays list-only. Both directions are pinned so neither can
    silently shadow the other.
    """

    def test_digit_segment_resolves_a_string_object_key(self) -> None:
        from ..runner import resolve_json_path

        document = {"result": {"casilla_values": {"03": "500.00", "01": "1000.00"}}}
        assert resolve_json_path(document, "result.casilla_values.03") == (True, "500.00")
        assert resolve_json_path(document, "result.casilla_values.01") == (True, "1000.00")
        assert resolve_json_path(document, "result.casilla_values.99") == (False, None)

    def test_digit_segment_resolves_a_list_index_when_the_node_is_a_list(self) -> None:
        from ..runner import resolve_json_path

        document = {"result": {"items": [{"id": "first"}, {"id": "second"}]}}
        assert resolve_json_path(document, "result.items.1.id") == (True, "second")
        assert resolve_json_path(document, "result.items.2.id") == (False, None)
        # The bracketed form remains the explicit list address for the same node.
        assert resolve_json_path(document, "result.items[0].id") == (True, "first")

    def test_bracket_form_never_indexes_an_object(self) -> None:
        from ..runner import resolve_json_path

        document = {"result": {"casilla_values": {"0": "zero-key"}}}
        assert resolve_json_path(document, "result.casilla_values[0]") == (False, None)
        assert resolve_json_path(document, "result.casilla_values.0") == (True, "zero-key")

    def test_bracket_quoted_segment_resolves_a_dotted_hyphenated_object_key(self) -> None:
        from ..runner import resolve_json_path

        # M349's declarante casillas are flat string keys carrying a literal dot
        # and hyphens; the dotted grammar would split on the dot, so the
        # bracket-quoted form is the only way to address them.
        document = {
            "result": {
                "casilla_values": {
                    "decl.importe-operaciones": "12345.00",
                    "decl.numero-operadores": "3",
                },
            },
        }
        assert resolve_json_path(document, 'result.casilla_values["decl.importe-operaciones"]') == (True, "12345.00")
        assert resolve_json_path(document, 'result.casilla_values["decl.numero-operadores"]') == (True, "3")
        # An absent quoted key misses cleanly.
        assert resolve_json_path(document, 'result.casilla_values["decl.nope"]') == (False, None)

    def test_bracket_quoted_segment_is_a_dict_key_never_a_list_index(self) -> None:
        from ..runner import resolve_json_path

        # On a list node the quoted form addresses no element and misses cleanly
        # (it is a literal object key only, never a list index).
        document = {"result": {"items": [{"id": "first"}, {"id": "second"}]}}
        assert resolve_json_path(document, 'result.items["0"]') == (False, None)
        # On a dict whose key is the digit string, the quoted form finds it.
        digit_key_doc = {"result": {"casilla_values": {"0": "zero-key"}}}
        assert resolve_json_path(digit_key_doc, 'result.casilla_values["0"]') == (True, "zero-key")

    def test_bracket_quoted_segment_on_a_non_dict_node_misses_cleanly(self) -> None:
        from ..runner import resolve_json_path

        # A quoted key applied to a scalar (non-Mapping, non-list) node returns
        # (False, None) rather than raising.
        document = {"result": {"status": "verified_complete"}}
        assert resolve_json_path(document, 'result.status["x"]') == (False, None)


class TestAmbientEnvNeutralisation:
    def test_ambient_operator_env_never_reaches_frame_execution(
        self,
        tmp_path: Path,
    ) -> None:
        """Operator machine state (ambient CADRUMO_*/AEAT_* env — Cl@ve
        credentials, live opt-ins) is scrubbed for the whole sandbox scope, so
        no frame execution can observe it; the storage-root isolation pin
        survives, and everything is restored verbatim on exit."""
        import os

        from ..runner import sequence_sandbox

        with (
            scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", "fake-operator-dni-99999999R"),
            scoped_env_var(_FAKE_SESSION_ENV_NAME, "fake-session-marker-do-not-leak"),
        ):
            observed: dict[str, str | None] = {}
            with sequence_sandbox(sequence_id="env-scrub-probe", sandbox_root=tmp_path / "scope"):
                observed["clave"] = os.environ.get("CADRUMO_CLAVE_MOVIL_DNI_NIE")
                observed["aeat"] = os.environ.get(_FAKE_SESSION_ENV_NAME)
                observed["pin"] = os.environ.get("CADRUMO_LOCAL_STORAGE_ROOT")

            # Inside the scope: operator vars gone, the isolation pin intact.
            assert observed["clave"] is None
            assert observed["aeat"] is None
            assert observed["pin"] is not None
            # Outside the sandbox scope but still under the export: restored verbatim.
            assert os.environ["CADRUMO_CLAVE_MOVIL_DNI_NIE"] == "fake-operator-dni-99999999R"
            assert os.environ[_FAKE_SESSION_ENV_NAME] == "fake-session-marker-do-not-leak"

    def test_external_tool_probes_are_pinned_to_stable_absence(self, tmp_path: Path) -> None:
        """A real browser probe cannot observe workstation installs.

        This probed the subprocess LLM providers as well, and that whole
        transport has since been deleted -- ``probe_subprocess_providers`` is a
        named member of the retired set that
        ``core/tests/test_cloud_transport_fully_deleted.py`` asserts stays
        gone. The import outlived it, so this case could not be COLLECTED and
        the pins below went unchecked on every run.

        Only the deleted half is dropped. What the case exists to prove is that
        the sandbox pins ``PATH`` and ``PLAYWRIGHT_BROWSERS_PATH`` beneath its
        own workdir, and both pins are still asserted here against a probe that
        really runs.
        """
        import os

        from cadrumo.application.provisioning_browser import probe_playwright_browser

        from ..runner import sequence_sandbox

        original_path = os.environ.get("PATH")
        with sequence_sandbox(sequence_id="external-tool-probe", sandbox_root=tmp_path / "scope"):
            browser = probe_playwright_browser()

            assert browser.available is False
            # ``remediation`` carried the fix as executable text and was
            # deliberately removed: ``DependencyStatus`` now closes an
            # unavailable outcome through the typed ``precondition_verdict``
            # instead, "without embedding presentation or executable text".
            # Asserting the verdict is present is asserting the contract the
            # model actually enforces, rather than a string it stopped holding.
            assert browser.precondition_verdict is not None
            # Both pins live BENEATH the sandbox workdir so the golden path
            # normaliser rewrites their per-run root to ``<sandbox-workdir>``.
            assert os.environ["PATH"] == str(tmp_path / "scope" / "workdir" / ".external-tools")
            assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(
                tmp_path / "scope" / "workdir" / ".playwright-browsers",
            )

        assert os.environ.get("PATH") == original_path

    def test_credential_vault_is_pinned_absent_on_every_host(self, tmp_path: Path) -> None:
        """A ``config login`` frame's output is a sandbox property, not a host one.

        ``config login`` custodies its session key through :mod:`keyring`, so on a
        vault-bearing workstation it reports ``session_persisted: true`` while a
        headless CI runner emits the ``session_not_persisted`` warning and a
        ``warning`` spine status. That made four committed goldens encode the
        CAPTURING MACHINE, flipping red whenever a differently-postured machine
        ran the gate. Pinning absence is what makes them stable, so this probe
        guards the pin from both sides.

        BOTH resolution channels are asserted because both are load-bearing and
        they fail differently: the environment variable is what subprocess
        execution paths read, while :func:`keyring.set_keyring` is what the
        in-process path needs — :mod:`keyring` caches its detected backend in a
        module global, so on any host where something resolved a backend before
        the sandbox opened (a pytest session, a docs build) the environment
        variable alone is inert. Asserting only the variable would therefore pass
        on a fresh process while the real gate still flapped.
        """
        import os

        import keyring
        import keyring.core

        from ..runner import sequence_sandbox

        host_backend = keyring.core._keyring_backend
        with sequence_sandbox(sequence_id="credential-vault-probe", sandbox_root=tmp_path / "scope"):
            assert os.environ["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
            # Probe the REAL custody call the login path uses, not the backend's
            # name: a write must reach nothing and read back absent, which is
            # what keeps the sandbox out of the operator's own credential store.
            keyring.set_password("cadrumo:probe", "sandbox-bucket", "must-not-be-retained")
            assert keyring.get_password("cadrumo:probe", "sandbox-bucket") is None

        # Restored verbatim: the pin must not leak into the rest of the session,
        # or every real keychain-custody test downstream would silently pass
        # against a no-op backend.
        assert keyring.core._keyring_backend is host_backend

    def test_frames_execute_green_and_leak_free_under_ambient_operator_env(
        self,
        tmp_path: Path,
    ) -> None:
        """A real sequence executes normally with fake operator env exported,
        and no frame's captured output carries the operator value — the
        end-to-end proof that docs builds never observe machine state."""
        operator_marker = "fake-operator-dni-99999999R"
        with scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", operator_marker):
            sequence = _result_sequence(
                "aeat --format json config profile list\n"
                "@result aeat --format json config profile list\n"
                '@expect status == "success"\n',
                sequence_id="runner-env-scrub",
            )
            transcript = execute_sequence(sequence, sandbox_root=tmp_path / "run")

        for frame in transcript.frames:
            assert frame.exit_code == 0
            assert operator_marker not in frame.output
            assert operator_marker not in frame.stderr

    def test_bridged_dotenv_value_never_reaches_frame_execution(
        self,
        tmp_path: Path,
    ) -> None:
        """The historical second operator-state channel — the project dotenv
        (``env/.env``, once loaded by pydantic-settings via an ABSOLUTE path
        independent of ``os.environ``) — no longer exists in production:
        ``Settings.settings_customise_sources`` never returns a dotenv source,
        regardless of ``model_config["env_file"]``. The one surviving route for
        an ``env/.env``-declared value to reach a process is the repo-root
        ``conftest.py`` bridge (:func:`cadrumo.tests.env_loader.bridge_env_file_into_environ`),
        which parses a real dotenv file and applies each pair to ``os.environ``
        via ``setdefault`` before any test runs. This drives that REAL bridge
        function against a synthetic dotenv file (anti-vacuity: the bridge is
        proven to genuinely land the pair in ``os.environ``, not assumed), then
        proves the bridged value — now indistinguishable from a genuinely
        ambient ``CADRUMO_*`` variable — is scrubbed by the same
        ``_neutralized_ambient_env`` seam :class:`TestAmbientEnvNeutralisation`'s
        other probes exercise directly, end to end through a real sequence run."""
        import os

        from cadrumo.tests.env_loader import bridge_env_file_into_environ

        from ..runner import sequence_sandbox

        operator_marker = "fake-operator-dni-77777777H"
        env_var_name = "CADRUMO_CLAVE_MOVIL_DNI_NIE"
        scripted_dotenv = tmp_path / "scripted.env"
        scripted_dotenv.write_text(f"{env_var_name}={operator_marker}\n", encoding="utf-8")

        # A real host may already carry this var (bridged from the host's own
        # env/.env), so the prior value — present or absent — is saved and
        # restored rather than assumed clean, exactly as scoped_env_var does.
        had_prior = env_var_name in os.environ
        prior_value = os.environ.get(env_var_name)
        os.environ.pop(env_var_name, None)
        try:
            # Anti-vacuity: the bridge is a real parser + os.environ writer, not
            # a stand-in — prove it genuinely lands the pair before trusting
            # anything downstream of it. ``setdefault`` semantics mean this
            # only takes effect because the slot was just cleared above.
            bridged = bridge_env_file_into_environ(scripted_dotenv)
            assert bridged == {env_var_name: operator_marker}
            assert os.environ[env_var_name] == operator_marker

            with sequence_sandbox(sequence_id="dotenv-bridge-probe", sandbox_root=tmp_path / "scope"):
                assert os.environ.get(env_var_name) is None

            # Restored outside the sandbox scope: the bridged value persists in
            # the ambient environment exactly like a real operator export would.
            assert os.environ[env_var_name] == operator_marker

            # End to end: a real sequence executes green and no frame observes it.
            sequence = _result_sequence(
                "aeat --format json config profile list\n"
                "@result aeat --format json config profile list\n"
                '@expect status == "success"\n',
                sequence_id="runner-dotenv-bridge-scrub",
            )
            transcript = execute_sequence(sequence, sandbox_root=tmp_path / "run")
            for frame in transcript.frames:
                assert frame.exit_code == 0
                assert operator_marker not in frame.output
                assert operator_marker not in frame.stderr
        finally:
            if had_prior:
                assert prior_value is not None
                os.environ[env_var_name] = prior_value
            else:
                os.environ.pop(env_var_name, None)
