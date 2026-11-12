"""The parse boundary of a counterparty filing name's ``--rendering WIDTH=TEXT`` option.

It lives apart from the command handler so command-schema and help discovery,
which resolve every option's parser, load no behaviour target.
"""

from __future__ import annotations

from ...application.ledger.counterparty_operation import CounterpartyFilingNameRendering
from ...core.cli_value_parsers import refuse_cli_value
from ...core.i18n.render import tr


def parse_filing_name_rendering(value: object) -> CounterpartyFilingNameRendering:
    """Read one ``WIDTH=TEXT`` rendering at the parse boundary, refusing one that names no width."""
    if isinstance(value, CounterpartyFilingNameRendering):
        return value
    rendering = str(value)
    width, separator, text = rendering.partition("=")
    if not separator or not width.isdigit() or int(width) == 0 or not text:
        refuse_cli_value(tr("cli.ledger.counterparty.errors.rendering_malformed", rendering=rendering))
    return CounterpartyFilingNameRendering(width=int(width), text=text)
