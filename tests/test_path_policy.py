from pathlib import Path

import pytest

from ida_pro_mcp.path_policy import normalize_input_path


def test_normalize_input_path_accepts_existing_absolute_file(tmp_path):
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"sample")

    assert normalize_input_path(sample) == sample.resolve()


def test_normalize_input_path_rejects_relative_file_even_when_it_exists(
    tmp_path, monkeypatch
):
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"sample")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="input_path must be absolute") as exc:
        normalize_input_path(Path("sample.bin"))

    assert str(tmp_path) in str(exc.value)
    assert "Resolve the path client-side" in str(exc.value)


def test_normalize_input_path_rejects_missing_absolute_file(tmp_path):
    missing = (tmp_path / "missing.bin").resolve()

    with pytest.raises(FileNotFoundError, match="Input file not found"):
        normalize_input_path(missing)


def test_normalize_input_path_rejects_directory(tmp_path):
    with pytest.raises(ValueError, match="Input path is not a file"):
        normalize_input_path(tmp_path.resolve())
