"""AEAT top-level CLI command routing.

Provides the Typer-based CLI application entry point.
"""

import typer

app = typer.Typer(help="AEAT Automation CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """AEAT Command Line Interface."""
    pass


@app.command()
def hello() -> None:
    """A proof-of-concept command."""
    typer.echo("Hello from AEAT CLI")


__all__ = ["app"]
