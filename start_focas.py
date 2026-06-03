from __future__ import annotations

import os
import runpy
import sys


def main() -> None:
    candidates = [
        "/home/admin/app",
        "/home/admin/app/app",
        os.getcwd(),
        os.path.join(os.getcwd(), "app"),
    ]
    for candidate in candidates:
        server = os.path.join(candidate, "focas_api", "server.py")
        if os.path.exists(server):
            os.chdir(candidate)
            sys.path.insert(0, candidate)
            runpy.run_module("focas_api.server", run_name="__main__")
            return

    print(f"Cannot locate focas_api. Current directory: {os.getcwd()}")
    for root, dirs, _files in os.walk("/home/admin"):
        if "focas_api" in dirs:
            print(os.path.join(root, "focas_api"))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
