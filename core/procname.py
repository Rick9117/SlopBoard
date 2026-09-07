"""
Give SlopBoard's background processes friendly names in Task Manager.

Windows lists a process under its executable's file name, so anything started
with Python normally shows up as "python.exe" or "pythonw.exe". To show
"SlopBoard" and "SlopBoard tracker" instead, we launch them through a *copy* of
the Python interpreter that has been renamed accordingly.

The copy has to sit next to the real interpreter, because that's where Python
finds its DLLs and standard library. If the copy can't be made for any reason we
simply fall back to the original interpreter, so launching never breaks.

Note: this changes the name in Task Manager's "Details" tab (the image name).
The "Processes" tab may still group it under "Python", because Windows reads
that label from the file's version info, which a plain copy keeps.
"""

import shutil
from pathlib import Path


def named_interpreter(python: str, label: str) -> str:
    """Return a copy of `python` named "<label>.exe", or `python` if that fails.

    The copy lives beside the real interpreter so it keeps working. It's created
    once and reused on later runs.
    """
    try:
        source = Path(python)
        if source.suffix.lower() != ".exe":      # non-Windows: nothing to do
            return python
        target = source.with_name(f"{label}.exe")
        if not target.exists():
            shutil.copy2(source, target)
        return str(target)
    except Exception:
        return python
