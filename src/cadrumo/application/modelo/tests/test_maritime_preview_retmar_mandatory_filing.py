"""The RETMAR mandatory-filing answer survives the incomplete-profile rerun.

When the active profile is missing a fact the full exemption resolution needs,
the preview reruns that resolution against facts with the RETMAR flag
deliberately CLEARED. That is the only way to obtain observations at all from
incomplete data, and it is correct as far as it goes -- but it means the rerun
result carries ``retmar_mandatory_filing=False`` on exactly the path where the
real answer may be ``True``.

The renderer was compensating for that. It read
``result.retmar_mandatory_filing or facts.retmar_registered``, reaching past the
muddled result to the untouched fact. The answer it produced was right, so
nothing failed and nothing pinned it: the end-to-end test that covers this path
asserts the flag is ``True`` for a registered taxpayer, which the ``or`` also
satisfies, so the two sources were never distinguished.

That is what this test exists to separate. It asserts the two DISAGREE on the
warning path -- the result says false, the preview says true -- which is only
meaningful once the preview answers from the facts rather than from the rerun.
A future change that made the preview read the result again would fail here
rather than silently telling a registered taxpayer their filing is optional.
"""

from __future__ import annotations

import pytest

from ....application.calculations._maritime_exemption_service import (
    resolve_maritime_exemption,
    retmar_mandatory_filing,
)
from ....domain.renta.maritime_exemption import MaritimeWorkerFacts, ProfileCompletenessError
from .._maritime_preview import ModeloMaritimeExemptionPreview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A registered taxpayer whose profile is missing what the resolution needs.
#: Registration is the fact under test; the rest is deliberately unstated, which
#: is what drives the resolution to refuse and the preview to rerun.
_REGISTERED_BUT_INCOMPLETE = MaritimeWorkerFacts(
    worker_class="trabajador_del_mar",
    retmar_registered=True,
)


def _preview_as_the_warning_path_builds_it() -> ModeloMaritimeExemptionPreview:
    """Reproduce the preview the incomplete-profile branch constructs.

    Built through the real resolution rather than a stub, so the result carries
    whatever that function actually returns for cleared facts. A hand-made
    result would prove only that this test can set a boolean.
    """
    with pytest.raises(ProfileCompletenessError) as excinfo:
        resolve_maritime_exemption(
            facts=_REGISTERED_BUT_INCOMPLETE,
            annual_salary=None,
            qualifying_days=None,
            gross_navigation_income=None,
        )

    cleared = MaritimeWorkerFacts(
        worker_class=_REGISTERED_BUT_INCOMPLETE.worker_class,
        retmar_registered=False,
    )
    return ModeloMaritimeExemptionPreview(
        facts=_REGISTERED_BUT_INCOMPLETE,
        result=resolve_maritime_exemption(
            facts=cleared,
            annual_salary=None,
            qualifying_days=None,
            gross_navigation_income=None,
        ),
        retmar_warning_error=excinfo.value,
    )


def test_the_rerun_result_understates_mandatory_filing() -> None:
    """The rerun result is false for a registered taxpayer, by construction.

    Pinned so the rest of this file is not asserting a property that happens to
    agree with an already-correct result. If the rerun ever stopped clearing the
    flag this would fail, and the preview's property would become redundant
    rather than load-bearing -- a fact worth learning from a failure.
    """
    preview = _preview_as_the_warning_path_builds_it()

    assert preview.result.retmar_mandatory_filing is False


def test_the_preview_reports_mandatory_filing_from_the_original_facts() -> None:
    """The preview answers true where its own result says false."""
    preview = _preview_as_the_warning_path_builds_it()

    assert preview.facts.retmar_registered is True
    assert preview.retmar_mandatory_filing is True
    assert preview.retmar_mandatory_filing != preview.result.retmar_mandatory_filing


def test_the_preview_defers_to_the_service_determination() -> None:
    """The preview does not restate the rule, it asks for it.

    Guards the shape rather than the value: the answer must agree with the
    service's own determination over the same facts for every input, so that a
    second condition joining that function reaches this surface too. That was
    the concrete risk in the renderer version -- a hand-folded ``or`` would have
    gone on returning the old answer.
    """
    for registered in (True, False):
        facts = MaritimeWorkerFacts(worker_class="trabajador_del_mar", retmar_registered=registered)
        preview = ModeloMaritimeExemptionPreview(
            facts=facts,
            result=resolve_maritime_exemption(
                facts=MaritimeWorkerFacts(worker_class="trabajador_del_mar", retmar_registered=False),
                annual_salary=None,
                qualifying_days=None,
                gross_navigation_income=None,
            ),
        )
        assert preview.retmar_mandatory_filing == retmar_mandatory_filing(facts)
