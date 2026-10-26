"""Historical 216 keeps its own identity fields and seven-partida byte geometry."""

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from shutil import copytree

import pytest

from cadrumo.core import atomic_write
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field

from ...compiler.authority import compiled_bundled_authority
from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ...form_layout.reconciliation import install_authored_export_reconciliation, reconcile_authored_export_addition
from ...form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from .._export_tree import render_complete_export_tree
from ..authored_form_bridge import prepare_authored_form_bridge
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _with_export(before, layout):
    references = derive_casilla_export_refs((layout,), before.bindings)
    casillas = tuple(c.model_copy(update={"export_refs": references.get(c.id, ())}) for c in before.casillas)
    return before.model_copy(update={"export_layouts": (layout,), "casillas": casillas})


def _omit_historical_export(directory, names):
    path = Path(directory)
    return {"export"} if path.name == "2020-2023" and path.parent.parent.name == "216" else set()


@pytest.fixture(scope="module")
def historical_before(tmp_path_factory):
    """Reconstruct the authored liquidation-only state before first publication."""
    root = tmp_path_factory.mktemp("before-export") / "216"
    copytree(Path("src/cadrumo/_data/registry/aeat/modelos/216"), root, ignore=_omit_historical_export)
    revision = load_modelo_directory(root).revisions["2020-2023"]
    layout = revision.form_layouts[0]
    page = layout.pages[0]
    page = page.model_copy(update={"sections": tuple(s for s in page.sections if s.id == "liquidacion")})
    layout = layout.model_copy(update={"pages": (page,)})
    revision = revision.model_copy(update={"form_layouts": (layout,)})
    layout = layout.model_copy(update={"source_state_digest": form_layout_source_digest(revision)})
    form_layout_fragment_path(root / "revisions" / "2020-2023").write_text(
        render_form_layout_toml("2020-2023", layout), encoding="utf-8", newline="\n"
    )
    before = load_modelo_directory(root).revisions["2020-2023"]
    assert not before.export_layouts
    assert form_layout_failures(before) == ()
    return before, root


@pytest.fixture(scope="module")
def historical_rendered(tmp_path_factory):
    authority = compiled_bundled_authority()
    revision = authority.modelo("216").revisions["2020-2023"]
    bootstrap = (
        None
        if revision.export_layouts
        else GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-216-2020-2023-fichero",
            line_ending="none",
            source_ref="aeat-dr-216-2020-2023",
            source_sha256="a68460b791ed6c14d698eb0aef3752eda9d407c4fc9b3249d0e4053887f9fee8",
        )
    )
    inputs = revision_render_inputs(
        authority,
        modelo="216",
        revision="2020-2023",
        source_ref="aeat-dr-216-2020-2023",
        filing_year=2023,
        period="4T",
        bootstrap_transport=bootstrap,
    )
    target = tmp_path_factory.mktemp("historical-216") / "export"
    rendered = render_complete_export_tree(
        target,
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    return rendered, target


@pytest.fixture(scope="module")
def historical_layout(historical_rendered):
    return historical_rendered[0].layout


def test_historical_identity_and_payment_fields_use_the_historical_offsets(historical_layout):
    fields = {str(f.id).removeprefix("modelo-216-page-01-"): f for f in historical_layout.records[0].fields}
    for name, offset, length, producer in (
        ("apellidos", 23, 60, "taxpayer.surnames_or_legal_name"),
        ("nombre", 83, 20, "taxpayer.given_name"),
        ("iban", 228, 34, "selected_account.iban"),
        ("complementaria", 262, 1, "amendment_evidence.is_complementaria"),
        ("complementaria-justificante", 263, 13, "amendment_evidence.original_aeat_receipt"),
    ):
        field = fields[name]
        assert (field.offset, field.length, str(field.producer_key)) == (offset, length, producer)
    assert (fields["close"].offset, fields["close"].length) == (389, 12)
    assert render_fixed_width_export_field(fields["devengo-ejercicio"], 2023) == "2023"


def test_historical_counts_and_money_do_not_share_a_decimal_scale(historical_layout):
    fields = {str(f.casilla_id): f for f in historical_layout.records[0].fields if f.casilla_id is not None}
    assert set(fields) == {str(n) for n in range(1, 8)}
    for n in range(1, 8):
        field = fields[str(n)]
        assert (field.offset, field.length) == (109 + (n - 1) * 17, 17)
        if n in (1, 4):
            assert render_fixed_width_export_field(field, 123) == "0" * 14 + "123"
            with pytest.raises(RegistryValidationError):
                render_fixed_width_export_field(field, Decimal("1.25"))
        else:
            assert render_fixed_width_export_field(field, Decimal("123.45")) == "0" * 12 + "12345"
        with pytest.raises(RegistryValidationError):
            render_fixed_width_export_field(field, -1)


def test_first_export_reconciliation_preserves_the_authored_design(historical_layout, historical_before):
    before, _root = historical_before
    after = _with_export(before, historical_layout)
    reconciled = reconcile_authored_export_addition(before, after)
    original = before.form_layouts[0]
    assert reconciled.source_state_digest != original.source_state_digest
    assert reconciled.model_dump(exclude={"source_state_digest"}) == original.model_dump(
        exclude={"source_state_digest"}
    )
    assert form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)})) == ()
    assert before.form_layouts == (original,)


@pytest.mark.parametrize("change", ["casilla", "presentation", "stale", "existing_export", "missing_reverse_edges"])
def test_first_export_reconciliation_cannot_bless_other_changes(historical_layout, historical_before, change):
    before, _root = historical_before
    after = _with_export(before, historical_layout)
    if change == "casilla":
        changed = after.casillas[0].model_copy(update={"number": "99"})
        after = after.model_copy(update={"casillas": (changed, *after.casillas[1:])})
    elif change == "presentation":
        changed_form = after.form_layouts[0].model_copy(update={"pages": ()})
        after = after.model_copy(update={"form_layouts": (changed_form,)})
    elif change == "stale":
        stale_form = before.form_layouts[0].model_copy(update={"source_state_digest": "0" * 64})
        before = before.model_copy(update={"form_layouts": (stale_form,)})
        after = after.model_copy(update={"form_layouts": (stale_form,)})
    elif change == "missing_reverse_edges":
        after = after.model_copy(update={"casillas": before.casillas})
    else:
        before = before.model_copy(update={"export_layouts": (historical_layout,)})
    with pytest.raises(RegistryValidationError):
        reconcile_authored_export_addition(before, after)


@pytest.mark.parametrize(
    "tamper", [None, "old_receipt", "new_receipt", "authored_edit", "write_failure", "replace_failure", "staged_edit"]
)
def test_form_owner_installs_only_the_prevalidated_reconciliation(
    tmp_path: Path, historical_rendered, historical_before, tamper, monkeypatch: pytest.MonkeyPatch
):
    rendered, export_root = historical_rendered
    before, before_root = historical_before
    modelo_root = tmp_path / "216"
    copytree(before_root, modelo_root)
    revision_root = modelo_root / "revisions" / "2020-2023"
    copytree(export_root, revision_root / "export")
    form = form_layout_fragment_path(revision_root)
    original = form.read_bytes()
    reconciled = reconcile_authored_export_addition(before, _with_export(before, rendered.layout))
    expected = render_form_layout_toml(str(before.id), reconciled).encode("utf-8")
    old_sha = sha256(original).hexdigest()
    new_sha = sha256(expected).hexdigest()
    if tamper == "old_receipt":
        old_sha = "0" * 64
    elif tamper == "new_receipt":
        new_sha = "0" * 64
    elif tamper == "authored_edit":
        form.write_bytes(original + b"# concurrent author edit\n")
    pre_attempt = form.read_bytes()

    def fail_write(fd, data):
        atomic_write.os.write(fd, data[:10])
        raise OSError("injected partial write")

    def fail_replace(source, target):
        raise OSError("injected replacement failure")

    if tamper in {"write_failure", "replace_failure"}:
        if tamper == "write_failure":
            monkeypatch.setattr(atomic_write, "write_all", fail_write)
        else:
            monkeypatch.setattr(atomic_write.os, "replace", fail_replace)
        with pytest.raises(OSError, match="injected"):
            install_authored_export_reconciliation(
                modelo_root, before=before, expected_old_sha256=old_sha, expected_new_sha256=new_sha
            )
        assert form.read_bytes() == pre_attempt
    elif tamper == "staged_edit":
        original_write = atomic_write.write_all

        def edit_during_staging(fd, data):
            original_write(fd, data)
            form.write_bytes(original + b"# edit during staging\n")

        monkeypatch.setattr(atomic_write, "write_all", edit_during_staging)
        with pytest.raises(RegistryValidationError, match="changed before write"):
            install_authored_export_reconciliation(
                modelo_root, before=before, expected_old_sha256=old_sha, expected_new_sha256=new_sha
            )
        assert form.read_bytes() == original + b"# edit during staging\n"
    elif tamper is not None:
        with pytest.raises(RegistryValidationError):
            install_authored_export_reconciliation(
                modelo_root, before=before, expected_old_sha256=old_sha, expected_new_sha256=new_sha
            )
        assert form.read_bytes() == pre_attempt
    else:
        install_authored_export_reconciliation(
            modelo_root, before=before, expected_old_sha256=old_sha, expected_new_sha256=new_sha
        )
        assert form.read_bytes() == expected
    assert tuple(form.parent.iterdir()) == (form,)


def test_first_export_bridge_prevalidates_and_detects_a_changed_form(
    tmp_path: Path, historical_rendered, historical_before
):
    _rendered, export_root = historical_rendered
    source_root = Path("src/cadrumo/_data").resolve()
    live = tmp_path / "live" / "aeat"
    candidate = tmp_path / "candidate" / "aeat"
    copytree(source_root / "registry" / "aeat", live, ignore=_omit_historical_export)
    before, _before_root = historical_before
    form_layout_fragment_path(live / "modelos/216/revisions/2020-2023").write_text(
        render_form_layout_toml("2020-2023", before.form_layouts[0]), encoding="utf-8", newline="\n"
    )
    copytree(live, candidate)
    relative = Path("modelos/216/revisions/2020-2023")
    copytree(export_root, candidate / relative / "export")
    live_form = form_layout_fragment_path(live / relative)
    original = live_form.read_bytes()
    bridge = prepare_authored_form_bridge(
        registry_root=live,
        candidate_root=candidate,
        source_root=source_root,
        temporary_root=tmp_path,
        modelo="216",
        revision="2020-2023",
    )
    assert live_form.read_bytes() == original
    assert not (live / relative / "export").exists()
    # Simulate the separate export owner's completed source interval.
    copytree(export_root, live / relative / "export")
    bridge.require_export_cutover()
    live_form.write_bytes(original + b"# later author edit\n")
    with pytest.raises(RegistryValidationError, match="form changed"):
        bridge.finish_with_form_owner(live, source_root)
    assert live_form.read_bytes().endswith(b"# later author edit\n")
    live_form.write_bytes(original)
    bridge.finish_with_form_owner(live, source_root)
    revision = load_modelo_directory(live / "modelos" / "216").revisions["2020-2023"]
    assert form_layout_failures(revision) == ()
    assert live_form.read_bytes() == form_layout_fragment_path(candidate / relative).read_bytes()
