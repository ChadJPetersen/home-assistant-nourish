"""Check manifest/changelog consistency and PR version bump discipline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components/nourish/manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
HEADING = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s+—\s+\d{4}-\d{2}-\d{2}\s*$", re.M)


def run_git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Git commit SHA of the pull request base")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print("Manifest version must be X.Y.Z", file=sys.stderr)
        return 1
    changelog = CHANGELOG.read_text(encoding="utf-8")
    headings = HEADING.findall(changelog)
    if not headings or headings[0] != version:
        print(f"CHANGELOG first version must match manifest ({version})", file=sys.stderr)
        return 1

    if args.base:
        changed = run_git("diff", "--name-only", args.base, "HEAD").splitlines()
        runtime_changed = any(p.startswith("custom_components/nourish/") for p in changed)
        if runtime_changed:
            try:
                previous = json.loads(
                    run_git("show", f"{args.base}:custom_components/nourish/manifest.json")
                )["version"]
            except (subprocess.CalledProcessError, ValueError, KeyError) as err:
                print(f"Could not read base manifest: {err}", file=sys.stderr)
                return 1
            if previous == version:
                print("Integration files changed without a manifest version bump", file=sys.stderr)
                return 1
            if "CHANGELOG.md" not in changed:
                print("Integration files changed without a changelog update", file=sys.stderr)
                return 1
    print(f"Release checks passed for {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
