"""The served Modelo form models resolve their field annotations at import and restore from their public mirror.

A frontend client restores a form from its public mirror without ever building
the canonical models first, so a canonical annotation left as a forward
reference at import reaches the restoration unresolved. The models defer
building their validators, so a resolved annotation, not a built model, is what
the restoration needs. Both checks therefore
run in a fresh interpreter that has imported the modules and done nothing else.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ...operations.public_mirror import project_public_mirror
from ..edit_models import ModeloEditBindingIntentKind
from ..work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ..work_form_models import ModeloFormBindingStatement, ModeloFormField
from ..workbench_projection import PublicModeloFormField

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CARRY = "modelo-100-base-liquidable-negativa-pendiente"


def _completed(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _field_with_statements() -> ModeloFormField:
    statements = (
        ModeloFormBindingStatement(
            intent=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
            binding_id=_CARRY,
            action_words="State nothing is pending",
            statement_words="Nothing is pending from earlier years.",
            effect_words="The carry is stated as nothing.",
        ),
        ModeloFormBindingStatement(
            intent=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            binding_id=_CARRY,
            action_words="State the earlier figure",
            statement_words="The figure comes from an earlier return.",
            effect_words="The carry takes the stated figure.",
            source_words="the earlier return",
        ),
    )
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id("1380")),
        box="1380",
        label=ModeloFormText(text="Pending negative base", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        help=None,
        data_type="money",
        value=Decimal("0.00"),
        origin=ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        editability=ModeloFormEditability.EDITABLE_VALUE,
        required=False,
        statements=statements,
    )


def test_every_served_form_model_resolves_its_field_annotations_at_import() -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import inspect, typing\n"
            "from pydantic import BaseModel\n"
            "from cadrumo.application.modelo import work_form_models, workbench_projection\n"
            "for module in (work_form_models, workbench_projection):\n"
            "    for name, member in vars(module).items():\n"
            "        if not (inspect.isclass(member) and issubclass(member, BaseModel)):\n"
            "            continue\n"
            "        if member.__module__ != module.__name__:\n"
            "            continue\n"
            "        unresolved = [field for field, info in member.model_fields.items()\n"
            "                      if isinstance(info.annotation, (str, typing.ForwardRef))]\n"
            "        if unresolved:\n"
            "            print(module.__name__, name, unresolved)\n",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ),
        check=False,
    )
    assert _completed(probe) == ""


def test_a_field_with_statements_restores_from_its_public_mirror_in_a_fresh_client() -> None:
    field = _field_with_statements()
    public = project_public_mirror(field, ModeloFormField, PublicModeloFormField)
    assert isinstance(public, PublicModeloFormField)

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from cadrumo.application.operations.public_mirror import restore_public_mirror\n"
            "from cadrumo.application.modelo.work_form_models import ModeloFormField\n"
            "from cadrumo.application.modelo.workbench_projection import PublicModeloFormField\n"
            "public = PublicModeloFormField.model_validate_json(sys.stdin.read())\n"
            "restored = restore_public_mirror(public, ModeloFormField, PublicModeloFormField)\n"
            "assert isinstance(restored, ModeloFormField), type(restored)\n"
            "print(restored.model_dump_json())\n",
        ],
        input=public.model_dump_json(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ),
        check=False,
    )

    assert json.loads(_completed(probe)) == json.loads(field.model_dump_json())
