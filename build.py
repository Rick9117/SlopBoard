"""
Build a self-contained, no-Python-needed release of SlopBoard.

Run this on Windows with your normal Python:

    py build.py                # bundle the Python version you're building with
    py build.py 3.12.7         # or bundle a specific version instead

It produces  dist/SlopBoard/  - ONE folder that contains everything:
  - runtime/        a private copy of Python with every dependency installed
  - the app code    (slopboard.py, launcher.pyw, core/, pages/, tracker/, ...)
  - SlopBoard.bat   double-click to run - no system Python required
...and zips it to  dist/SlopBoard-<version>.zip  for a GitHub Release.

Anyone can unzip that folder and run SlopBoard without installing Python or
anything else. (Windows already ships with Edge, which is used for the app
window, so nothing external is needed.)

Note: this must be run on Windows, because the bundled runtime and packages are
Windows-specific. Build in a Python 3.12/3.13 environment if 3.14 wheels for a
dependency aren't available yet - the end user gets whatever you build with.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- settings
ROOT: Path = Path(__file__).resolve().parent      # the project folder
DIST: Path = ROOT / "dist"                         # build output lives here
APP_DIR: Path = DIST / "SlopBoard"                 # the folder we ship
RUNTIME: Path = APP_DIR / "runtime"                # the bundled interpreter

# Which Python to bundle. Defaults to the version you're building with, so the
# packages we install always match it. Override by passing a version argument.
VERSION: str = sys.argv[1] if len(sys.argv) > 1 else platform.python_version()

EMBED_URL: str = (f"https://www.python.org/ftp/python/{VERSION}/"
                  f"python-{VERSION}-embed-amd64.zip")
GET_PIP_URL: str = "https://bootstrap.pypa.io/get-pip.py"

# rcedit stamps a friendly FileDescription onto the renamed .exes so Task
# Manager's NAME column shows "SlopBoard" instead of "Python" (see below).
RCEDIT_URL: str = ("https://github.com/electron/rcedit/releases/download/"
                   "v2.0.0/rcedit-x64.exe")

# Run the bundled Python in isolation: PYTHONNOUSERSITE stops it seeing packages
# from your own machine's user folder, so pip actually installs each dependency
# INTO the runtime instead of deciding it's "already available" and skipping it.
BUILD_ENV: dict[str, str] = {**os.environ, "PYTHONNOUSERSITE": "1"}

# Packages that must end up in the runtime for SlopBoard to work; the build
# fails loudly if any is missing (win32gui also checks the pywin32 fix worked).
REQUIRED_IMPORTS: list[str] = ["streamlit", "pandas", "altair", "psutil", "win32gui"]

# App files to copy into the release. Everything else (data/, caches, the dev
# .bat launchers) is left out - the app recreates what it needs on first run.
INCLUDE: list[str] = [
    "slopboard.py", "launcher.pyw", "requirements.txt", "README.md",
    "core", "pages", "tracker", ".streamlit",
]


def _download(url: str, dest: Path) -> None:
    """Download a URL to a local file."""
    print(f"    downloading {url}")
    urllib.request.urlretrieve(url, dest)


def fetch_runtime() -> None:
    """Download the embeddable Python and unzip it into runtime/."""
    print(f"[1/7] Fetching Python {VERSION} runtime")
    embed_zip = DIST / "python-embed.zip"
    _download(EMBED_URL, embed_zip)
    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(RUNTIME)
    embed_zip.unlink()

    # The embeddable build ships with site-packages switched off; turn it on so
    # the dependencies we install below can actually be imported.
    for pth in RUNTIME.glob("python*._pth"):
        lines = [ln for ln in pth.read_text().splitlines()
                 if ln.strip() != "#import site"]
        if "Lib\\site-packages" not in lines:
            lines.insert(1, "Lib\\site-packages")
        if "import site" not in lines:
            lines.append("import site")
        pth.write_text("\n".join(lines) + "\n")


def install_dependencies() -> None:
    """Bootstrap pip inside the runtime and install requirements into it."""
    print("[2/7] Installing dependencies into the runtime")
    python = RUNTIME / "python.exe"
    get_pip = DIST / "get-pip.py"
    _download(GET_PIP_URL, get_pip)
    subprocess.run([str(python), str(get_pip), "--no-warn-script-location"],
                   check=True, env=BUILD_ENV)
    get_pip.unlink()
    subprocess.run([str(python), "-m", "pip", "install",
                    "--no-warn-script-location", "-r", str(ROOT / "requirements.txt")],
                   check=True, env=BUILD_ENV)


def fix_pywin32() -> None:
    """Make pywin32 importable inside the embeddable runtime.

    pywin32 keeps its DLLs in site-packages/pywin32_system32 and its modules in
    site-packages/win32 (etc.). Copying the DLLs next to python.exe puts them on
    the default search path, and a .pth file adds the module folders to sys.path,
    so `import win32gui` works. (If it still fails, run pywin32_postinstall.py.)
    """
    print("[3/7] Fixing up pywin32")
    site_packages = RUNTIME / "Lib" / "site-packages"
    dll_dir = site_packages / "pywin32_system32"
    if dll_dir.exists():
        for dll in dll_dir.glob("*.dll"):
            shutil.copy2(dll, RUNTIME / dll.name)
    (site_packages / "slopboard_pywin32.pth").write_text(
        "win32\nwin32\\lib\nPythonwin\n")


def verify_runtime() -> None:
    """Fail the build if any required package didn't make it into the runtime.

    Catches silent gaps (e.g. a dependency pip decided was "already available")
    before we ship a broken folder.
    """
    print("[4/7] Verifying the runtime has everything")
    python = RUNTIME / "python.exe"
    check = "import " + ", ".join(REQUIRED_IMPORTS)
    result = subprocess.run([str(python), "-c", check], env=BUILD_ENV)
    if result.returncode != 0:
        raise SystemExit(
            "\nBuild stopped: a required package is missing from the runtime "
            "(see the import error above).\nTry re-running `py build.py`, or build "
            "in a Python 3.12/3.13 environment if a wheel isn't available yet.")


def name_and_stamp_exes() -> None:
    """Create the renamed interpreter copies and give them friendly names.

    SlopBoard runs the dashboard and tracker through copies of the interpreter
    named "SlopBoard.exe" / "SlopBoard tracker.exe" (that's the Process name
    column in Task Manager). We also stamp each copy's FileDescription with
    rcedit so the NAME column reads "SlopBoard" / "SlopBoard tracker" instead of
    "Python". Best-effort: if rcedit can't run, the copies still work fine - the
    NAME column just falls back to "Python".
    """
    print("[5/7] Naming the SlopBoard executables")
    copies = {
        "SlopBoard.exe": RUNTIME / "python.exe",          # the dashboard
        "SlopBoard tracker.exe": RUNTIME / "pythonw.exe",  # the tracker
    }
    for name, source in copies.items():
        shutil.copy2(source, RUNTIME / name)

    try:
        rcedit = DIST / "rcedit.exe"
        _download(RCEDIT_URL, rcedit)
        for name in copies:
            label = name[:-len(".exe")]        # "SlopBoard tracker"
            subprocess.run([str(rcedit), str(RUNTIME / name),
                            "--set-version-string", "FileDescription", label,
                            "--set-version-string", "ProductName", label],
                           check=True)
        rcedit.unlink()
    except Exception as error:                 # keep the build going regardless
        print(f"    (skipped friendly names: {error})")


def copy_app() -> None:
    """Copy the app source into the release folder and add the launcher."""
    print("[6/7] Copying app files")
    for name in INCLUDE:
        source, target = ROOT / name, APP_DIR / name
        if source.is_dir():
            shutil.copytree(source, target,
                            ignore=shutil.ignore_patterns("__pycache__"))
        elif source.exists():
            shutil.copy2(source, target)
    (APP_DIR / "data").mkdir(exist_ok=True)      # empty folder to write into

    # The double-click launcher: run our launcher with the BUNDLED Python.
    # newline="\r\n" writes proper Windows line endings (no doubled carriage returns).
    (APP_DIR / "SlopBoard.bat").write_text(
        '@echo off\n'
        'cd /d "%~dp0"\n'
        'start "" "runtime\\pythonw.exe" launcher.pyw\n',
        newline="\r\n")


def make_zip() -> None:
    """Zip the release folder for uploading to a GitHub Release."""
    print("[7/7] Zipping the release")
    zip_base = DIST / f"SlopBoard-{VERSION}"
    shutil.make_archive(str(zip_base), "zip", DIST, "SlopBoard")
    print(f"\nDone -> {zip_base}.zip")


def main() -> None:
    """Assemble the whole self-contained release from scratch."""
    if DIST.exists():
        shutil.rmtree(DIST)              # always start clean
    DIST.mkdir(parents=True)
    fetch_runtime()
    install_dependencies()
    fix_pywin32()
    verify_runtime()
    name_and_stamp_exes()
    copy_app()
    make_zip()


if __name__ == "__main__":
    main()
