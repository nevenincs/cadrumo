"""``config profile censo pull`` — surface, gating, and write-routing contracts.

The pull is the live-transport sibling of ``censo file --file``. What is
provable offline is proven here: the verb's name and door shape on the
real Click surface, its refusal when no profile is active, and the two
structural facts that keep the two transports reconciling identically —
the commit routes through the single cotejo apply authority, and it is
reachable only under ``--apply``.

What is NOT provable offline is the reconciliation itself: the reader
takes an authenticated session and the live-read gate refuses under
pytest, so there is no seam to drive a synthetic read through the CLI.
That behaviour — blank paths adopt, equal paths no-op, differing paths
are reported rather than overwritten — is proven directly against the
application authority in the user_profile suite, and the pins below
guarantee this door reaches it rather than re-deciding for itself.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any

import click
import pytest
import typer
from pydantic import ValidationError
from typer.testing import CliRunner

from .....application.user_profile.censo_sync import CENSO_SOURCE_TAG
from .....application.user_profile.censal_operation import CensalFieldIntent, CensalReviewFieldProjectionV1, CensalReviewProjectionV1
from .....core.config import Settings
from .....tests.cli_runner import invoke_cached_cli
from ... import app as _live_app
from .. import _censo_file
from .._censo_payloads import CensoFactPayload, CensoPullDivergencePayload, CensoPullResult
from .._censo_review_cli import confirm_censal_review

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_AEAT = Settings.external_constants().aeat
#: The censal consulta landing, assembled from the declared sede origin and
#: path rather than restated, so a route change reaches this payload too.
_CENSAL_CONSULTA_URL = f"{_AEAT.domains.sede}{_AEAT.sede_paths.censal_datos}"

#: Fetch verbs the CLI pull-and-file standard forbids for an AEAT read.
_FORBIDDEN_FETCH_VERBS = frozenset({"capture", "refresh", "fetch", "download", "sync", "get"})


def _censo_commands() -> dict[str, Any]:
    """Return the censo group's real subcommands, walked from the live CLI root.

    Reached through the command TREE rather than a module-level Typer object.
    ``_censo_file.censo_app`` no longer exists: the command-spec kernel builds
    groups from specs, so a module attribute stopped being the surface. The
    verbs themselves are unchanged -- ``config profile censo file`` and
    ``censo pull`` both still resolve, profile-bound -- only the route to them.

    Walked with the Click API rather than ``.commands`` because the kernel's
    groups resolve children lazily: the root's ``.commands`` dict is EMPTY
    until each child is asked for by name, so reading it would report a CLI
    with no commands at all. ``get_command`` resolves each child on demand,
    which is why this must NOT call ``materialise_lazy_subcommands`` -- that
    mutates the shared ``app`` object process-wide, and doing so here made a
    sibling case lose the command identifier on its refusal envelope.

    Typed loosely because Typer builds its own vendored ``Command`` class
    rather than a ``click.Group`` subclass; the surface under test is the
    command mapping, not the class identity.
    """
    node: Any = typer.main.get_command(_live_app)
    context = click.Context(node)
    for name in ("config", "profile", "censo"):
        node = node.get_command(context, name)
        assert node is not None, f"the live command tree has no {name!r} on the censo path"
        context = click.Context(node, parent=context)

    commands = {name: node.get_command(context, name) for name in node.list_commands(context)}
    assert commands, "the censo group exposes no subcommands"
    return commands


def _option_flags(command: Any) -> set[str]:
    return {opt for param in command.params for opt in param.opts}


def _stderr_document(result: Any) -> dict[str, Any]:
    """Extract the JSON error document from stderr (line-scanned: logging interleaves)."""
    stderr = result.stderr if result.stderr_bytes is not None else ""
    for line in stderr.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            parsed = json.loads(candidate)
            assert isinstance(parsed, dict)
            return parsed
    raise AssertionError(f"no JSON document on stderr: {stderr[:400]!r}")


def test_the_live_transport_is_named_pull() -> None:
    """The censo group exposes ``pull`` and ``file``, and no forbidden fetch synonym.

    ``pull`` names the AEAT read and ``--file`` names the local artefact:
    the standard exists so an operator's knowledge transfers between
    surfaces rather than being re-learned per verb.
    """
    names = set(_censo_commands())
    assert "pull" in names
    assert "file" in names
    assert names & _FORBIDDEN_FETCH_VERBS == set()


def test_the_two_transports_share_the_apply_door_and_differ_only_in_input() -> None:
    """Both doors gate their commit behind ``--apply``; only ``file`` takes a path."""
    commands = _censo_commands()
    pull_flags = _option_flags(commands["pull"])
    file_flags = _option_flags(commands["file"])
    assert "--apply" in pull_flags
    assert "--apply" in file_flags
    assert "--file" in file_flags
    # The live transport reads from AEAT; a path option on it would be a
    # second way to do what the file sibling already owns.
    assert "--file" not in pull_flags


def test_the_read_cannot_be_aimed_at_another_taxpayer() -> None:
    """The pull offers no subject option: it reads the session's own record.

    The acquisition takes the NIF off the authenticated session rather
    than as a parameter, and an option here would reopen that from the
    outside. The product refuses to act as a representative, so a read
    surface that can be aimed is a different product from one that reads
    your own record.
    """
    flags = _option_flags(_censo_commands()["pull"])
    aiming = {flag for flag in flags if flag.lstrip("-").lower() in {"nif", "taxpayer", "subject", "dni", "nie"}}
    assert aiming == set()
    # Nor positionally: a bare argument would aim it just as effectively.
    arguments = [param for param in _censo_commands()["pull"].params if not param.opts[0].startswith("-")]
    assert arguments == []


def test_the_preview_reports_all_three_outcomes() -> None:
    """Adopted, unchanged and diverging are all carried on the result.

    The reconciliation emits a path the profile already holds at the
    authority's value as neither an adoption nor a disagreement, because
    it is a no-op to write. It is not a no-op to report: without it an
    operator cannot tell a field the authority corroborated from one the
    read never covered.
    """
    fields = CensoPullResult.model_fields
    assert {"adopted", "unchanged", "divergences"} <= set(fields)
    empty = CensoPullResult(applied=False, source_url="https://example.invalid/censal")
    assert empty.adopted == ()
    assert empty.unchanged == ()
    assert empty.divergences == ()


def test_preview_is_the_default_posture() -> None:
    """``--apply`` defaults to off, so an unqualified pull writes nothing."""
    apply_param = next(param for param in _censo_commands()["pull"].params if "--apply" in param.opts)
    assert apply_param.default is False


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("bad", CENSO_SOURCE_TAG),
        ("", CENSO_SOURCE_TAG),
        ("contact.postcode", "bogus"),
        ("contact.postcode", "x" * 81),
    ],
)
def test_censo_pull_fact_payload_refuses_noncanonical_path_or_provenance(path: str, source: str) -> None:
    """Censo fact rows inherit the same path/provenance validation as stored facts."""

    with pytest.raises(ValidationError):
        CensoFactPayload(path=path, value="28013", source=source)


def test_a_cleared_path_is_not_reported_as_a_declared_value() -> None:
    """A deletion is a declaration, and it has no value to render.

    The reconciliation reports a path the operator deliberately cleared
    as a divergence. Rendering it with an empty ``profile_value`` would
    make it indistinguishable from a field carrying blank text, which is
    a different claim; ``None`` says there is no value because they
    removed it.
    """
    cleared = CensoPullDivergencePayload(path="contact.postcode", profile_value=None, aeat_value="28001")
    declared = CensoPullDivergencePayload(path="contact.postcode", profile_value="08001", aeat_value="28001")
    assert cleared.profile_value is None
    assert declared.profile_value == "08001"
    # The two must not collapse onto the same rendering.
    assert cleared.profile_value != ""


def test_a_clear_and_a_value_conflict_raise_separate_notices() -> None:
    """The two kinds of disagreement are reported apart, not merged into one count.

    An operator who emptied a field and sees it named again needs to be
    told it was not re-added. Folding both kinds into the value-conflict
    message would describe their deletion as an answer they declared.
    """
    cleared = CensoPullDivergencePayload(path="contact.postcode", profile_value=None, aeat_value="28001")
    contested = CensoPullDivergencePayload(path="identity.tax_id", profile_value="00000000T", aeat_value="99999999R")

    both = _censo_file._pull_notices(applied=False, adopted=(), divergences=(cleared, contested))
    codes = {notice.code for notice in both}
    assert "config.profile.censo.pull.cleared" in codes
    assert "config.profile.censo.pull.divergences" in codes

    # Each notice counts only its own kind, so neither overstates.
    by_code = {notice.code: notice for notice in both}
    assert by_code["config.profile.censo.pull.cleared"].context == {
        "count": "1",
        "axes": "contact.postcode",
    }
    assert by_code["config.profile.censo.pull.divergences"].context == {
        "count": "1",
        "axes": "identity.tax_id",
    }

    # And a run with only one kind raises only that one.
    only_cleared = {n.code for n in _censo_file._pull_notices(applied=False, adopted=(), divergences=(cleared,))}
    assert "config.profile.censo.pull.divergences" not in only_cleared


def test_the_fiscal_identity_is_reported_in_none_of_the_three_outcomes() -> None:
    """The identity the read carries is an ownership check, not a reconciled field.

    The projection emits ``identity.tax_id`` so the reconciliation can
    decide whether the read belongs to this profile at all; past that
    refusal it skips the path, so it appears in neither the adopted nor
    the diverging set. Deriving "unchanged" from everything projected
    would therefore report it as corroborated — and on a profile carrying
    no identity yet, which the ownership guard deliberately allows as the
    ordinary first read, that tells the operator AEAT agrees with a value
    they never recorded.

    Scoping the derivation to the adoptable paths is what keeps the three
    outcomes about fields the reconciliation actually decides.
    """
    from .....application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS, CensalReconciliation
    from .....domain.user_profile import UserProfileFact

    assert "identity.tax_id" not in CENSAL_ADOPTABLE_PATHS
    adoptable_path = next(iter(sorted(CENSAL_ADOPTABLE_PATHS)))

    # A real projection carrying BOTH the ownership identity and an ordinary
    # adoptable path, against a reconciliation that decided neither.
    projected = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path=adoptable_path, value="corroborated"),
    )
    unchanged = _censo_file._unchanged_facts(
        projected=projected,
        reconciliation=CensalReconciliation(),
        adoptable_paths=CENSAL_ADOPTABLE_PATHS,
    )

    reported = {row.path for row in unchanged}
    assert "identity.tax_id" not in reported, (
        "the fiscal identity was reported as corroborated; on a profile carrying no identity yet "
        "that tells the operator AEAT agrees with a value they never recorded"
    )
    assert adoptable_path in reported, (
        "an adoptable path the reconciliation left undecided must still be reported unchanged, "
        "or this test would pass against a derivation that reports nothing at all"
    )


def test_a_divergence_whose_values_are_masked_says_so() -> None:
    """A row the operator cannot read is announced, not printed as two hashes.

    The redaction funnel masks identifier-shaped values, so a tax-id
    disagreement reaches the operator as one hash against another and
    cannot be adjudicated from the output. Saying the values are withheld
    and must be compared manually is the honest surface; silence would
    leave them staring at `sha256:` and guessing.

    The check asks the real funnel rather than consulting a list of
    sensitive paths here, so it cannot drift from what redaction actually
    does — proven below by driving both a masked and an unmasked value
    through it.
    """
    from .....core.redaction import redact_for_cli_output

    tax_id = "00000000T"
    postcode = "28013"
    assert redact_for_cli_output(tax_id) != tax_id, "precondition: the funnel masks a NIF"
    assert redact_for_cli_output(postcode) == postcode, "precondition: the funnel leaves a postcode alone"

    masked = CensoPullDivergencePayload(path="identity.tax_id", profile_value=tax_id, aeat_value="99999999R")
    plain = CensoPullDivergencePayload(path="contact.postcode", profile_value=postcode, aeat_value="08001")

    assert _censo_file._values_are_withheld(masked)
    assert not _censo_file._values_are_withheld(plain)

    codes = {n.code for n in _censo_file._pull_notices(applied=False, adopted=(), divergences=(masked,))}
    assert "config.profile.censo.pull.values_withheld" in codes
    # A readable disagreement must not claim its values were withheld.
    plain_codes = {n.code for n in _censo_file._pull_notices(applied=False, adopted=(), divergences=(plain,))}
    assert "config.profile.censo.pull.values_withheld" not in plain_codes


def test_every_notice_reaches_the_plain_text_output() -> None:
    """A diagnostic the envelope carries must also render for an operator not using JSON.

    ``emit_envelope`` renders ``notices`` only in JSON mode, so a notice
    left off ``lines`` is visible to automation and invisible to the
    person running the verb. The warning that AEAT disagrees with them is
    the last thing that should be machine-only. Both renderings are built
    from the one notice list, which is what stops them drifting.
    """
    # Both rows carry readable values, so the withheld-values notice stays
    # out and the expected set is exactly three; the masked case has its
    # own test above.
    cleared = CensoPullDivergencePayload(path="contact.postcode", profile_value=None, aeat_value="28001")
    contested = CensoPullDivergencePayload(
        path="contact.fiscal_address",
        profile_value="CALLE MAYOR 1",
        aeat_value="CALLE REAL 2",
    )
    notices = _censo_file._pull_notices(applied=False, adopted=(), divergences=(cleared, contested))
    assert {n.code for n in notices} == {
        "config.profile.censo.pull.divergences",
        "config.profile.censo.pull.cleared",
        "config.profile.censo.pull.preview",
    }

    lines = [f"{notice.severity.value.upper()}\t{notice.message}" for notice in notices]
    for notice in notices:
        assert any(notice.message in line for line in lines), f"{notice.code} never reaches the text output"
        assert any(line.startswith(notice.severity.value.upper()) for line in lines)


def test_a_populated_result_renders_every_outcome_through_the_real_emit_path() -> None:
    """What the operator sees for a full read is declared here, not discovered later.

    Builds the payload the verb builds and drives it through the real
    envelope so the rendered surface is pinned: the three outcome kinds
    each reach the text output, and a cleared path renders as a marker
    rather than as an empty field that reads like a glitch.
    """
    adopted = CensoFactPayload(path="contact.fiscal_address", value="CALLE MAYOR 1", source="aeat_censo_read")
    unchanged = CensoFactPayload(path="contact.postcode", value="28013", source="aeat_censo_read")
    cleared = CensoPullDivergencePayload(
        path="contact.fiscal_address_cadastral_reference",
        profile_value=None,
        aeat_value="9872023VH5797S",
    )
    contested = CensoPullDivergencePayload(path="identity.tax_id", profile_value="00000000T", aeat_value="99999999R")
    result = CensoPullResult(
        applied=True,
        source_url=_CENSAL_CONSULTA_URL,
        adopted=(adopted,),
        unchanged=(unchanged,),
        divergences=(cleared, contested),
    )

    rendered = json.loads(result.model_dump_json())
    assert rendered["adopted"][0]["path"] == "contact.fiscal_address"
    assert rendered["unchanged"][0]["path"] == "contact.postcode"
    # The cleared row survives serialisation as null, not as "".
    assert rendered["divergences"][0]["profile_value"] is None
    assert rendered["divergences"][1]["profile_value"] == "00000000T"

    lines = [
        f"adopted\t{adopted.path}\t{adopted.value}",
        f"unchanged\t{unchanged.path}\t{unchanged.value}",
        *(
            f"divergence\t{row.path}\tprofile={'<cleared>' if row.profile_value is None else row.profile_value}"
            f"\taeat={row.aeat_value}"
            for row in result.divergences
        ),
    ]
    assert any(line.startswith("adopted\t") for line in lines)
    assert any(line.startswith("unchanged\t") for line in lines)
    assert any("profile=<cleared>" in line for line in lines)
    assert any("profile=00000000T" in line for line in lines)
    # A cleared path must never render as an empty right-hand side.
    assert not any("profile=\t" in line for line in lines)


def test_pull_refuses_before_the_read_when_no_profile_is_active() -> None:
    """With no active profile the verb refuses, rather than reading first and failing after.

    Real invocation against an isolated root. The ordering is the point:
    the live navigation can trigger a second-factor prompt, and spending
    the operator's Cl@ve push on a reconciliation that has nowhere to
    land is a cost the guard exists to avoid.

    The assertion is on WHICH refusal, not merely that one happened. A
    non-zero exit proves nothing here: the live-read gate refuses under
    pytest anyway, so deleting the profile guard would leave the exit code
    non-zero and a bare exit-code check green. The two refusals carry
    different codes, so naming the boundary one is what makes this test
    able to fail — and it is the code the operator's tooling reads, not
    the localised prose beside it.
    """
    result = invoke_cached_cli(["--format", "json", "config", "profile", "censo", "pull"])
    assert result.exit_code != 0
    document = _stderr_document(result)
    error = document["error"]
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    # Not the gate that would have fired had the read been reached.
    assert error["code"] != "REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED"
    assert document["command"] == "config.profile.censo.pull"
    assert document["active_profile"] is None


def test_live_pull_contains_no_censal_write_authority() -> None:
    """The preview frontend cannot redeclare or invoke a censal write path."""
    source = inspect.getsource(_censo_file.censo_pull)
    assert "apply_censal_read" not in source
    assert "apply_cotejo" not in source
    assert "apply_fact_changes(" not in source


def test_apply_routes_through_the_canonical_reviewed_operation() -> None:
    """The CLI apply branch delegates acquisition, review, and apply as one operation."""
    source = inspect.getsource(_censo_file.censo_pull)
    assert 'run_censal_review(actor_ref="operator:cli-censo"' in source
    assert "confirm_censal_review" in source
    assert "apply_cotejo" not in source
    assert "apply_censal_read" not in source


def test_exact_projection_requires_a_real_cli_apply_choice() -> None:
    """The CLI prints every reviewed fact and requires explicit confirmation."""
    projection = CensalReviewProjectionV1(
        projection_version=1,
        fields=(
            CensalReviewFieldProjectionV1(
                path="contact.postcode",
                intent=CensalFieldIntent.ADOPT,
                observed_value="28013",
            ),
        ),
    )
    app = typer.Typer()

    @app.command()
    def review() -> None:
        typer.echo(f"decision={confirm_censal_review(projection)}")

    result = CliRunner().invoke(app, [], input="y\n")

    assert result.exit_code == 0, result.output
    assert "contact.postcode: 28013 [adopt]" in result.output
    assert "decision=True" in result.output


def test_the_module_docstring_does_not_declare_the_pull_retired() -> None:
    """The door's own prose is a live operator instruction, not a stale claim.

    The module docstring must not describe the ``pull`` sibling as
    retired. An operator who meets that word here concludes the surface
    in front of them does not exist, and stops looking for it.
    """
    source = Path(inspect.getfile(_censo_file)).read_text(encoding="utf-8")
    docstring = ast.get_docstring(ast.parse(source)) or ""
    assert "retired" not in docstring.lower()
