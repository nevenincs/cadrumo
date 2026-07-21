"""Shared Typer option and argument aliases for the ``modelo work`` command family.

The work-unit addressing surface — ``WORK_UNIT_ID`` plus ``--modelo``,
``--year``, ``--period``, ``--revision``, ``--bucket-id``, and ``--by`` — is
identical across every ``aeat app modelo work`` verb (wizard, amend wizard,
calculate, reconcile, verification, revision, lifecycle). Declaring the
:class:`~typing.Annotated` aliases once here keeps a single home for the shared
``cli.app.modelo.work.*`` help keys, so ``--help`` renders byte-identically for
every verb from one ``tr`` lookup rather than a per-module re-declaration.

A verb that addresses only a subset of these axes imports only the aliases it
uses; a verb whose help copy diverges (a different ``tr`` key) keeps its own
local alias rather than sharing one here.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ...core.external_constants import OutputLanguage
from ...core.i18n import tr

_WorkUnitIdArg = Annotated[str | None, typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help"))]
_CalculationRevisionIdArg = Annotated[
    str | None, typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help"))
]
_ModeloOpt = Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help"))]
_YearOpt = Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.work.year_help"))]
_PeriodOpt = Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.work.period_help"))]
_RevisionOpt = Annotated[str | None, typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help"))]
_RegistryRevisionOpt = Annotated[
    str | None, typer.Option("--registry-revision", help=tr("cli.app.modelo.work.revision_help"))
]
_BucketIdOpt = Annotated[str | None, typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help"))]
_ActorOpt = Annotated[str | None, typer.Option("--by", help=tr("cli.app.modelo.work.actor_help"))]
_NameOpt = Annotated[str | None, typer.Option("--name", help=tr("cli.app.modelo.work.name_help"))]
_WorkUnitIdOpt = Annotated[str | None, typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help"))]
_RevisionSelectorOpt = Annotated[
    str,
    typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector.")),
]
_WizardOutputLanguageOpt = Annotated[
    OutputLanguage | None, typer.Option("--output-language", help=tr("cli.app.modelo.work.output_language_help"))
]
