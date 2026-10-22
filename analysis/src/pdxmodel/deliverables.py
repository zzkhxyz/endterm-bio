"""Synchronize site assets and package a clean submission archive."""

from __future__ import annotations

import argparse
import logging
import shutil
import zipfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]


def web_data() -> None:
    """Copy pipeline outputs needed by the statically exported site."""
    public = ROOT / "web/public"
    (public / "data").mkdir(parents=True, exist_ok=True)
    for source, target in (
        (ROOT / "analysis/outputs/results.json", public / "data/results.json"),
        (ROOT / "report/report.pdf", public / "report.pdf"),
    ):
        if not source.exists():
            raise FileNotFoundError(f"Generate the prerequisite first: {source}")
        shutil.copyfile(source, target)
        LOGGER.info("Copied %s to %s", source, target)


def make_zip() -> Path:
    """Package the report, README, and reproducible analysis without raw XLSX."""
    archive = ROOT / "submission.zip"
    required = [ROOT / "report/report.pdf", ROOT / "README.md"]
    if any(not path.exists() for path in required):
        raise FileNotFoundError("Build the report before packaging")
    files = required + [
        path
        for path in (ROOT / "analysis").rglob("*")
        if path.is_file()
        and "raw" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
        and path.suffix not in {".pyc", ".xlsx"}
    ]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in files:
            output.write(path, path.relative_to(ROOT).as_posix())
    LOGGER.info("Created %s with %d files", archive, len(files))
    return archive


def main() -> None:
    """Run the requested delivery action."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["web-data", "zip"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.action == "web-data":
        web_data()
    else:
        make_zip()


if __name__ == "__main__":
    main()
