"""Executor-level mask-honesty (anti-tautology) gate for cli-sequence goldens.

The sequence-level analogue of the substrate's own anti-tautology proof
(``cadrumo.core.observability.tests.test_golden``), enforced through the REAL
executor and comparison path. Three interlocking claims:

1. **Residual determinism, pinned exactly.** A representative sequence executed
   twice in fresh hermetic sandboxes yields pre-mask differing JSON paths equal
   to the sequence's residual non-deterministic set. On today's enrollable
   surface that residual is EMPTY — with the clock frozen and the profile id
   injected, every reachable identifier is content-addressed or pinned — which
   is trivially within the central ``GOLDEN_MASK_FIELDS``.
2. **The masked-field canary.** No hermetic-reachable enrollable envelope
   surfaces a centrally-masked surrogate key (``snapshot_id``, ``run_id``) in
   a fresh sandbox today: every ``snapshot_id`` emitter is a live-AEAT surface
   (unenrollable by design), and the one enrollable non-live ``run_id``
   carrier — the ``app diagnostics runs`` payload — lists per-run rows that are
   empty in a fresh sandbox, so the key never materialises. The representative
   sequence deliberately includes that diagnostics read so the canary scans the
   nearest surface that COULD emit a masked key. If one ever appears, the
   canary fails loudly and claim 1 must be extended to a sequence that
   genuinely exercises the flap — the gate cannot silently rot into vacuity.
3. **The mask bites exactly the declared set — through the real compare
   path.** A masked-field value difference injected into a REAL golden/live
   pair compares CLEAN (the mask hides it), while the same difference under
   any other key compares RED (the mask hides nothing else). Together with the
   substrate proof over real live-capture envelopes, widening or shrinking the
   central mask is a loud failure at both tiers.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.errors import SphinxError

from cadrumo.tests.env_scope import scoped_env_var
from cadrumo.tests.golden_comparison import GOLDEN_MASK_FIELDS, differing_paths
from dev._paths import REPO_ROOT

from ..sequences.checks import (
    check_page_coherence_in_subprocess,
    check_sequences,
    check_sequences_in_subprocess,
    discover_sequences,
    english_pinned_environment,
    refresh_sequences,
)
from ..sequences.cli import main as sequences_cli_main
from ..sequences.compare import compare_transcript_to_golden
from ..sequences.golden_store import SequenceGolden, build_golden
from ..sequences.parser import parse_sequence
from ..sequences.runner import SequenceTranscript, execute_sequence
from ..sequences.schema import ParsedSequence

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

#: Wall ceiling for the two gates that fan out into a pool of child
#: interpreters. Deliberately far above the repository's 300s default rather
#: than a shaved margin: the unscoped gate measured 344s on an IDLE box, and
#: these tests run in a lane sharing the machine, so a tight bound would fire
#: on load rather than on a defect. The ceiling still exists -- a genuinely
#: wedged pool fails here instead of running forever.
#:
#: Sizing this correctly is load-bearing beyond this file. When the ceiling
#: fires on a test parked in ``subprocess.wait()``, the thread timeout method
#: cannot interrupt it, so the xdist WORKER dies instead of the test failing,
#: and the run is then re-scheduled or wedged rather than reported.
_SUBPROCESS_POOL_TIMEOUT = 1800

_PAGE = "tutorials/anti-tautology-gate"
_PROFILE_DELETE_SEQUENCE_ID = "profile-setup-delete"
_PROFILE_DELETE_DIGEST_PATH = "result.fingerprint.digest"

#: The workstation gate's own sequence, parsed here rather than taken from the
#: enrolled docs tree. ``install-confirm`` -- the page that shows these very
#: commands -- is deliberately display-only: every command that confirms an
#: installation reports host facts, so no golden of it is reproducible on a
#: second machine and all its frames carry a nondeterministic-output reason. A
#: display-only sequence has no executed frames at all, so it cannot carry this
#: gate. The gate does not need a committed golden: it compares two transcripts
#: captured on the SAME host minutes apart, which is exactly the comparison the
#: free-memory mask exists for.
_WORKSTATION_SEQUENCE_ID = "workstation-mask-honesty"
_WORKSTATION_BODY = "\n".join(
    [
        "@step Turn off a capability whose dependency this sandbox does not provision.",
        "@setup aeat config profile capabilities set llm_vision off",
        "@step Ask what is installed and what is missing.",
        "@result aeat --format json config check",
        "@expect exit_code == 0",
    ],
)

#: A dependency row whose facts carry the live free-RAM reading the mask hides,
#: alongside the total-RAM reading it must NOT hide.
_WORKSTATION_HARDWARE_SERVICE = "local-inference-hardware"

#: A preflight row `config check` really emits whose health is a deterministic
#: product fact, not a host reading: it reports whether the bundled legal
#: normatives corpus resolved. Inverting it must red, proving the host mask
#: did not swallow the product evidence beside it.
_WORKSTATION_DETERMINISTIC_CHECK = "corpus:normatives"

#: The docs page these commands document. Used only as the comparison's page
#: coordinate in diagnostics; this gate compares two live transcripts and
#: consults no committed golden.
_WORKSTATION_PAGE = "workstation-setup"

#: The representative sequence: a real capture-threaded JSON read chain. The
#: ``app diagnostics runs`` frame is deliberate: its payload is the one
#: enrollable non-live surface whose schema carries a masked key (``run_id``
#: per run row), so the canary below scans the nearest surface that could emit
#: one — in a fresh hermetic sandbox the run list is empty and the key never
#: materialises.
_BODY = "\n".join(
    [
        "aeat --format json app diagnostics runs",
        "aeat --format json config profile list",
        "@capture run_status status",
        "@result aeat --format json config profile list",
        '@expect status == "success"',
        "@expect exit_code == 0",
    ],
)


def _representative_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="anti-tautology-gate",
        options={"verify": "Verify the profile listing succeeds."},
        body=_BODY,
    )


@pytest.fixture(scope="module")
def double_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[SequenceTranscript, SequenceTranscript]:
    """Two REAL executions of the representative sequence, fresh sandboxes."""
    first = execute_sequence(_representative_sequence(), sandbox_root=tmp_path_factory.mktemp("run-a"))
    second = execute_sequence(_representative_sequence(), sandbox_root=tmp_path_factory.mktemp("run-b"))
    return first, second


def _envelope_keys(node: object) -> frozenset[str]:
    """Collect every mapping key at any depth of an envelope document."""
    keys: set[str] = set()

    def _walk(value: object) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                keys.add(str(key))
                _walk(item)
            return
        if isinstance(value, list | tuple):
            for item in value:
                _walk(item)

    _walk(node)
    return frozenset(keys)


def _mutated_golden(golden: SequenceGolden, key: str, value: str) -> SequenceGolden:
    """Return the golden with ``key: value`` injected into frame 0's result."""
    document = golden.model_dump(mode="json")
    document["frames"][0]["envelope"]["result"][key] = value
    return SequenceGolden.model_validate_json(json.dumps(document))


def _mutated_transcript(transcript: SequenceTranscript, key: str, value: str) -> SequenceTranscript:
    """Return the transcript with ``key: value`` injected into frame 0's envelope."""
    document = transcript.model_dump(mode="json")
    document["frames"][0]["envelope"]["result"][key] = value
    return SequenceTranscript.model_validate_json(json.dumps(document))


#: Executes one enrolled sequence in a child interpreter and writes its page and
#: transcript to the file named as ``argv[2]``. The gate below needs two runs
#: that are independent AT THE PROCESS level: the sandbox profile is published
#: once per process and every later sandbox in that process is a clone of that
#: published state, so two in-process runs delete byte-identical encrypted
#: profiles and the delete fingerprint over them no longer differs. Two
#: processes provision independently, which is where the residual this gate
#: measures actually lives -- and is the level a docs build, a CI shard and a
#: developer's machine each compare at.
#:
#: The payload travels through a FILE rather than stdout: the child runs real
#: CLI frames, and anything they or the logging stack write to stdout would be
#: indistinguishable from the payload.
_TRANSCRIPT_CHILD_PROGRAM = textwrap.dedent(
    """
    import json
    import sys
    import tempfile
    from pathlib import Path

    from dev.docs.sequences.checks import discover_sequences
    from dev.docs.sequences.runner import execute_sequence

    discovered, problems = discover_sequences(sequence_id=sys.argv[1])
    if problems or len(discovered) != 1:
        raise SystemExit(f"discovery of {sys.argv[1]!r} failed: {problems} ({len(discovered)} found)")
    enrolled = discovered[0]
    with tempfile.TemporaryDirectory(prefix="cli-sequence-gate-", ignore_cleanup_errors=True) as sandbox:
        transcript = execute_sequence(enrolled.sequence, sandbox_root=Path(sandbox))
    payload = json.dumps({"page": enrolled.page, "transcript": transcript.model_dump_json()})
    Path(sys.argv[2]).write_text(payload, encoding="utf-8")
    """,
)


def _execute_in_child_interpreter(sequence_id: str, payload_path: Path) -> tuple[str, SequenceTranscript]:
    """Execute one enrolled sequence in its own interpreter; return page + transcript.

    The transcript crosses the process boundary as the model's OWN serialised
    form and is rehydrated with ``model_validate_json``, the round trip the
    rest of this module uses. A plain ``model_dump``/``model_validate`` pair
    does not round-trip here: the transcript's strict field types reject the
    JSON surrogates (a list where a tuple is declared, a string where a
    datetime is) that the dump produces.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", _TRANSCRIPT_CHILD_PROGRAM, sequence_id, str(payload_path)],
        cwd=REPO_ROOT,
        env=english_pinned_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"sequence child failed (exit {result.returncode}):\n{result.stderr}"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    page = payload["page"]
    assert isinstance(page, str), f"sequence child reported a non-text page: {page!r}"
    return page, SequenceTranscript.model_validate_json(payload["transcript"])


@pytest.fixture(scope="module")
def profile_delete_double_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[str, SequenceTranscript, SequenceTranscript]:
    """Execute the real logout/delete contract twice in independent interpreters."""
    payloads = tmp_path_factory.mktemp("delete-transcripts")
    page, first = _execute_in_child_interpreter(_PROFILE_DELETE_SEQUENCE_ID, payloads / "first.json")
    _page, second = _execute_in_child_interpreter(_PROFILE_DELETE_SEQUENCE_ID, payloads / "second.json")
    return page, first, second


def _set_delete_fingerprint_leaf(
    value: SequenceGolden | SequenceTranscript,
    leaf: str,
    replacement: object,
) -> SequenceGolden | SequenceTranscript:
    """Return ``value`` with one real profile-delete fingerprint leaf changed."""
    document = value.model_dump(mode="json")
    fingerprint = document["frames"][1]["envelope"]["result"]["fingerprint"]
    fingerprint[leaf] = replacement
    return type(value).model_validate_json(json.dumps(document))


def _workstation_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id=_WORKSTATION_SEQUENCE_ID,
        options={"verify": "Verify the workstation check reports its dependency and preflight rows."},
        body=_WORKSTATION_BODY,
    )


@pytest.fixture(scope="module")
def workstation_double_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[str, SequenceTranscript, SequenceTranscript]:
    """Execute the real workstation diagnostic contract twice in fresh sandboxes."""
    sequence = _workstation_sequence()
    first = execute_sequence(sequence, sandbox_root=tmp_path_factory.mktemp("workstation-a"))
    second = execute_sequence(sequence, sandbox_root=tmp_path_factory.mktemp("workstation-b"))
    return _WORKSTATION_PAGE, first, second


def _set_workstation_fact(
    transcript: SequenceTranscript,
    *,
    service: str,
    fact: str,
    replacement: object,
) -> SequenceTranscript:
    """Return a real workstation transcript with one dependency fact changed."""
    document = transcript.model_dump(mode="json")
    dependencies = document["frames"][-1]["envelope"]["result"]["dependencies"]
    row = next((item for item in dependencies if item["service"] == service), None)
    assert row is not None, (
        f"the workstation check no longer reports a {service!r} dependency row, so this gate has no "
        f"host-volatile fact to tamper with; it reports {sorted(item['service'] for item in dependencies)}"
    )
    assert fact in row["facts"], (
        f"the {service!r} row no longer carries the {fact!r} fact this gate tampers with; "
        f"it carries {sorted(row['facts'])}"
    )
    row["facts"][fact] = replacement
    return SequenceTranscript.model_validate_json(json.dumps(document))


def _invert_deterministic_health(transcript: SequenceTranscript) -> SequenceTranscript:
    """Return a real workstation transcript with one deterministic preflight row flipped."""
    document = transcript.model_dump(mode="json")
    checks = document["frames"][-1]["envelope"]["result"]["preflight"]
    row = next((item for item in checks if item["check"] == _WORKSTATION_DETERMINISTIC_CHECK), None)
    assert row is not None, (
        f"the workstation check no longer emits the {_WORKSTATION_DETERMINISTIC_CHECK!r} preflight row, so "
        "this gate cannot prove the host mask leaves deterministic product evidence biting; it emits "
        f"{sorted(item['check'] for item in checks)}"
    )
    row["healthy"] = not bool(row["healthy"])
    return SequenceTranscript.model_validate_json(json.dumps(document))


class TestWorkstationFreeMemoryMaskHonesty:
    def test_two_real_runs_compare_clean_through_the_central_policy(
        self,
        workstation_double_run: tuple[str, SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Fresh diagnostics remain comparable without pinning the free-RAM reading."""
        page, first, second = workstation_double_run
        assert compare_transcript_to_golden(second, build_golden(first), page=page) == ()

    def test_only_free_memory_tampering_is_ignored_and_deterministic_facts_bite(
        self,
        workstation_double_run: tuple[str, SequenceTranscript, SequenceTranscript],
    ) -> None:
        """The real compare path masks free RAM but retains host and product evidence."""
        page, first, second = workstation_double_run
        golden = build_golden(first)

        volatile = _set_workstation_fact(
            second,
            service=_WORKSTATION_HARDWARE_SERVICE,
            fact="free_memory_bytes",
            replacement=1,
        )
        assert compare_transcript_to_golden(volatile, golden, page=page) == ()

        total_memory = _set_workstation_fact(
            second,
            service=_WORKSTATION_HARDWARE_SERVICE,
            fact="total_memory_bytes",
            replacement=1,
        )
        assert compare_transcript_to_golden(total_memory, golden, page=page)

        corpus_changed = _invert_deterministic_health(second)
        assert compare_transcript_to_golden(corpus_changed, golden, page=page)


class TestProfileDeletePathMaskHonesty:
    def test_fresh_sandbox_residual_is_exactly_the_delete_digest(
        self,
        profile_delete_double_run: tuple[str, SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Two independently provisioned runs flap at the one enrolled path, and nowhere else.

        Independence is taken at the PROCESS level (see
        :data:`_TRANSCRIPT_CHILD_PROGRAM`). Two sandboxes inside one process are
        clones of one published profile, so the delete fingerprint over its
        encrypted bytes is identical between them and this measurement would
        read an empty residual and prove nothing about the enrolled mask.
        """
        _page, first, second = profile_delete_double_run
        residual: set[str] = set()
        for left, right in zip(first.frames, second.frames, strict=True):
            assert left.envelope is not None and right.envelope is not None
            residual |= differing_paths(left.envelope, right.envelope)
        assert residual == {_PROFILE_DELETE_DIGEST_PATH}

    def test_only_digest_flap_compares_clean_and_sibling_tampering_bites(
        self,
        profile_delete_double_run: tuple[str, SequenceTranscript, SequenceTranscript],
    ) -> None:
        """The path mask hides the real flap but preserves fingerprint evidence."""
        page, first, second = profile_delete_double_run
        golden = build_golden(first)
        assert compare_transcript_to_golden(second, golden, page=page) == ()

        for leaf, tampered in (("file_count", 999), ("total_bytes", 999999)):
            changed = _set_delete_fingerprint_leaf(second, leaf, tampered)
            assert isinstance(changed, SequenceTranscript)
            problems = compare_transcript_to_golden(changed, golden, page=page)
            assert len(problems) == 1
            assert f"result.fingerprint.{leaf}" in problems[0]


class TestExecutorMaskHonesty:
    def test_pre_mask_residual_equals_the_declared_nondeterministic_set(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 1: the double-execution pre-mask diff is pinned EXACTLY.

        The residual for the enrollable surface is empty (content-addressed
        ids, frozen clock, injected profile id); pinning `== frozenset()`
        rather than `<= mask` means ANY new residual path — masked or not —
        is a named regression that must be consciously enrolled, never
        silently absorbed.
        """
        first, second = double_run
        residual: set[str] = set()
        for left, right in zip(first.frames, second.frames, strict=True):
            assert left.envelope is not None and right.envelope is not None
            residual |= differing_paths(left.envelope, right.envelope)
            assert left.output == right.output
            assert left.stderr == right.stderr
        # Empty is trivially within the central mask; the equality pin is the
        # stronger claim.
        assert residual == frozenset(), sorted(residual)

    def test_masked_keys_do_not_appear_on_the_enrollable_surface_yet(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 2 (canary): no hermetic-reachable enrollable envelope surfaces
        a masked key in a fresh sandbox. The scan includes the one enrollable
        non-live surface whose SCHEMA carries ``run_id`` (``app diagnostics
        runs``) — its per-run rows are empty in a fresh sandbox. If this ever
        fails, an enrollable envelope has started emitting a masked field —
        extend the double-run proof above to a sequence that genuinely
        exercises that flap before touching this assertion."""
        first, _ = double_run
        seen: set[str] = set()
        for frame in first.frames:
            seen |= _envelope_keys(frame.envelope)
        assert seen & GOLDEN_MASK_FIELDS == frozenset(), sorted(seen & GOLDEN_MASK_FIELDS)

    @pytest.mark.parametrize("masked_key", sorted(GOLDEN_MASK_FIELDS))
    def test_mask_hides_a_masked_field_flap_through_the_real_compare_path(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
        masked_key: str,
    ) -> None:
        """Claim 3a: a golden/live pair differing ONLY in a masked field's
        value compares clean through ``compare_transcript_to_golden`` — the
        exact flap (a uuid tail) the central mask exists to hide."""
        first, second = double_run
        golden = _mutated_golden(build_golden(first), masked_key, "writer-run-value-1111")
        live = _mutated_transcript(second, masked_key, "checker-run-value-2222")
        assert compare_transcript_to_golden(live, golden, page=_PAGE) == ()

    def test_mask_hides_nothing_but_the_declared_fields(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 3b: the identical value flap under an UNDECLARED key is a
        loud post-mask divergence — the mask is exactly the declared set, so
        it cannot silently widen to launder a real regression."""
        first, second = double_run
        undeclared_key = "some_other_surrogate_id"
        assert undeclared_key not in GOLDEN_MASK_FIELDS
        golden = _mutated_golden(build_golden(first), undeclared_key, "writer-run-value-1111")
        live = _mutated_transcript(second, undeclared_key, "checker-run-value-2222")
        problems = compare_transcript_to_golden(live, golden, page=_PAGE)
        assert len(problems) == 1
        assert undeclared_key in problems[0]


class TestCommittedGoldensCleanGate:
    """The pytest half of the two-surfaces-one-engine gate.

    Calls the same ``check_sequences`` the ``builder-inited`` Sphinx hook wires,
    unscoped over the committed ``docs/`` tree, so CI catches golden drift
    without a full docs build. A non-empty problem set is a divergence: each
    entry already names the page, sequence, frame, argv, and diff, so they are
    printed verbatim on failure.
    """

    @pytest.mark.timeout(_SUBPROCESS_POOL_TIMEOUT)
    def test_every_committed_golden_matches_live_execution(self) -> None:
        """Every enrolled sequence re-executes clean against its committed golden.

        Page-sharded across 8 bounded child interpreters: each sequence still
        executes in its own fresh hermetic sandbox, so the verdict is identical
        to the serial run — only the scheduling changes. Width 8 is the
        machine-aware CI lane size (24 cores / 3 co-resident lanes, the same
        bound the pytest lanes use).

        Carries its own timeout because it legitimately outruns the repository
        ceiling: measured at 344s on an idle box, against a 300s default. That
        gap is what killed xdist workers rather than failing this test. The
        default timeout method here is ``thread``, which cannot interrupt a
        thread parked in ``subprocess.wait()`` on eight children, so the ceiling
        fired, the test did not die, and the WORKER exited uncleanly instead --
        after which xdist re-ran this test on a replacement node (one id
        reported as three failures) or wedged its scheduler.
        """
        problems = check_sequences_in_subprocess(jobs=8)
        assert problems == (), "cli-sequence goldens diverge from live execution:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# Both gate surfaces red on an injected divergence, green on clean
# ---------------------------------------------------------------------------

_FIXTURE_SEQUENCE_ID = "fixture-divergence"
_FIXTURE_BODY = "\n".join(
    [
        "aeat --format json config profile list",
        "@result aeat --format json config profile list",
        "@expect result.profiles[0].active == true",
        "@expect exit_code == 0",
    ],
)
_FIXTURE_INDEX = (
    "# Fixture\n\n"
    "Create a profile first with `aeat config profile create`.\n\n"
    f"```{{cli-sequence}} {_FIXTURE_SEQUENCE_ID}\n"
    ":verify: Confirm the profile listing succeeds.\n"
    "```\n"
)


@pytest.fixture
def _hermetic_env(tmp_path: pytest.TempPathFactory) -> Iterator[None]:
    """Pin an isolated storage root and English output for the CLI-tree walk."""
    root = Path(str(tmp_path)) / "cadrumo-store"
    root.mkdir()
    with (
        scoped_env_var("CADRUMO_LOCAL_STORAGE_ROOT", str(root)),
        scoped_env_var("CADRUMO_OUTPUT_LANGUAGE", "en"),
    ):
        yield


def _write_fixture_docs(root: Path) -> tuple[Path, Path]:
    """Write an isolated fixture docs tree and its own goldens root; return both.

    Never touches the committed ``docs/`` tree: the page lives under a tmp docs
    root and the golden under a tmp goldens root the directive's config seam
    redirects to.
    """
    docs_root = root / "docs"
    docs_root.mkdir(parents=True)
    goldens_root = root / "goldens"
    goldens_root.mkdir(parents=True)
    (docs_root / "index.md").write_text(_FIXTURE_INDEX, encoding="utf-8")
    contract_dir = docs_root / "_sequences" / "contracts" / "index"
    contract_dir.mkdir(parents=True)
    (contract_dir / f"{_FIXTURE_SEQUENCE_ID}.seq").write_text(_FIXTURE_BODY + "\n", encoding="utf-8")
    return docs_root, goldens_root


def _refresh_fixture_golden(docs_root: Path, goldens_root: Path) -> Path:
    """Execute the fixture sequence and write its (correct) committed golden."""
    written, problems, _advisories = refresh_sequences(docs_root=docs_root, goldens_root=goldens_root)
    assert problems == (), problems
    assert len(written) == 1
    return written[0]


def _corrupt_golden_exit_code(golden_path: Path) -> None:
    """Inject a divergence: rewrite frame 0's exit code to a value live never emits."""
    document = json.loads(golden_path.read_text(encoding="utf-8"))
    document["frames"][0]["exit_code"] = 99
    golden_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _write_fixture_conf(site: Path, goldens_root: Path) -> None:
    """Write a fixture Sphinx conf registering the directive and the build gate.

    The gate is the SAME ``check_sequence_goldens`` the real ``docs/conf.py``
    connects, so this build surface exercises the production hook, not a copy.
    """
    conf = (
        'extensions = ["myst_parser"]\n'
        'myst_enable_extensions = ["colon_fence"]\n'
        f"cadrumo_sequences_goldens_root = {str(goldens_root)!r}\n"
        "\n"
        "def setup(app):\n"
        "    from dev.docs.sequence_directive import register\n"
        "    from dev.docs.sequence_build_gate import check_sequence_goldens\n"
        "    register(app)\n"
        "    app.connect('builder-inited', lambda a: check_sequence_goldens(a, pages=None))\n"
    )
    (site / "conf.py").write_text(conf, encoding="utf-8")


def _build_fixture_site(root: Path, docs_root: Path, goldens_root: Path) -> str:
    """Build the fixture page in-process and return the warning log.

    Raises:
        SphinxError: propagated from the ``builder-inited`` gate on a divergence.
    """
    site = root / "site"
    site.mkdir()
    (site / "index.md").write_text(_FIXTURE_INDEX, encoding="utf-8")
    contract_dir = site / "_sequences" / "contracts" / "index"
    contract_dir.mkdir(parents=True)
    (contract_dir / f"{_FIXTURE_SEQUENCE_ID}.seq").write_text(_FIXTURE_BODY + "\n", encoding="utf-8")
    _write_fixture_conf(site, goldens_root)
    warning = io.StringIO()
    app = Sphinx(
        srcdir=str(site),
        confdir=str(site),
        outdir=str(root / "_out"),
        doctreedir=str(root / "_doctree"),
        buildername="html",
        status=io.StringIO(),
        warning=warning,
        freshenv=True,
        warningiserror=True,
    )
    app.build()
    return warning.getvalue()


class TestBothSurfacesRedOnDivergence:
    """An injected golden divergence reds BOTH gate surfaces, and
    clean goldens pass BOTH green — proving the Sphinx build hook and the pytest
    gate share one execution path. The fixture tree is fully isolated;
    the committed ``docs/`` tree is never mutated."""

    def test_divergent_golden_reds_the_sphinx_build(
        self,
        tmp_path: Path,
        _hermetic_env: None,
    ) -> None:
        """The ``builder-inited`` gate raises, naming the divergence and remedy."""
        docs_root, goldens_root = _write_fixture_docs(tmp_path)
        golden_path = _refresh_fixture_golden(docs_root, goldens_root)
        _corrupt_golden_exit_code(golden_path)

        with pytest.raises(SphinxError) as excinfo:
            _build_fixture_site(tmp_path, docs_root, goldens_root)
        message = str(excinfo.value)
        assert "golden expects 99" in message, message
        assert "python -m dev.docs.sequences refresh" in message, message

    def test_divergent_golden_reds_the_pytest_gate(
        self,
        tmp_path: Path,
        _hermetic_env: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The engine check function and its CLI check mode both red, naming the
        divergence and the refresh remedy — CI catches drift without a build."""
        docs_root, goldens_root = _write_fixture_docs(tmp_path)
        golden_path = _refresh_fixture_golden(docs_root, goldens_root)
        _corrupt_golden_exit_code(golden_path)

        # The engine function this gate asserts empty on now reds.
        problems, _advisories = check_sequences(docs_root=docs_root, goldens_root=goldens_root)
        assert problems != ()
        assert any("golden expects 99" in problem for problem in problems), problems

        # The CLI check mode — the surface CI runs without a full docs build —
        # exits non-zero and prints both the divergence and the refresh remedy.
        exit_code = sequences_cli_main(
            ["check", "--docs-root", str(docs_root), "--goldens-root", str(goldens_root)],
        )
        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "golden expects 99" in stderr, stderr
        assert "python -m dev.docs.sequences refresh" in stderr, stderr

    def test_sharded_check_matches_the_serial_verdict_red_and_green(
        self,
        tmp_path: Path,
        _hermetic_env: None,
    ) -> None:
        """The page-sharded parallel check (jobs > 1) is verdict-identical.

        Green on the correct committed golden, red — naming the exact injected
        divergence — once the golden is corrupted. This pins the sharded
        scheduling path the lane-wide gates run with, through real child
        interpreters against a real fixture tree.
        """
        docs_root, goldens_root = _write_fixture_docs(tmp_path)
        golden_path = _refresh_fixture_golden(docs_root, goldens_root)

        clean = check_sequences_in_subprocess(docs_root=docs_root, goldens_root=goldens_root, jobs=2)
        assert clean == (), clean

        _corrupt_golden_exit_code(golden_path)
        problems = check_sequences_in_subprocess(docs_root=docs_root, goldens_root=goldens_root, jobs=2)
        assert problems != ()
        assert any("golden expects 99" in problem for problem in problems), problems

    def test_bounded_check_reports_the_last_real_frame_before_expiry(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The public bounded check reports a real child runner's last frame.

        The enrolled lifecycle page is the longest-running enrolled surface. The
        check launches its real child interpreter and the bounded supervisor
        expires after the runner has journalled one of that page's actual
        frames. The assertion resolves the reported coordinate against current
        discovery, proving the parent/child receipt without pinning which frame
        scheduling reaches before expiry.

        The bound is MEASURED rather than pinned: the page's own clean duration
        is timed first, and the bounded run is given half of it. A pinned
        constant is what rotted this gate once -- the sandbox stopped being
        republished per sequence, the page's duration fell under the 30s
        constant, and the supervisor this test exists for never fired while the
        test reported a clean check as a failure. Half a measured duration
        tracks the machine instead: it is always well inside the page and well
        past the child's first journalled frame.
        """
        seed_sequence_id = "irpf-lifecycle-position"
        seed, discovery_problems = discover_sequences(sequence_id=seed_sequence_id)
        assert discovery_problems == ()
        assert len(seed) == 1
        page = seed[0].page
        discovered, discovery_problems = discover_sequences(page=page)
        assert discovery_problems == ()

        started = time.monotonic()
        clean_exit = sequences_cli_main(["check", "--page", page])
        clean_duration = time.monotonic() - started
        capsys.readouterr()
        assert clean_exit == 0, "the bound is measured against a CLEAN run of this page"
        timeout = round(clean_duration / 2, 3)

        exit_code = sequences_cli_main(
            [
                "check",
                "--page",
                page,
                "--timeout",
                str(timeout),
            ],
        )

        assert exit_code == 1, (
            f"a {timeout}s bound did not expire on a page measured at {clean_duration:.1f}s; "
            "the supervisor under test never ran"
        )
        stderr = capsys.readouterr().err
        assert f"timeout after {timeout}s while executing page {page!r}" in stderr, (
            f"the bound expired before the child journalled any frame, so the receipt under test "
            f"was never produced (page measured at {clean_duration:.1f}s): {stderr}"
        )
        sequence_match = re.search(r" sequence '(?P<sequence_id>[^']+)' frame ", stderr)
        assert sequence_match is not None
        enrolled = next(item for item in discovered if item.sequence_id == sequence_match.group("sequence_id"))
        frame_match = re.search(r" frame (?P<index>\d+) \(", stderr)
        assert frame_match is not None
        frame_index = int(frame_match.group("index"))
        frame = enrolled.sequence.executed_frames[frame_index]
        assert (
            f"sequence {enrolled.sequence_id!r} frame {frame_index} ({frame.source} line {frame.line_number})"
        ) in stderr
        assert " ".join(frame.argv) in stderr

    def test_clean_goldens_pass_both_surfaces_green(
        self,
        tmp_path: Path,
        _hermetic_env: None,
    ) -> None:
        """With the correct committed golden, both surfaces pass: the engine check
        is clean AND a real Sphinx build succeeds and renders the sequence."""
        docs_root, goldens_root = _write_fixture_docs(tmp_path)
        _refresh_fixture_golden(docs_root, goldens_root)

        problems, _advisories = check_sequences(docs_root=docs_root, goldens_root=goldens_root)
        assert problems == (), problems

        warnings = _build_fixture_site(tmp_path, docs_root, goldens_root)
        rendered = (tmp_path / "_out" / "index.html").read_text(encoding="utf-8")
        assert "cadrumo-sequence" in rendered, warnings
        assert f'data-sequence-id="{_FIXTURE_SEQUENCE_ID}"' in rendered


class TestPageCoherenceGate:
    """The page-coherence tier over the COMMITTED docs tree (rollout gate).

    For each enrolled page: one fresh sandbox, all the page's sequences
    executed in page order with state accumulating — what a reader following
    the page top to bottom in one clean environment experiences. Every
    ``@expect`` must hold against the live cumulative output. This is
    deliberately NOT golden equality (goldens stay the per-sequence isolated
    contract); a failure here means the PAGE's narrative does not survive its
    own accumulated state and the page content must change.
    """

    @pytest.mark.timeout(_SUBPROCESS_POOL_TIMEOUT)
    def test_every_enrolled_page_is_coherent_top_to_bottom(self) -> None:
        """Coherence is a page-scoped property (one sandbox per page, state
        accumulating only within the page), so pages shard cleanly across the
        same bounded 8-wide child pool as the goldens gate above.

        Carries the same ceiling as that gate, and for the same reason: it fans
        out into the identical 8-wide child pool, so it has the identical
        exposure to a ceiling firing while the test thread is parked in
        ``subprocess.wait()`` and unkillable by the thread timeout method.
        """
        problems = check_page_coherence_in_subprocess(jobs=8)
        assert problems == (), "enrolled pages are not coherent under cumulative execution:\n" + "\n".join(problems)
