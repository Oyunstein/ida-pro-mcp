"""Filesystem boundary helpers shared by idalib supervisor and workers."""

from __future__ import annotations

from pathlib import Path


def normalize_input_path(input_path: str | Path) -> Path:
    """Return an existing absolute input file path.

    MCP clients and stdio servers do not necessarily share a working directory.
    Reject relative paths instead of resolving them against the server process
    and potentially opening a different same-named binary.
    """

    path = Path(input_path)
    if not path.is_absolute():
        raise ValueError(
            "input_path must be absolute because MCP server working directories "
            f"are client-independent; received {str(input_path)!r} while the "
            f"server cwd is '{Path.cwd()}'. Resolve the path client-side."
        )
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")
    return path.resolve()
