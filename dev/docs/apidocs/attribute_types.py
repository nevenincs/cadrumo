"""Autodoc rendering for Pydantic field annotations with parser-sensitive metadata."""

from __future__ import annotations

from typing import override

from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.ext.autodoc import AttributeDocumenter
from sphinx.util.typing import get_type_hints

from .rendering import attribute_type_components


class ApiAttributeDocumenter(AttributeDocumenter):
    """Keep constrained metadata intact without feeding regexes to RST parsing."""

    _rendered_field_type: tuple[str, str | None] | None = None

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


def setup(app: Sphinx) -> dict[str, bool]:
    """Register the attribute documenter after Sphinx's standard autodoc setup."""
    app.add_autodocumenter(ApiAttributeDocumenter, override=True)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
