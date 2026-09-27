"""
Build a self-contained, no-Python-needed release of SlopBoard.

Run this on Windows with your normal Python:

    py build.py                # bundle the Python version you're building with
    py build.py 3.12.7         # or bundle a specific version instead

It produces  dist/SlopBoard/  - ONE folder that contains everything:
  - runtime/        a private copy of Python with every dependency installed
  - the app code    (slopboard.py, launcher.pyw, core/, pages/, tracker/, ...)
  - SlopBoard.exe   double-click to run - no system Python required
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
import stat
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
    "assets",
    "core", "pages", "tracker", ".streamlit",
]


def _download(url: str, dest: Path) -> None:
    """Download a URL to a local file."""
    print(f"    downloading {url}")
    urllib.request.urlretrieve(url, dest)


def fetch_runtime() -> None:
    """Download the embeddable Python and unzip it into runtime/."""
    print(f"[1/9] Fetching Python {VERSION} runtime")
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
    print("[2/9] Installing dependencies into the runtime")
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
    print("[3/9] Fixing up pywin32")
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
    print("[4/9] Verifying the runtime has everything")
    python = RUNTIME / "python.exe"
    check = "import " + ", ".join(REQUIRED_IMPORTS)
    result = subprocess.run([str(python), "-c", check], env=BUILD_ENV)
    if result.returncode != 0:
        raise SystemExit(
            "\nBuild stopped: a required package is missing from the runtime "
            "(see the import error above).\nTry re-running `py build.py`, or build "
            "in a Python 3.12/3.13 environment if a wheel isn't available yet.")


def slim_runtime() -> None:
    """Delete files the app never needs at runtime, to shrink the download.

    Safe to remove: pip/wheel (only used while building, not while running),
    pywin32's IDE (Pythonwin - we only use win32gui/win32process), compiled
    caches (regenerated on demand), and type stubs. The heavy data-science
    libraries (pyarrow, pandas, numpy) are required and stay.
    """
    print("[5/9] Slimming the runtime")
    site = RUNTIME / "Lib" / "site-packages"

    # Whole folders that aren't needed once the app is built.
    for folder in ["pip", "wheel", "pythonwin", "Pythonwin"]:
        shutil.rmtree(site / folder, ignore_errors=True)
    for info in site.glob("pip-*.dist-info"):
        shutil.rmtree(info, ignore_errors=True)
    for info in site.glob("wheel-*.dist-info"):
        shutil.rmtree(info, ignore_errors=True)

    # Compiled caches and type stubs, anywhere under the runtime.
    for cache in RUNTIME.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    for stub in RUNTIME.rglob("*.pyi"):
        stub.unlink(missing_ok=True)


def name_and_stamp_exes() -> None:
    """Create the renamed interpreter copies and give them friendly names.

    SlopBoard runs the dashboard and tracker through copies of the interpreter
    named "SlopBoard.exe" / "SlopBoard tracker.exe" (that's the Process name
    column in Task Manager). We also stamp each copy's FileDescription with
    rcedit so the NAME column reads "SlopBoard" / "SlopBoard tracker" instead of
    "Python", and give them the SlopBoard icon so Task Manager shows that too.
    Best-effort: if rcedit can't run, the copies still work fine - they just keep
    Python's name and icon.
    """
    print("[6/9] Naming the SlopBoard executables")
    copies = {
        "SlopBoard.exe": RUNTIME / "python.exe",          # the dashboard
        "SlopBoard tracker.exe": RUNTIME / "pythonw.exe",  # the tracker
    }
    for name, source in copies.items():
        shutil.copy2(source, RUNTIME / name)

    icon = ROOT / "assets" / "slopboard.ico"
    icon_args = ["--set-icon", str(icon)] if icon.exists() else []
    try:
        rcedit = DIST / "rcedit.exe"
        _download(RCEDIT_URL, rcedit)
        for name in copies:
            label = name[:-len(".exe")]        # "SlopBoard tracker"
            subprocess.run([str(rcedit), str(RUNTIME / name),
                            "--set-version-string", "FileDescription", label,
                            "--set-version-string", "ProductName", label]
                           + icon_args, check=True)
        rcedit.unlink()
    except Exception as error:                 # keep the build going regardless
        print(f"    (skipped friendly names: {error})")


def copy_app() -> None:
    """Copy the app source into the release folder and add the launcher."""
    print("[7/9] Copying app files")
    for name in INCLUDE:
        source, target = ROOT / name, APP_DIR / name
        if source.is_dir():
            shutil.copytree(source, target,
                            ignore=shutil.ignore_patterns("__pycache__"))
        elif source.exists():
            shutil.copy2(source, target)
    (APP_DIR / "data").mkdir(exist_ok=True)      # empty folder to write into
    # No .bat here: build_exe() creates SlopBoard.exe as the launcher, and only
    # falls back to writing a .bat if the .exe couldn't be built.


def build_exe() -> None:
    """Compile a real SlopBoard.exe entry point with PyInstaller.

    People can then start SlopBoard by double-clicking a program (with an icon)
    instead of a .bat. The .exe is only a tiny launcher that hands off to the
    bundled runtime, so PyInstaller packages a few lines - not Streamlit, which
    is the fragile part. Best-effort: if PyInstaller isn't available or fails,
    the build still succeeds and the .bat remains as the way to start it.
    """
    print("[8/9] Building SlopBoard.exe")
    try:
        # Make sure PyInstaller is available in the Python running this build.
        check = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode != 0:
            print("    installing PyInstaller...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller",
                            "--quiet"], check=True)

        work = DIST / "_exe_build"
        cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole",
               "--name", "SlopBoard",
               "--distpath", str(work / "dist"),
               "--workpath", str(work / "build"),
               "--specpath", str(work)]
        icon = ROOT / "assets" / "slopboard.ico"
        if icon.exists():
            cmd += ["--icon", str(icon)]        # give it a proper program icon
        cmd.append(str(ROOT / "slopboard_app.py"))

        subprocess.run(cmd, check=True)
        shutil.copy2(work / "dist" / "SlopBoard.exe", APP_DIR / "SlopBoard.exe")
        shutil.rmtree(work, ignore_errors=True)
        print("    SlopBoard.exe created")
    except Exception as error:                  # keep the build going regardless
        print(f"    (couldn't build SlopBoard.exe: {error})")
        print("    writing SlopBoard.bat as a fallback launcher instead")
        (APP_DIR / "SlopBoard.bat").write_text(
            '@echo off\n'
            'cd /d "%~dp0"\n'
            'start "" "runtime\\pythonw.exe" launcher.pyw\n',
            newline="\r\n")


def make_zip() -> None:
    """Zip the release folder for uploading to a GitHub Release."""
    print("[9/9] Zipping the release")
    zip_base = DIST / f"SlopBoard-{VERSION}"
    shutil.make_archive(str(zip_base), "zip", DIST, "SlopBoard")
    print(f"\nDone -> {zip_base}.zip")


def _clear_old_dist() -> None:
    """Delete any previous build so we start clean.

    A running SlopBoard locks files inside dist/ (Windows won't delete a DLL
    that's in use), so we clear read-only files automatically and turn the
    "still running" case into a clear message instead of a stack trace.
    """
    if not DIST.exists():
        return

    def on_error(func, path, _exc) -> None:      # clear a read-only bit and retry
        os.chmod(path, stat.S_IWRITE)
        func(path)

    try:
        shutil.rmtree(DIST, onexc=on_error)
    except OSError:
        raise SystemExit(
            "\nBuild stopped: couldn't clear the old dist/ folder because "
            "SlopBoard is still running and locking files inside it.\n"
            "Close the dashboard window and end SlopBoard.exe / SlopBoard "
            "tracker.exe in Task Manager (or use Settings > Stop tracking), "
            "then run `py build.py` again.")


def main() -> None:
    """Assemble the whole self-contained release from scratch."""
    _clear_old_dist()
    DIST.mkdir(parents=True)
    fetch_runtime()
    install_dependencies()
    fix_pywin32()
    verify_runtime()
    slim_runtime()
    name_and_stamp_exes()
    copy_app()
    build_exe()
    make_zip()


if __name__ == "__main__":
    main()
