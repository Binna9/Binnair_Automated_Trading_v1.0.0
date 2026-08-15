#!/usr/bin/env python3
"""Assert requirements-fincast.txt covers known FinCast load-path packages."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
req = (ROOT / "requirements-fincast.txt").read_text()
needed = [
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "tqdm",
    "absl-py",
    "utilsforecast",
    "einops",
    "einx",
    "beartype",
    "CoLT5-attention",
    "jax",
]
missing = [n for n in needed if n.lower() not in req.lower()]
assert not missing, f"requirements-fincast.txt missing: {missing}"
print("check_fincast_requirements: ok")
