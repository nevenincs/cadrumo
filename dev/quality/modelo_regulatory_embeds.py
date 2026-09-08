"""Fail while modelo-specific registry modules embed regulatory literals."""

from __future__ import annotations

from ..registry.analysis.modelo_embed_scan import census


def main() -> None:
    """Print every current finding and exit non-zero until the set is empty."""
    evidence = tuple(item for record in census() for item in record.evidence)
    if not evidence:
        return
    print(f"modelo-specific registry embeds: {len(evidence)} finding(s); expected zero")
    for item in evidence:
        print(f"  + {item.render()}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
