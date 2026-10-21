"""Stage the recorded test host as the installed desktop image of a package mirror, and name both.

The packaged end-to-end tests start the same remote-debugging host the lane
does, and the desktop supervises its runtime only as an installed image, so
they start it from this mirror too. Prints one JSON line with the package root
and the image to start; exits 3 when the host or its staged package is absent
or older than its sources.
"""

from __future__ import annotations

import argparse
import json

from .lane import UnavailableError, require_current, stage_package, test_host


def main(argv: list[str] | None = None) -> int:
    """Stage the mirror and print where it is."""
    parser = argparse.ArgumentParser(prog="stage-host", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--served", action="store_true", help="Stage the host whose shell the dev server serves.")
    options = parser.parse_args(argv)
    try:
        host = test_host(options.served)
        require_current(host)
        image = stage_package(host, host.lane_package)
    except UnavailableError as absent:
        print(json.dumps({"step": "unavailable", "reason": str(absent)}), flush=True)
        return 3
    print(json.dumps({"package": str(host.lane_package), "executable": str(image)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
