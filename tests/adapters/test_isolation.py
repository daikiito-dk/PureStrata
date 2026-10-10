"""Adapter isolation tests: importing the core never pulls a framework."""

from __future__ import annotations

import subprocess
import sys


def test_importing_purestrata_pulls_no_framework():
    code = (
        "import sys, purestrata; "
        "leaked = [m for m in sys.modules "
        "if m == 'distilabel' or m.startswith('llama_index') "
        "or m.startswith('datasets') or m.startswith('sentence_transformers')]; "
        "assert not leaked, leaked"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
