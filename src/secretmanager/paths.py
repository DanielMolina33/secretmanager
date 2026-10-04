from pathlib import Path
import sys


def get_portable_root() -> Path:
    """Return the application root for source and portable bundle layouts."""
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        for candidate in (executable_dir, executable_dir.parent):
            if candidate.name.casefold() == "app":
                return candidate.parent
        return executable_dir

    # Editable/source installs use the project root, independent of cwd.
    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent

    # A non-frozen wheel install has no portable root marker. Keep its data
    # alongside the selected interpreter rather than using the caller's cwd.
    return Path(sys.executable).resolve().parent


def get_data_dir() -> Path:
    return get_portable_root() / "data"
