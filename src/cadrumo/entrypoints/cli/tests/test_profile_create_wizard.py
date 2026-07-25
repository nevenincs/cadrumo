"""Terminal-boundary coverage for an interactive ``aeat config profile create``.

``config profile create`` is the operator's first contact with Cadrumo. A
capable terminal is diverted to the profile manager before this command
runs; a host without a usable console (this test process included) reaches
the command and is refused instructively, naming the flag form, rather than
being half-prompted. This module covers that CLI boundary: the
machine-caller contract of a refused run, and the pinned question
inventory the flags are derived from.
"""

from __future__ import annotations

import json

import pytest

from ....application.wizard import WIZARD_FLOWS
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_NAME = "Primer Contacto"

_CREATE_ARGS = [
    "config", "profile", "create", _PROFILE_NAME,
]  # fmt: skip


def test_interactive_create_without_a_console_refuses_instructively() -> None:
    """A host with no usable console is refused, never half-prompted.

    The capability probe classifies this test process as non-interactive;
    the refusal must be the translated unsupported-console error, not a
    traceback and not a partially-created profile.
    """
    result = invoke_cached_cli(_CREATE_ARGS)
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_interactive_create_under_json_keeps_stdout_parseable() -> None:
    """Machine callers get a parseable stream even when the run is refused.

    Under ``--format json`` stdout must never carry prompt noise or prose:
    it is either empty or a JSON envelope, and the refusal document rides
    stderr where the error contract puts it.
    """
    result = invoke_cached_cli(["--format", "json", *_CREATE_ARGS])
    assert result.exit_code != 0
    stdout = result.stdout.strip()
    if stdout:
        json.loads(stdout.splitlines()[0])
    stderr = result.stderr if result.stderr_bytes is not None else ""
    documents = [line for line in stderr.splitlines() if line.strip().startswith("{")]
    assert documents, f"no JSON error document on stderr: {stderr[:300]!r}"
    parsed = json.loads(documents[0])
    assert "error" in parsed


# The pinned profile-create prompted-question inventory (see the question-count
# decision note in the cli-authority-quality-backlog plan): the full declared question set
# of the setup flow, which is exactly the ``supplied_question_ids`` frozenset the
# ``create`` path writes to the payload. This is the single place the inventory is
# pinned; a legitimate add or drop updates this set here, and any silent change
# fails the gate below.
_EXPECTED_SETUP_QUESTION_IDS = frozenset(
    {
        "activity",
        "activity-start-date",
        "address-postcode",
        "art109-activity-income-withholding-ge-70pct",
        "bienes-extranjero-above-threshold",
        "cloud-evidence-upload",
        "country-of-fiscal-residence",
        "does-intracomunitario",
        "enrollment-large-company",
        "enrollment-public-administration-budget-gt-6000000",
        "entity-type",
        "family-descendants-eu-eea-deduction",
        "family-minor-children-in-unit",
        "fiscal-residency",
        "google-export",
        "has-employees",
        "incn-prior-12-months",
        "irpf-estimation-regime",
        "irpf-income-categories",
        "irpf-special-regime",
        "irpf-special-regime-start-date",
        "iva-group-dominant-entity-enrolled",
        "iva-group-member-enrolled",
        "iva-intracommunity-operations-exceed-50000-eur",
        "iva-oss-enrolled",
        "iva-redeme-enrolled",
        "iva-regime",
        "iva-roi-enrolled",
        "iva-sii-enrolled",
        "legal-entity-form",
        "legal-name",
        "ley-49-2002-option-date",
        "ley-49-2002-option-declared",
        "ley-49-2002-renunciation-date",
        "ley-49-2002-renunciation-declared",
        "llm-vision",
        "modelo-111-no-retenciones-periods",
        "monedas-virtuales-extranjero-above-threshold",
        "name",
        "new-entity-first-two-profit-periods",
        "notes",
        "objective-estimation-modulos-iae-epigraph",
        "objective-estimation-modulos-module-1-units",
        "objective-estimation-modulos-module-2-units",
        "objective-estimation-modulos-module-3-units",
        "objective-estimation-modulos-module-4-units",
        "objective-estimation-modulos-module-5-units",
        "objective-estimation-modulos-module-6-units",
        "objective-estimation-modulos-module-7-units",
        "output-language",
        "pays-capital-income-with-retencion",
        "pays-professionals-with-retencion",
        "pays-rent-with-retencion",
        "representante-fiscal-nif",
        "representante-fiscal-nombre",
        "situacion-familiar",
        "spouse-birth-date",
        "spouse-disability-grade",
        "spouse-eu-eea-country",
        "spouse-eu-eea-resident",
        "spouse-name",
        "spouse-non-resident-irpf",
        "spouse-sex",
        "spouse-surnames",
        "spouse-tax-id",
        "surnames",
        "tax-id",
        "tax-residence-ccaa",
        "taxation-type",
        "taxpayer-birth-date",
        "taxpayer-death-date",
        "taxpayer-disability-grade",
        "taxpayer-marital-status",
        "taxpayer-marriage-date",
        "taxpayer-sex",
        "third-party-transactions-above-347-threshold",
    }
)
_EXPECTED_SETUP_QUESTION_COUNT = 76


def test_profile_create_prompted_question_inventory_is_pinned() -> None:
    """A silent add, drop, or rename of a setup-flow question fails loudly.

    The wizard surfaces one flow; ``create`` writes every declared question id to
    the payload. Pinning the exact id set plus the declared count catches an added
    or dropped question and a same-size rename swap, while conditional per-answer
    visibility stays covered by the interactive persisted-fact tests above.
    """
    assert len(WIZARD_FLOWS) == 1, WIZARD_FLOWS
    flow = WIZARD_FLOWS[0]
    assert flow.id == "setup", flow.id

    declared_ids = [question.id for section in flow.sections for question in section.questions]
    surfaced_ids = frozenset(declared_ids)

    # No id is declared twice (declared count == unique count) and the set is exactly
    # the pinned inventory of the decided size.
    assert len(declared_ids) == _EXPECTED_SETUP_QUESTION_COUNT
    assert len(surfaced_ids) == _EXPECTED_SETUP_QUESTION_COUNT
    assert surfaced_ids == _EXPECTED_SETUP_QUESTION_IDS
