"""Autodoc rendering for Pydantic field annotations with parser-sensitive metadata."""

from __future__ import annotations

from typing import Any, override

from docutils.statemachine import StringList
from pydantic import BaseModel
from sphinx.application import Sphinx
from sphinx.ext.autodoc import AttributeDocumenter
from sphinx.util.inspect import signature as sphinx_signature
from sphinx.util.typing import get_type_hints

from .rendering import attribute_type_components


class ApiAttributeDocumenter(AttributeDocumenter):
    """Keep constrained metadata intact without feeding regexes to RST parsing."""

    _rendered_field_type: tuple[str, str | None] | None = None

    @override
    def update_annotations(self, parent: Any) -> None:
        """Keep inherited Pydantic annotations in their defining namespace.

        Sphinx copies source annotations from every base onto the documented
        class. Pydantic subsequently interprets ``__pydantic_extra__`` as an
        explicit subclass annotation, resolving BaseModel's ``Dict`` against
        the application module and leaving new subclasses incomplete. Model
        fields already have runtime annotations, so no source backfill is needed.
        """
        if isinstance(parent, type) and issubclass(parent, BaseModel):
            return
        super().update_annotations(parent)

    @override
    def add_line(self, line: str, source: str, *lineno: int) -> None:
        """Replace only a field's generated type line when its annotation needs it."""
        rendered = self._rendered_field_type
        if rendered is not None and line.startswith("   :type: "):
            line = f"   :type: {rendered[0]}"
        super().add_line(line, source, *lineno)

    @override
    def add_directive_header(self, sig: str) -> None:
        """Delegate the standard header and substitute only supported field types."""
        self._rendered_field_type = None
        if self.config.autodoc_typehints != "none" and self.options.annotation is None:
            annotations = get_type_hints(
                self.parent,
                None,
                self.config.autodoc_type_aliases,
                include_extras=True,
            )
            annotation = annotations.get(self.objpath[-1])
            if annotation is not None:
                rendered = attribute_type_components(annotation)
                if (
                    rendered is not None
                    and "\n" not in rendered[0]
                    and (rendered[1] is None or "\n" not in rendered[1])
                ):
                    self._rendered_field_type = rendered
        super().add_directive_header(sig)

    @override
    def add_content(self, more_content: StringList | None) -> None:
        """Add constraint metadata as literal prose in the attribute body."""
        rendered = self._rendered_field_type
        try:
            if rendered is not None and rendered[1] is not None:
                source = self.get_sourcename()
                self.add_line(f"Constraint: ``{rendered[1]}``", source)
                self.add_line("", source)
            super().add_content(more_content)
        finally:
            self._rendered_field_type = None


def render_signature_constraints(
    app: Sphinx,
    what: str,
    name: str,
    obj: Any,
    options: object,
    lines: list[str],
) -> None:
    """Keep constrained signature types out of Sphinx's raw annotation fields.

    sphinx.ext.autodoc.typehints records annotations directly from the Python
    signature, bypassing ``typehints_formatter``. Its later merge reads the
    current document's annotation map, so normalize only supported annotated
    parameters after sphinx-autodoc-typehints has added its docstring fields.
    """
    del what, options
    current_document = app.env.current_document
    annotations = getattr(current_document, "autodoc_annotations", None)
    if not isinstance(annotations, dict):
        return
    object_annotations = annotations.get(name)
    if not isinstance(object_annotations, dict):
        return

    try:
        signature = sphinx_signature(obj, type_aliases=app.config.autodoc_type_aliases)
    except (TypeError, ValueError):
        return

    constraints: list[tuple[str, str]] = []
    for parameter in signature.parameters.values():
        rendered = attribute_type_components(parameter.annotation)
        if rendered is None or rendered[1] is None:
            continue
        object_annotations[parameter.name] = rendered[0]
        constraints.append((parameter.name, rendered[1]))

    if constraints:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(f"Constraint for ``{parameter}``: ``{metadata}``." for parameter, metadata in constraints)


def setup(app: Sphinx) -> dict[str, bool]:
    """Register the attribute documenter after Sphinx's standard autodoc setup."""
    app.add_autodocumenter(ApiAttributeDocumenter, override=True)
    # sphinx-autodoc-typehints records raw signature annotations at priority 500.
    app.connect("autodoc-process-docstring", render_signature_constraints, priority=501)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
