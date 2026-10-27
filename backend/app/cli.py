"""Command line helper.

    python -m app.cli fetch    # live fetch from Elexon, write the gzipped snapshot
    python -m app.cli info     # describe the snapshot currently on disk

`fetch` needs network access to the Elexon API. Commit the resulting snapshot only if you
are happy to publish that data (it is public Elexon data, but check the licence terms).
"""

from __future__ import annotations

import sys

from .config import load_settings
from .elexon import ElexonError
from .store import DataStore


def main(argv: list[str]) -> int:
    settings = load_settings()
    store = DataStore(settings)
    cmd = argv[1] if len(argv) > 1 else "info"
    if cmd == "fetch":
        try:
            ds = store.refresh()
        except ElexonError as exc:
            print(f"Fetch failed: {exc}", file=sys.stderr)
            return 1
        print(f"Snapshot written to {store.snapshot_path}")
        print(f"actuals: {ds.actual_quality.as_dict()}")
        print(f"forecasts: {ds.forecast_quality.as_dict()}")
        return 0
    if cmd == "info":
        path = store.snapshot_path
        print(f"{path}: {'present' if path.exists() else 'absent'}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
