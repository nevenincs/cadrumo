"""The OSS/IOSS detail-row closing path on an edition authored at calculation grade.

Every calculation runs this resolver, whatever the modelo. An edition that
reaches calculation grade and publishes no export layout must still calculate:
the closing path may not ask the authority for a filing-grade snapshot.
"""

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions_where,
    revision_covering,
    supported_authored_exercises,
)
from ....domain.calculations.registry.tests.published_authority import published_revision
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..oss_ioss_resolver import OssIossLedgerSourceResolver
from ..source_mesh import CalculationSourceContext
from .test_oss_detail_sections import BUCKET, Reader, Transactions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_a_calculation_grade_edition_without_export_layouts_closes_no_rows_and_is_not_refused(
    operation: PinnedAuthorityOperation,
) -> None:
    calculation_only = {
        str(revision.id)
        for revision in authored_revisions_where(
            "200",
            lambda revision: (
                revision.authority_grade is RegistryAuthorityGrade.CALCULATION
                and not published_revision("200", str(revision.id)).export_layouts
            ),
        )
    }
    assert calculation_only
    exercise = next(
        year
        for year in supported_authored_exercises("200")
        if str(revision_covering("200", year).id) in calculation_only
    )
    period = Period.from_year_and_code(exercise, "0A")
    revision = operation.revision("200", str(revision_covering("200", exercise).id))
    assert not revision.export_layouts

    resolution = OssIossLedgerSourceResolver(
        ports=InvoiceCatalogueReadPorts(invoice_reader=Reader(()), transaction_reader=Transactions())
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            work_unit_id="a" * 64,
            modelo="200",
            filing_year=exercise,
            period=period,
            revision=revision,
            operation=operation,
        )
    )

    assert resolution.closed_record_row_sets == ()
