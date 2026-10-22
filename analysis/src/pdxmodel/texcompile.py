"""Compile the report with a pinned official Tectonic binary if needed."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.17.0"
ASSETS = {
    ("Windows", "AMD64"): "x86_64-pc-windows-msvc.zip",
    ("Linux", "x86_64"): "x86_64-unknown-linux-gnu.tar.gz",
    ("Darwin", "arm64"): "aarch64-apple-darwin.tar.gz",
    ("Darwin", "x86_64"): "x86_64-apple-darwin.tar.gz",
}


def tectonic_binary() -> Path:
    """Use PATH or obtain the pinned official GitHub release in ignored work/."""
    installed = shutil.which("tectonic")
    if installed:
        return Path(installed)
    local = ROOT / "work/tectonic/bin" / ("tectonic.exe" if platform.system() == "Windows" else "tectonic")
    if local.exists():
        return local
    key = (platform.system(), platform.machine())
    suffix = ASSETS.get(key)
    if not suffix:
        raise RuntimeError(f"Install Tectonic {VERSION} for unsupported platform {key}")
    name = f"tectonic-{VERSION}-{suffix}"
    url = f"https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40{VERSION}/{name}"
    download = ROOT / "work/tectonic" / name
    local.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading official Tectonic release %s", url)
    urllib.request.urlretrieve(url, download)
    if suffix.endswith(".zip"):
        with zipfile.ZipFile(download) as source:
            source.extract("tectonic.exe", local.parent)
    else:
        with tarfile.open(download, "r:gz") as source:
            member = next(item for item in source.getmembers() if Path(item.name).name == "tectonic")
            with source.extractfile(member) as stream, local.open("wb") as output:
                if stream is None:
                    raise RuntimeError("Tectonic archive is missing its executable")
                shutil.copyfileobj(stream, output)
        local.chmod(0o755)
    return local


def main() -> None:
    """Compile report.tex to report.pdf."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    subprocess.run([str(tectonic_binary()), "report.tex", "--outdir", "."], cwd=ROOT / "report", check=True)


if __name__ == "__main__":
    main()
