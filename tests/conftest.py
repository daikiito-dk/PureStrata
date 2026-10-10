"""Shared fixtures: the bundled sample manufacturing data."""

from __future__ import annotations

from pathlib import Path

import pytest

from purestrata import Corpus, ingest_dxf, ingest_failures, ingest_manual, ingest_step

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data_dir() -> Path:
    return REPO_ROOT / "examples" / "data"


@pytest.fixture
def en_manual(data_dir: Path) -> Path:
    return data_dir / "manuals" / "lathe_mk3_maintenance.md"


@pytest.fixture
def ja_manual(data_dir: Path) -> Path:
    return data_dir / "manuals" / "ja" / "cnc_press_maintenance.md"


@pytest.fixture
def dxf_path(data_dir: Path) -> Path:
    return data_dir / "cad" / "bracket_mk3.dxf"


@pytest.fixture
def step_path(data_dir: Path) -> Path:
    return data_dir / "cad" / "bracket_assy_mk3.step"


@pytest.fixture
def failures_csv(data_dir: Path) -> Path:
    return data_dir / "failures" / "plant_failures.csv"


@pytest.fixture
def corpus(
    en_manual: Path, ja_manual: Path, dxf_path: Path, step_path: Path, failures_csv: Path
) -> Corpus:
    chunks = (
        ingest_manual(en_manual)
        + ingest_manual(ja_manual)
        + ingest_dxf(dxf_path)
        + ingest_step(step_path)
        + ingest_failures(failures_csv)
    )
    return Corpus(chunks)
