"""``_stamp.py``'s three exception-formatting refusal sites never echo a raw payload.

:func:`~dev.registry.conformance._stamp.stamp_revision` writes governance
provenance -- who engineered or reviewed a revision -- and every value it
handles is caller-supplied free text. Three sites in that module format an
arbitrary underlying exception into the ``StampError`` message a caller sees,
and the CLI's ``stamp`` command relays that message verbatim as a
:exc:`typer.BadParameter`, so whatever lands in a ``StampError`` reaches the
terminal.

Two of the three sites wrap :exc:`~pydantic.ValidationError` (directly, or
nested inside a :class:`~cadrumo.domain.calculations.registry.errors.RegistryError`
from the loader). Measured here: ``str(ValidationError)`` appends an
``input_value=`` fragment holding a length-truncated repr of the WHOLE
validated payload, and a SHORT reviewer identity survives that truncation
whole while a longer one happens to fall inside the elided middle -- a leak
whose presence depends on incidental string length, not on anything a caller
decided. That leak is REPRODUCED here for the schema-probe site
(``_assert_schema_accepts``); the loader site (``_assert_revision_is_compiled``)
turns out to be structurally protected today because the loader always
appends a long computed ``localization_key`` as the payload's last entry, and
that is documented, not assumed, where the loader test lives. The fix covers
both sites identically anyway, because nothing about that protection is a
contract either site can rely on. The third site wraps
:exc:`tomllib.TOMLDecodeError`, whose messages are measured here to be purely
positional (line/column) and never echo the offending literal, so it needs a
test proving that stays true rather than a code change.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from .._stamp import (
    StampError,
    _assert_revision_is_compiled,  # pyright: ignore[reportPrivateUsage]
    _assert_schema_accepts,  # pyright: ignore[reportPrivateUsage]
    _declared_governance,  # pyright: ignore[reportPrivateUsage]
    _Stamp,  # pyright: ignore[reportPrivateUsage]
    bundled_registry_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Reviewer identities spanning the exact length band measured to control
#: whether pydantic's truncated ``input_value=`` repr happens to retain the
#: literal (a single character survives; a longer taxpayer-shaped string does
#: not) -- the fix must hide all of them, not just the ones that were already
#: accidentally elided by string length.
_REVIEWER_IDENTITIES_BY_LENGTH = ("X", "nif-Z", "12345678Z-Juan-Perez-Garcia-secret-taxpayer-nif-value")


# ── Site: schema validation refusal (`_assert_schema_accepts`) ──────────────


@pytest.mark.parametrize("reviewed_by", _REVIEWER_IDENTITIES_BY_LENGTH)
def test_schema_refusal_never_carries_the_reviewer_identity(reviewed_by: str) -> None:
    """A reviewer supplied without the reviewed_at date is refused by the real schema.

    ``review_status="agent_reviewed"`` with no ``reviewed_at`` is genuinely
    malformed input to :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`:
    the coherence validator refuses it regardless of what ``reviewed_by`` says,
    so the refusal message must never depend on ``reviewed_by`` either.
    """
    resolved = _Stamp(engineered_by=None, review_status="agent_reviewed", reviewed_by=reviewed_by, reviewed_at=None)

    with pytest.raises(StampError) as excinfo:
        _assert_schema_accepts("2019-y-siguientes", resolved)

    message = str(excinfo.value)
    assert reviewed_by not in message


def test_schema_refusal_message_is_independent_of_the_reviewer_identity() -> None:
    """Assert the complement: the message text does not vary with the payload at all.

    Stronger than a substring check on any one identity: every identity in
    :data:`_REVIEWER_IDENTITIES_BY_LENGTH` -- including the one PROVEN, before
    the fix, to survive pydantic's truncation whole -- must produce the exact
    same message. A message that is byte-identical across payloads cannot be
    carrying any of them.
    """
    messages = set()
    for reviewed_by in _REVIEWER_IDENTITIES_BY_LENGTH:
        resolved = _Stamp(
            engineered_by=None,
            review_status="agent_reviewed",
            reviewed_by=reviewed_by,
            reviewed_at=None,
        )
        with pytest.raises(StampError) as excinfo:
            _assert_schema_accepts("2019-y-siguientes", resolved)
        messages.add(str(excinfo.value))

    assert messages == {
        "refused governance stamp for revision '2019-y-siguientes': Value error, revision "
        "'2019-y-siguientes' declares review_status='agent_reviewed' but omits ['reviewed_at']; "
        "a reviewed revision must name its reviewer and the date of review",
    }


def test_schema_refusal_never_carries_pydantics_own_value_dump() -> None:
    """Pin the absence of pydantic's own added framing, not just the secret.

    ``ValidationError.__str__`` appends ``[type=..., input_value=..., input_type=...]``
    and a documentation URL after the validator's own message; a fix that
    happened to hide today's secret but left that framing intact would still
    be one string-length coincidence away from a future leak.
    """
    resolved = _Stamp(engineered_by=None, review_status="agent_reviewed", reviewed_by="nif-Z", reviewed_at=None)

    with pytest.raises(StampError) as excinfo:
        _assert_schema_accepts("2019-y-siguientes", resolved)

    message = str(excinfo.value)
    assert "input_value" not in message
    assert "input_type" not in message
    assert "errors.pydantic.dev" not in message


def test_schema_refusal_still_names_the_revision_and_the_missing_field() -> None:
    """The fix must not trade the leak for an unhelpful message.

    Remediation stays: the revision id and the field the caller must supply are
    still named, because that text comes from the validator's own ``msg``, not
    from pydantic's payload dump.
    """
    resolved = _Stamp(engineered_by=None, review_status="agent_reviewed", reviewed_by="agent:x", reviewed_at=None)

    with pytest.raises(StampError, match=r"2019-y-siguientes.*reviewed_at"):
        _assert_schema_accepts("2019-y-siguientes", resolved)


# ── Site: registry-load refusal (`_assert_revision_is_compiled`) ────────────


def _modelo_130_with_a_short_unattributed_reviewer(tmp_path: Path, *, reviewed_by: str) -> Path:
    """A real, loadable modelo tree with one deliberately incoherent governance stamp.

    Copied whole from the shipped registry rather than hand-built, so the
    failure is reached through the REAL loader on a REAL fragmented tree, per
    this project's rule that a gate exercises the real authority path. Only the
    two governance lines are rewritten.
    """
    modelo_dir = tmp_path / "130"
    shutil.copytree(bundled_registry_root() / "modelos" / "130", modelo_dir)
    manifest = modelo_dir / "revisions" / "2019-y-siguientes" / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    assert 'reviewed_by = "agent-prepared-pending-operator"' in text
    text = text.replace(
        'reviewed_by = "agent-prepared-pending-operator"',
        f'reviewed_by = "{reviewed_by}"',
    )
    lines = [line for line in text.splitlines() if not line.startswith("reviewed_at = ")]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return modelo_dir


@pytest.mark.parametrize("reviewed_by", _REVIEWER_IDENTITIES_BY_LENGTH)
def test_load_refusal_never_carries_the_reviewer_identity(tmp_path: Path, reviewed_by: str) -> None:
    """The same coherence rule, now refused by the LOADER rather than the probe.

    A shipped-shaped revision.toml declaring ``agent_reviewed`` with a reviewer
    but no date fails to load at all -- ``_assert_revision_is_compiled`` wraps
    whatever :func:`~cadrumo.domain.calculations.registry.loader.load_modelo_directory`
    raises, and that ``RegistryError`` itself embeds the SAME pydantic
    ``ValidationError`` one layer down.

    Measured, not assumed: against a real shipped-shaped tree this path did NOT
    reproduce a leak even before the fix, for any identity in
    :data:`_REVIEWER_IDENTITIES_BY_LENGTH` -- the loader always appends a
    computed ``localization_key`` (``modelo.schema.<id>.revision.<id>.field.label``)
    as the LAST dict entry before validation, and that fixed-shape tail
    reliably survives pydantic's truncation in ``reviewed_by``'s place, pushing
    a short reviewer into the elided middle instead. This test pins that this
    site is closed regardless, as defense-in-depth: the mechanism is the exact
    one PROVEN exploitable at ``_assert_schema_accepts`` (see
    ``test_schema_refusal_never_carries_the_reviewer_identity``), and nothing
    guarantees every payload shape a future revision or validator can reach
    this call with keeps that same protective tail.
    """
    modelo_dir = _modelo_130_with_a_short_unattributed_reviewer(tmp_path, reviewed_by=reviewed_by)

    with pytest.raises(StampError) as excinfo:
        _assert_revision_is_compiled(modelo_dir, modelo="130", revision="2019-y-siguientes")

    message = str(excinfo.value)
    assert reviewed_by not in message
    assert "input_value" not in message
    assert "errors.pydantic.dev" not in message
    assert "130" in message
    assert "reviewed_at" in message


# ── Site: manifest TOML decode refusal (`_declared_governance`) ─────────────


#: Malformed manifest bodies, each carrying a taxpayer-shaped literal in the
#: position that breaks parsing. None of these are pydantic-mediated: tomllib
#: raises its own `TOMLDecodeError` before any schema ever sees the payload.
_MALFORMED_MANIFESTS = (
    pytest.param(
        '[revisions."2019-y-siguientes"]\nreviewed_by = "12345678Z-secret-taxpayer-nif\n',
        "12345678Z-secret-taxpayer-nif",
        id="unterminated_string",
    ),
    pytest.param(
        '[revisions."2019-y-siguientes"]\nreviewed_by = "34567890X-secret"\nreviewed_by = "collision"\n',
        "34567890X-secret",
        id="duplicate_key",
    ),
)


@pytest.mark.parametrize(("manifest_text", "secret"), _MALFORMED_MANIFESTS)
def test_toml_decode_refusal_never_carries_the_offending_literal(
    tmp_path: Path,
    manifest_text: str,
    secret: str,
) -> None:
    """Confirm, rather than assume, that ``tomllib``'s own errors stay positional.

    This is the one refusal site this module cannot fix by changing what it
    formats, because there is nothing to extract: ``tomllib.TOMLDecodeError``
    carries no structured field list. So this test is the reproduction proving
    the premise -- pydantic and TOML errors both routinely echo the offending
    literal -- does NOT hold for tomllib, using inputs shaped to be as
    leak-prone as possible (the secret is the value tomllib is actively
    scanning when it fails).
    """
    manifest = tmp_path / "revision.toml"

    # `tomllib` itself never echoes the literal -- reproduced directly so this
    # test also demonstrates why `_declared_governance` needs no fix here.
    with pytest.raises(tomllib.TOMLDecodeError) as raw_excinfo:
        tomllib.loads(manifest_text)
    assert secret not in str(raw_excinfo.value)

    with pytest.raises(StampError) as excinfo:
        _declared_governance(manifest, manifest_text, "2019-y-siguientes")

    message = str(excinfo.value)
    assert secret not in message
    assert str(manifest) in message
    assert "not valid TOML" in message


def test_toml_decode_refusal_names_the_manifest_and_stays_a_stamp_error() -> None:
    """The manifest path is a stable identifier the message MUST keep.

    Complement of the leak assertions above: this pins what the message DOES
    carry, so a future change cannot silently drop the one thing a caller
    needs to go fix the file.
    """
    manifest = Path("modelos") / "130" / "revisions" / "2019-y-siguientes" / "revision.toml"
    with pytest.raises(StampError, match=r"not valid TOML") as excinfo:
        _declared_governance(manifest, "not = [valid", "2019-y-siguientes")
    assert str(manifest) in str(excinfo.value)


# ── Cross-site regression guard ─────────────────────────────────────────────


def test_none_of_the_three_refusal_sites_reach_pydantics_raw_input_dump(tmp_path: Path) -> None:
    """One assertion spanning all three sites, so a regression in any of them fails loudly.

    Each branch below reproduces the malformed input the corresponding
    production caller (``stamp_revision``, the CLI ``stamp`` command) can
    actually construct, using the same short, easy-to-miss reviewer identity
    that was proven to leak before the fix.
    """
    leak_prone_reviewer = "nif-Z"

    schema_resolved = _Stamp(
        engineered_by=None,
        review_status="agent_reviewed",
        reviewed_by=leak_prone_reviewer,
        reviewed_at=None,
    )
    with pytest.raises(StampError) as schema_excinfo:
        _assert_schema_accepts("2019-y-siguientes", schema_resolved)

    modelo_dir = _modelo_130_with_a_short_unattributed_reviewer(tmp_path, reviewed_by=leak_prone_reviewer)
    with pytest.raises(StampError) as load_excinfo:
        _assert_revision_is_compiled(modelo_dir, modelo="130", revision="2019-y-siguientes")

    with pytest.raises(StampError) as toml_excinfo:
        _declared_governance(
            Path("revision.toml"),
            f'[revisions."2019-y-siguientes"]\nreviewed_by = "{leak_prone_reviewer}\n',
            "2019-y-siguientes",
        )

    for excinfo in (schema_excinfo, load_excinfo, toml_excinfo):
        message = str(excinfo.value)
        assert leak_prone_reviewer not in message
        assert "input_value" not in message
