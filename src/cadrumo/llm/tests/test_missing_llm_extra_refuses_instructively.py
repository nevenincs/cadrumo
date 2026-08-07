"""An absent imaging dependency refuses with the install hint, never a traceback.

The rasteriser's guard carries an unusual justification, and this module is what
turns that justification into something checkable. Pillow is never imported by
name anywhere in production: the page renderer reaches it from inside
``pypdfium2``'s ``to_pil()``. So an absent Pillow surfaces as a
``ModuleNotFoundError`` raised deep inside the render loop, where the
rasteriser's own ``except Exception`` catches it and re-raises it as "could not
rasterise PDF pages" -- reporting a missing dependency as a corrupt document,
and sending the operator to look at their PDF.

``require_optional_extra`` sits ahead of that loop to convert the deep failure
into one instructive refusal. Nothing proved it did, and the guard is exactly
the kind that rots unnoticed, because the condition it handles cannot be reached
by installing the product.

**Why a real install cannot reach it.** Pillow is declared in the ``llm`` extra
AND, deliberately, in the base dependencies -- the base entry exists to close an
undeclared-direct-reliance defect, since ``pdfplumber`` and ``pikepdf`` supply
Pillow incidentally and a change in either would break page rendering with no
resolution-time signal. The consequence is that ``pip install`` without the
extra still yields Pillow, so the extra is nominal today and the guard is
dormant. That is a correct packaging decision, not a defect; what it means for
testing is that the absent state has to be constructed rather than installed.

A meta-path finder in a fresh interpreter constructs it faithfully: the block is
installed before any product module is imported, and it RAISES rather than
returning ``None``, so a deep ``from PIL import ...`` inside a third-party
package fails exactly as it would against a genuinely absent distribution. No
mock, no patched guard -- the real refusal path, reached the real way.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

#: The import name :data:`~core.LLM_EXTRA` is registered under. Blocking THIS
#: name is what makes the constructed state correspond to the registered extra
#: rather than to some other absent package.
_IMAGING_IMPORT_NAME = "PIL"


def _run_rasteriser_with_blocked_imaging(*, block: bool) -> subprocess.CompletedProcess[str]:
    """Rasterise a one-page PDF in a fresh interpreter, optionally without Pillow.

    ``block`` parameterises the control rather than duplicating the runner, so
    the blocked and unblocked runs differ in exactly one respect and nothing
    else can explain a difference between them.
    """
    code = textwrap.dedent(
        f"""
        import io, os, sys
        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = "en"

        class _Blocked:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == {_IMAGING_IMPORT_NAME!r}:
                    raise ModuleNotFoundError(f"No module named {{fullname!r}}", name=fullname)
                return None

        # The fixture PDF is built BEFORE the block goes up, and the ordering is
        # load-bearing rather than tidy: reportlab imports Pillow itself, so
        # building afterwards fails inside the test's own scaffolding and the
        # run reports a traceback that has nothing to do with the guard.
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        page = canvas.Canvas(buf, pagesize=A4)
        page.drawString(72, 760, "factura")
        page.save()
        pdf_bytes = buf.getvalue()

        if {block!r}:
            # Purge what reportlab pulled in, so the block governs the product's
            # own resolution rather than being satisfied from a warm cache.
            for name in [n for n in sys.modules if n.split(".")[0] == {_IMAGING_IMPORT_NAME!r}]:
                del sys.modules[name]
            sys.meta_path.insert(0, _Blocked())

        from cadrumo.core import MissingOptionalExtraError
        from cadrumo.llm import rasterise_pdf_pages_to_base64_png

        try:
            pages = rasterise_pdf_pages_to_base64_png(pdf_bytes)
        except MissingOptionalExtraError as exc:
            print("REFUSED:" + str(exc))
        except Exception as exc:
            print(f"WRONG_ERROR:{{type(exc).__name__}}:{{exc}}")
        else:
            print(f"RENDERED:{{len(pages)}}")
        """,
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def test_absent_imaging_dependency_refuses_with_the_install_command() -> None:
    """The deep failure becomes one instructive refusal naming the remedy.

    The specific thing asserted is that the refusal is NOT the rasteriser's
    generic document-error wrapper. That wrapper is what an unguarded render
    would produce, it is a plausible-looking message, and it would send the
    operator to inspect a PDF that is perfectly fine.
    """
    completed = _run_rasteriser_with_blocked_imaging(block=True)
    output = completed.stdout.strip()

    assert "REFUSED:" in output, f"expected a typed missing-extra refusal, got: {output!r} {completed.stderr}"
    assert "could not rasterise PDF pages" not in output, (
        "a missing imaging dependency was reported as a broken document; the guard ahead of the "
        "render loop is not firing, which is the exact misdiagnosis it exists to prevent"
    )
    assert "Traceback" not in completed.stderr, completed.stderr
    # The refusal names the remedy. Asserted on the extra name rather than on the
    # full localised sentence, which is free to change.
    assert "llm" in output, f"the refusal must name the extra to install: {output!r}"


def test_the_same_call_renders_when_the_imaging_dependency_is_present() -> None:
    """Positive control: the block is what causes the refusal.

    Without this, the refusal above is equally consistent with a rasteriser that
    cannot render anything at all, or with a child interpreter that fails to
    import the product -- both of which would satisfy every assertion there.
    """
    completed = _run_rasteriser_with_blocked_imaging(block=False)
    output = completed.stdout.strip()

    assert output.startswith("RENDERED:"), f"the unblocked run must render, got: {output!r} {completed.stderr}"
    assert int(output.removeprefix("RENDERED:")) >= 1, "a one-page PDF must rasterise to at least one page"
