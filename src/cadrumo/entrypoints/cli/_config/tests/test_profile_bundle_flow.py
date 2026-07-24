"""Real-behavior proofs for the interactive profile bundle export / import flow.

The interactive mode is a presentation over the one canonical bundle
path: the flow collects only the answers the operator omitted from
``argv``, and everything it collects is acted on by the same
:func:`~cadrumo.application.user_profile.export_profile_bundle` service
and import validation gates a fully-specified invocation uses. The
proofs below drive the real flow engine (scripted canonical tokens — the
identical validation and branching every frontend runs), the real
export authority, and the real CLI import command over real encrypted
storage; nothing is mocked.

The roundtrip proof follows ``aeat-roundtrip-discipline``: a bundle
exported through flow-collected answers is imported into a second,
fresh storage root through the live CLI import verb, re-exported there,
and the two on-disk bundles must be strictly equal as
:class:`~cadrumo.domain.user_profile.UserProfilePortableExport` models
(modulo the provenance-only ``exported_at`` stamp the bundle documents
as non-content-addressable).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....application.flows import run_scripted_flow
from .....application.user_profile import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
    export_profile_bundle,
)
from .....core.flows import CheckpointAvailability, FlowMode, FlowWidgetKind
from .....domain.user_profile import UserProfilePortableExport
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root
from .._profile_bundle_flow import (
    build_export_flow_definition,
    build_import_flow_definition,
    export_request_from_state,
    import_request_from_state,
    registered_run_copy_table,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUN_TOKEN = "test-run-token"  # noqa: S105 - opaque copy-table run token, not a secret


def _export_definition(
    *,
    profile_labels: tuple[str, ...] = ("subject", "gestor-client"),
    active_label: str | None = "subject",
    include_profile_page: bool = True,
    include_destination_page: bool = True,
    include_transport_page: bool = True,
    copy_table: dict[str, str] | None = None,
):
    return build_export_flow_definition(
        run_token=_RUN_TOKEN,
        copy_table=copy_table if copy_table is not None else {},
        profile_labels=profile_labels,
        active_label=active_label,
        include_profile_page=include_profile_page,
        include_destination_page=include_destination_page,
        include_transport_page=include_transport_page,
    )


def _page_widgets(definition) -> dict[str, FlowWidgetKind]:
    return {page.id: page.widget for section in definition.sections for page in section.items}


def test_export_definition_declares_exactly_the_missing_pages() -> None:
    full = _export_definition()
    assert _page_widgets(full) == {
        "profile": FlowWidgetKind.SELECT,
        "destination": FlowWidgetKind.PATH,
        "transport": FlowWidgetKind.SELECT,
    }

    partial = _export_definition(include_profile_page=False, include_transport_page=False)
    assert _page_widgets(partial) == {"destination": FlowWidgetKind.PATH}

    no_profiles = _export_definition(profile_labels=(), active_label=None)
    assert "profile" not in _page_widgets(no_profiles)


def test_neither_definition_carries_a_secret_page_or_checkpointing() -> None:
    """The passphrase never enters a flow page and no answer may persist mid-run.

    The bundle passphrase rides the shared ``_secure_input`` channel
    only; a SECRET page here would put a secret into the flow answer
    map, and an AVAILABLE checkpoint arm would persist collected
    answers to disk mid-run. Both are structurally refused by the
    definitions.
    """
    for definition in (
        _export_definition(),
        build_import_flow_definition(include_label_page=True),
    ):
        widgets = _page_widgets(definition).values()
        assert FlowWidgetKind.SECRET not in widgets
        assert definition.checkpoint == {
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        }


def test_transport_choices_are_the_canonical_transport_taxonomy() -> None:
    """The transport SELECT re-uses the typed export-transport axis verbatim."""
    definition = _export_definition(include_profile_page=False, include_destination_page=False)
    (transport_page,) = [page for section in definition.sections for page in section.items]
    assert {choice.value for choice in transport_page.choices} == {
        member.value for member in ProfileBundleExportTransport
    }
    assert transport_page.default == ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED.value


def test_profile_choices_resolve_through_the_run_scoped_copy_table() -> None:
    copy_table: dict[str, str] = {}
    definition = _export_definition(copy_table=copy_table)
    (profile_page,) = [page for section in definition.sections for page in section.items if page.id == "profile"]
    assert {choice.value for choice in profile_page.choices} == {"subject", "gestor-client"}
    assert profile_page.default == "subject"
    for choice in profile_page.choices:
        assert copy_table[choice.label.ref] == choice.value


def test_scripted_export_run_yields_a_complete_request() -> None:
    definition = _export_definition()
    state, _projection = run_scripted_flow(
        definition,
        ("gestor-client", str(Path("out") / "bundle.json"), "cleartext_local"),
        mode=FlowMode.CREATE,
    )
    request = export_request_from_state(
        state,
        name=None,
        destination=None,
        encrypt=False,
        cleartext_local=False,
    )
    assert request.profile_name == "gestor-client"
    assert request.destination == Path("out") / "bundle.json"
    assert request.encrypt is False


def test_scripted_export_run_never_overrides_argv_values() -> None:
    definition = _export_definition(include_profile_page=False, include_destination_page=False)
    state, _projection = run_scripted_flow(
        definition,
        (ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED.value,),
        mode=FlowMode.CREATE,
    )
    request = export_request_from_state(
        state,
        name="subject",
        destination=Path("argv-bundle.json"),
        encrypt=False,
        cleartext_local=False,
    )
    assert request.profile_name == "subject"
    assert request.destination == Path("argv-bundle.json")
    assert request.encrypt is True


def test_scripted_import_run_collects_path_and_optional_label() -> None:
    definition = build_import_flow_definition(include_label_page=True)
    state, _projection = run_scripted_flow(
        definition,
        (str(Path("in") / "bundle.json"), "client-copy"),
        mode=FlowMode.CREATE,
    )
    request = import_request_from_state(state, label=None)
    assert request.path == Path("in") / "bundle.json"
    assert request.label == "client-copy"

    blank_state, _projection = run_scripted_flow(
        build_import_flow_definition(include_label_page=True),
        (str(Path("in") / "bundle.json"), ""),
        mode=FlowMode.CREATE,
    )
    assert import_request_from_state(blank_state, label=None).label is None

    argv_state, _projection = run_scripted_flow(
        build_import_flow_definition(include_label_page=False),
        (str(Path("in") / "bundle.json"),),
        mode=FlowMode.CREATE,
    )
    assert import_request_from_state(argv_state, label="argv-label").label == "argv-label"


def _create_profile(label: str) -> None:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            label,
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--entity-type",
            "natural_person",
            "--name",
            "Subject",
            "--surnames",
            "Access",
        ],
    )
    assert result.exit_code == 0, result.output


def test_flow_collected_export_imports_back_to_a_strictly_equal_bundle(tmp_path: Path) -> None:
    """Roundtrip: flow-collected export → live CLI import → re-export → equality."""
    bundle_path = tmp_path / "portable-bundle.json"

    with isolated_profile_storage_root(tmp_path=tmp_path / "source-root"):
        _create_profile("subject")
        definition = _export_definition(
            profile_labels=("subject",),
            active_label="subject",
        )
        state, _projection = run_scripted_flow(
            definition,
            ("subject", str(bundle_path), "cleartext_local"),
            mode=FlowMode.CREATE,
        )
        request = export_request_from_state(
            state,
            name=None,
            destination=None,
            encrypt=False,
            cleartext_local=False,
        )
        export_profile_bundle(
            ProfileBundleExportRequest(
                profile_name=request.profile_name,
                destination=request.destination,
                purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
            ),
        )

    exported = UserProfilePortableExport.model_validate_json(bundle_path.read_text(encoding="utf-8"))

    reexport_path = tmp_path / "reexported-bundle.json"
    with isolated_profile_storage_root(tmp_path=tmp_path / "target-root"):
        import_definition = build_import_flow_definition(include_label_page=True)
        import_state, _projection = run_scripted_flow(
            import_definition,
            (str(bundle_path), ""),
            mode=FlowMode.CREATE,
        )
        import_request = import_request_from_state(import_state, label=None)
        import_result = invoke_cached_cli(
            ["config", "profile", "import", str(import_request.path)],
        )
        assert import_result.exit_code == 0, import_result.output

        reexport_result = invoke_cached_cli(
            [
                "config",
                "profile",
                "export",
                "subject",
                "--to",
                str(reexport_path),
                "--cleartext-local",
            ],
        )
        assert reexport_result.exit_code == 0, reexport_result.output

    reexported = UserProfilePortableExport.model_validate_json(reexport_path.read_text(encoding="utf-8"))
    # ``exported_at`` is documented non-content-addressable provenance, and the
    # import path REGISTERS a new profile record in the recipient store, so its
    # ``created_at`` / ``updated_at`` are recipient-local registration stamps,
    # not carried bundle content. Every carried field — identity facts, status,
    # display name, financial history, carried objects, coverage — must be
    # strictly equal.
    normalized = reexported.model_copy(
        update={
            "exported_at": exported.exported_at,
            "profile": reexported.profile.model_copy(
                update={
                    "created_at": exported.profile.created_at,
                    "updated_at": exported.profile.updated_at,
                },
            ),
        },
    )
    assert normalized == exported


# ── frontend render drives ──────────────────────────────────────────────────
#
# The definitions' static copy is locale-key references; the shipped
# catalogues own the production prose. The sanctioned locale-root override
# supplies a fixture catalogue carrying the same keys so the render-time
# copy assembler runs its real resolution path headlessly, exactly as the
# substrate's own frontend tests do.

_COPY_CATALOGUE: dict[str, object] = {
    "cli": {
        "config": {
            "profile": {
                "export_help": "Export a profile bundle",
                "import_help": "Import a profile bundle",
                "export_name_help": "Profile to export",
                "export_out_help": "Destination path",
                "import_path_help": "Path to the profile bundle",
                "import_label_help": "Label for the imported profile",
                "bundle_flow": {
                    "export_section_title": "Export profile bundle",
                    "import_section_title": "Import profile bundle",
                    "transport_prompt": "How should the bundle be written?",
                    "transport_encrypted_label": "Encrypted",
                    "transport_encrypted_description": "AEAD passphrase encryption",
                    "transport_cleartext_label": "Cleartext",
                    "transport_cleartext_description": "Unencrypted local JSON",
                },
            },
        },
    },
}


@pytest.fixture
def _bundle_flow_copy_catalogue(tmp_path_factory: pytest.TempPathFactory):
    import yaml

    from .....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, override_locales_root

    root = tmp_path_factory.mktemp("bundle-flow-locales")
    payload = yaml.safe_dump(_COPY_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")
    with override_locales_root(root):
        yield


def test_line_mode_renders_and_submits_the_export_flow(_bundle_flow_copy_catalogue) -> None:
    """Pipe-driven line-mode walk over the real questionary prompts."""
    from io import StringIO

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output.plain_text import PlainTextOutput

    from .....application.flows import LineFlowFrontend

    down = "\x1b[B"  # questionary select: move highlight down one row
    with registered_run_copy_table(_RUN_TOKEN) as copy_table:
        definition = _export_definition(copy_table=copy_table)
        with create_pipe_input() as pipe:
            # profile: down+enter picks 'gestor-client'; destination typed;
            # transport: enter keeps the encrypted arm; review: submit.
            pipe.send_text(f"{down}\rout-bundle.json\r\r\r")
            frontend = LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(StringIO()))
            state, projection = frontend.run(mode=FlowMode.CREATE)

    assert projection.submit_eligible
    request = export_request_from_state(
        state,
        name=None,
        destination=None,
        encrypt=False,
        cleartext_local=False,
    )
    assert request.profile_name == "gestor-client"
    assert request.destination == Path("out-bundle.json")
    assert request.encrypt is True


def test_line_mode_renders_and_submits_the_import_flow(_bundle_flow_copy_catalogue) -> None:
    from io import StringIO

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output.plain_text import PlainTextOutput

    from .....application.flows import LineFlowFrontend

    definition = build_import_flow_definition(include_label_page=True)
    with create_pipe_input() as pipe:
        pipe.send_text("in-bundle.json\rclient-copy\r\r")
        frontend = LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(StringIO()))
        state, projection = frontend.run(mode=FlowMode.CREATE)

    assert projection.submit_eligible
    request = import_request_from_state(state, label=None)
    assert request.path == Path("in-bundle.json")
    assert request.label == "client-copy"


@pytest.mark.asyncio
async def test_full_screen_app_renders_and_submits_the_export_flow(_bundle_flow_copy_catalogue) -> None:
    """Headless Textual Pilot drive of the export definition end to end."""
    from .....adapters.inbound.tui import FlowTuiApp

    with registered_run_copy_table(_RUN_TOKEN) as copy_table:
        definition = _export_definition(copy_table=copy_table)
        app = FlowTuiApp(definition, mode=FlowMode.CREATE)
        async with app.run_test(size=(140, 60)) as pilot:
            await pilot.press("2")  # profile SELECT: numbered option 'gestor-client'
            await pilot.pause()
            await pilot.press(*"outbundle")  # destination PATH input
            await pilot.click("#btn-next")
            await pilot.press("1")  # transport SELECT: the encrypted arm
            await pilot.pause()
            await pilot.press("f2")  # review
            await pilot.press("s")  # submit
            await pilot.pause()

        assert app.final_state is not None

    request = export_request_from_state(
        app.final_state,
        name=None,
        destination=None,
        encrypt=False,
        cleartext_local=False,
    )
    assert request.profile_name == "gestor-client"
    assert request.destination == Path("outbundle")
    assert request.encrypt is True
