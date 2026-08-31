"""Real-behaviour tests for the per-sequence hermetic sandbox runner.

Every test drives the REAL Cadrumo CLI in-process against a fresh
real-crypto sandbox (genuine ``bucket-dek-v1`` bucket, encrypted SQLite,
frozen clock, injected deterministic profile id) — no mocks, no skips, no
seeded stand-ins. The worked chain is the Modelo 130 lifecycle: ``work
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

from pathlib import Path

import pytest

from cadrumo.core.observability.golden import GOLDEN_MASK_FIELDS, differing_field_names, differing_paths
from cadrumo.tests.env_scope import scoped_env_var

from .. import (
    SANDBOX_PROFILE_ID,
    FrameKind,
    ParsedSequence,
    SequenceTranscript,
    execute_page_sequences,
    execute_sequence,
    parse_sequence,
    sequence_sandbox,
)
from ..errors import SequenceExecutionError

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

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
        body=('@result aeat --format json config profile show {profile_label}\n@expect status == "success"\n'),
        seeds_root=seeds_root,
    )


def test_sandbox_publishes_through_canonical_capsule_runtime(tmp_path: Path) -> None:
    """The docs runner must consume the relocated capsule owner, never its retired facade."""
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
        publish_test_profile_capsule as canonical_publish,
    )

    from .. import _runner

    assert _runner.publish_test_profile_capsule is canonical_publish
    with sequence_sandbox(sequence_id="canonical-capsule-runtime", sandbox_root=tmp_path / "scope") as sandbox:
        assert sandbox.profile_id == SANDBOX_PROFILE_ID
        assert (sandbox.storage_root / "buckets" / SANDBOX_PROFILE_ID).is_dir()


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

    assert transcript.frames[0].envelope is not None
    assert transcript.frames[0].envelope["result"]["logged_out_profile"] == "docs-sequence-sandbox"
    assert transcript.result_frame.envelope is not None
    assert transcript.result_frame.envelope["result"]["deleted"] is True
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
    """A login frame's unscoped session binding must not outlive its sandbox.

    ``config login`` binds its :class:`BucketSession` through the UNSCOPED
    ``bind_active_bucket_session`` so the login survives the call — correct for a
    real operator, whose every command is its own process. This engine invokes
    the CLI in-process, so the binding otherwise survives sandbox teardown; the
    next sandbox's root callback then short-circuits on
    ``has_active_bucket_session()`` instead of resuming for its own bucket, and
    the storage runtime correctly refuses every profile-bound verb because the
    route bucket is not the session bucket.
    """

    _LOGIN_BODY = "\n".join(
        [
            "@setup aeat config profile create me --quiet --entity-type natural_person"
            ' --tax-id 87654321X --name "Ana" --surnames "Garcia Lopez"',
            "@setup aeat config repair profile --clear-active --yes",
            "@result aeat --format json config login me",
            "@expect exit_code == 0",
        ],
    )

    def test_login_binding_is_evicted_at_teardown(self, tmp_path: Path) -> None:
        """A real login binds a real session inside, and nothing survives outside."""
        from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
        from cadrumo.tests.cli_runner import invoke_cached_cli

        assert current_active_bucket_session() is None, "a prior test leaked a bucket session"

        with sequence_sandbox(sequence_id="runner-session-leak", sandbox_root=tmp_path / "login"):
            created = invoke_cached_cli(
                [
                    "config",
                    "profile",
                    "create",
                    "me",
                    "--quiet",
                    "--entity-type",
                    "natural_person",
                    "--tax-id",
                    "87654321X",
                    "--name",
                    "Ana",
                    "--surnames",
                    "Garcia Lopez",
                ],
            )
            assert created.exit_code == 0, created.stderr
            cleared = invoke_cached_cli(["config", "repair", "profile", "--clear-active", "--yes"])
            assert cleared.exit_code == 0, cleared.stderr
            logged_in = invoke_cached_cli(["--format", "json", "config", "login", "me"])
            assert logged_in.exit_code == 0, logged_in.stderr

            # Anti-vacuity: the login really bound a session, and for a bucket
            # that is NOT this sandbox's injected profile — exactly the binding
            # that used to poison the next sandbox. Without this assertion the
            # post-teardown check below would pass on a run where nothing bound.
            bound = current_active_bucket_session()
            assert bound is not None
            assert bound.bucket_id != SANDBOX_PROFILE_ID

        assert current_active_bucket_session() is None

    def test_profile_bound_verb_serves_in_the_sandbox_after_a_login_sandbox(self, tmp_path: Path) -> None:
        """The operator-facing symptom: the NEXT sequence must still be served.

        Executed as two real sequences in two real sandboxes, the shape the
        ``how-to/troubleshooting`` page runs. With the binding left standing the
        second sequence exits 4 (``INTEGRITY_STORAGE_VALIDATION``: the database
        route does not match the active bucket session) and
        :func:`execute_sequence` raises.
        """
        execute_sequence(
            _result_sequence(self._LOGIN_BODY, sequence_id="runner-session-leak-a"),
            sandbox_root=tmp_path / "leak-a",
        )

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
        from .._runner import _live_aeat_tokens

        benign = _result_sequence(
            "@setup aeat app ledger import --file pull-history.csv\n"
            "@result aeat --format json config profile list\n"
            '@expect status == "success"\n',
            sequence_id="runner-option-value-scan",
        )
        assert _live_aeat_tokens(benign.frames[0]) == ()


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
        from .._runner import _resolve_json_path

        document = {"result": {"casilla_values": {"03": "500.00", "01": "1000.00"}}}
        assert _resolve_json_path(document, "result.casilla_values.03") == (True, "500.00")
        assert _resolve_json_path(document, "result.casilla_values.01") == (True, "1000.00")
        assert _resolve_json_path(document, "result.casilla_values.99") == (False, None)

    def test_digit_segment_resolves_a_list_index_when_the_node_is_a_list(self) -> None:
        from .._runner import _resolve_json_path

        document = {"result": {"items": [{"id": "first"}, {"id": "second"}]}}
        assert _resolve_json_path(document, "result.items.1.id") == (True, "second")
        assert _resolve_json_path(document, "result.items.2.id") == (False, None)
        # The bracketed form remains the explicit list address for the same node.
        assert _resolve_json_path(document, "result.items[0].id") == (True, "first")

    def test_bracket_form_never_indexes_an_object(self) -> None:
        from .._runner import _resolve_json_path

        document = {"result": {"casilla_values": {"0": "zero-key"}}}
        assert _resolve_json_path(document, "result.casilla_values[0]") == (False, None)
        assert _resolve_json_path(document, "result.casilla_values.0") == (True, "zero-key")

    def test_bracket_quoted_segment_resolves_a_dotted_hyphenated_object_key(self) -> None:
        from .._runner import _resolve_json_path

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
        assert _resolve_json_path(document, 'result.casilla_values["decl.importe-operaciones"]') == (True, "12345.00")
        assert _resolve_json_path(document, 'result.casilla_values["decl.numero-operadores"]') == (True, "3")
        # An absent quoted key misses cleanly.
        assert _resolve_json_path(document, 'result.casilla_values["decl.nope"]') == (False, None)

    def test_bracket_quoted_segment_is_a_dict_key_never_a_list_index(self) -> None:
        from .._runner import _resolve_json_path

        # On a list node the quoted form addresses no element and misses cleanly
        # (it is a literal object key only, never a list index).
        document = {"result": {"items": [{"id": "first"}, {"id": "second"}]}}
        assert _resolve_json_path(document, 'result.items["0"]') == (False, None)
        # On a dict whose key is the digit string, the quoted form finds it.
        digit_key_doc = {"result": {"casilla_values": {"0": "zero-key"}}}
        assert _resolve_json_path(digit_key_doc, 'result.casilla_values["0"]') == (True, "zero-key")

    def test_bracket_quoted_segment_on_a_non_dict_node_misses_cleanly(self) -> None:
        from .._runner import _resolve_json_path

        # A quoted key applied to a scalar (non-Mapping, non-list) node returns
        # (False, None) rather than raising.
        document = {"result": {"status": "verified_complete"}}
        assert _resolve_json_path(document, 'result.status["x"]') == (False, None)


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

        from .._runner import sequence_sandbox

        with (
            scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", "fake-operator-dni-99999999R"),
            scoped_env_var("AEAT_FAKE_SESSION_TOKEN", "fake-session-token-do-not-leak"),
        ):
            observed: dict[str, str | None] = {}
            with sequence_sandbox(sequence_id="env-scrub-probe", sandbox_root=tmp_path / "scope"):
                observed["clave"] = os.environ.get("CADRUMO_CLAVE_MOVIL_DNI_NIE")
                observed["aeat"] = os.environ.get("AEAT_FAKE_SESSION_TOKEN")
                observed["pin"] = os.environ.get("CADRUMO_LOCAL_STORAGE_ROOT")

            # Inside the scope: operator vars gone, the isolation pin intact.
            assert observed["clave"] is None
            assert observed["aeat"] is None
            assert observed["pin"] is not None
            # Outside the sandbox scope but still under the export: restored verbatim.
            assert os.environ["CADRUMO_CLAVE_MOVIL_DNI_NIE"] == "fake-operator-dni-99999999R"
            assert os.environ["AEAT_FAKE_SESSION_TOKEN"] == "fake-session-token-do-not-leak"  # noqa: S105 - synthetic test value

    def test_external_tool_probes_are_pinned_to_stable_absence(self, tmp_path: Path) -> None:
        """Real provider and browser probes cannot observe workstation installs."""
        import os

        from cadrumo.application.provisioning import (
            probe_playwright_browser,
            probe_subprocess_providers,
        )

        from .._runner import sequence_sandbox

        original_path = os.environ.get("PATH")
        with sequence_sandbox(sequence_id="external-tool-probe", sandbox_root=tmp_path / "scope"):
            providers = probe_subprocess_providers()
            browser = probe_playwright_browser()

            assert providers
            assert all(not status.available for status in providers)
            assert all("PATH" in status.remediation for status in providers)
            assert browser.available is False
            assert browser.remediation == "playwright install chromium"
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

        from .._runner import sequence_sandbox

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
        secret = "fake-operator-dni-99999999R"  # noqa: S105 - synthetic test value
        with scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", secret):
            sequence = _result_sequence(
                "aeat --format json config profile list\n"
                "@result aeat --format json config profile list\n"
                '@expect status == "success"\n',
                sequence_id="runner-env-scrub",
            )
            transcript = execute_sequence(sequence, sandbox_root=tmp_path / "run")

        for frame in transcript.frames:
            assert frame.exit_code == 0
            assert secret not in frame.output
            assert secret not in frame.stderr

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
        ``conftest.py`` bridge (:func:`cadrumo.tests._env_loader.bridge_env_file_into_environ`),
        which parses a real dotenv file and applies each pair to ``os.environ``
        via ``setdefault`` before any test runs. This drives that REAL bridge
        function against a synthetic dotenv file (anti-vacuity: the bridge is
        proven to genuinely land the pair in ``os.environ``, not assumed), then
        proves the bridged value — now indistinguishable from a genuinely
        ambient ``CADRUMO_*`` variable — is scrubbed by the same
        ``_neutralized_ambient_env`` seam :class:`TestAmbientEnvNeutralisation`'s
        other probes exercise directly, end to end through a real sequence run."""
        import os

        from cadrumo.tests._env_loader import bridge_env_file_into_environ

        from .._runner import sequence_sandbox

        secret = "fake-operator-dni-77777777H"  # noqa: S105 - synthetic test value
        env_var_name = "CADRUMO_CLAVE_MOVIL_DNI_NIE"
        scripted_dotenv = tmp_path / "scripted.env"
        scripted_dotenv.write_text(f"{env_var_name}={secret}\n", encoding="utf-8")

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
            assert bridged == {env_var_name: secret}
            assert os.environ[env_var_name] == secret

            with sequence_sandbox(sequence_id="dotenv-bridge-probe", sandbox_root=tmp_path / "scope"):
                assert os.environ.get(env_var_name) is None

            # Restored outside the sandbox scope: the bridged value persists in
            # the ambient environment exactly like a real operator export would.
            assert os.environ[env_var_name] == secret

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
                assert secret not in frame.output
                assert secret not in frame.stderr
        finally:
            if had_prior:
                os.environ[env_var_name] = prior_value  # type: ignore[assignment]
            else:
                os.environ.pop(env_var_name, None)
