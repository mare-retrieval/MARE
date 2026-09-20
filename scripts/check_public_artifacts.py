"""Fail if internal skill files are tracked or included in distribution archives."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def _is_internal_skill(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "skills" in parts or "SKILL.md" in parts


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    exposed = [path for path in tracked if path and _is_internal_skill(path)]

    for archive in Path("dist").glob("*"):
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
        elif archive.name.endswith(".tar.gz"):
            with tarfile.open(archive, "r:gz") as package:
                names = package.getnames()
        else:
            continue
        exposed.extend(f"{archive}: {name}" for name in names if _is_internal_skill(name))

    if exposed:
        print("Internal skill files would be public:", *exposed, sep="\n", file=sys.stderr)
        return 1
    print("No internal skill files tracked or packaged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
