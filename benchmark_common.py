"""Shared dataset discovery and PATH command selection."""
from pathlib import Path
import hashlib
import shutil

INPUT_ROOT = "/home/LC/SDRbench_inputs/"
# This project lives at workspace/projects/lc-lossy-residuals-test.
REPORT_ROOT = Path(__file__).resolve().parents[2] / "testrpts"


def discover_inputs(patterns, root=INPUT_ROOT):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Input directory does not exist: {root}")
    candidates = sorted(p for p in root.rglob("*") if p.is_file()
                        and p.name.endswith((".f32", ".f32.dat")))
    selected = set()
    for pattern in patterns or [""]:
        matches = [p for p in candidates if pattern in str(p.relative_to(root))]
        if not matches:
            raise ValueError(f"No .f32 or .f32.dat inputs match {pattern!r} under {root}")
        selected.update(matches)
    result = sorted(selected)
    if not result:
        raise ValueError(f"No .f32 or .f32.dat inputs under {root}")
    for path in result:
        if not path.stat().st_size or path.stat().st_size % 4:
            raise ValueError(f"Input must be nonempty f32 data with size divisible by 4: {path}")
    return result


def dataset_label(path):
    return path.name + "_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]


def executable(command, alternatives=()):
    for name in (*alternatives, command):
        if shutil.which(name):
            return name
    raise ValueError(f"Executable not found in PATH: {command}")


def lc_source_dir(value, command):
    if value:
        return Path(value).expanduser().resolve()
    installed = shutil.which(command)
    if installed is None:
        raise ValueError(f"Executable not found in PATH: {command}")
    executable_dir = Path(installed).resolve().parent
    candidates = [
        executable_dir,
        executable_dir.parent / "github" / "LC-framework",
        Path(__file__).resolve().parents[2] / "github" / "LC-framework",
    ]
    for candidate in candidates:
        if (candidate / "generate_standalone_CPU_compressor_decompressor.py").is_file():
            return candidate
    raise ValueError(
        "LC CPU standalone generator not found. Pass --lc-dir with the LC-framework "
        "source checkout. Searched: " + ", ".join(str(path) for path in candidates)
    )
