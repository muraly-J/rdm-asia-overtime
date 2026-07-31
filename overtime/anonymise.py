"""Stable pseudonyms for employees, so tests can freeze payroll numbers publicly.

The golden test has to pin every employee's monthly totals, but the repository is
public: names beside hours are payroll data about people who never agreed to
publish it. Keying on a digest of the name keeps the test exact — it still fails
the moment any figure moves — while putting no identity in the repository.

The real name is never written to disk here; it only ever exists in the uploaded
CSV, which is gitignored and, in the deployed app, held in memory for the session.
"""
from __future__ import annotations

import hashlib

ID_LENGTH = 10


def employee_id(name: str) -> str:
    """Return a short stable pseudonym for an employee name.

    Deterministic across runs and machines, so a regenerated golden file diffs
    cleanly. Not a secrecy mechanism: anyone holding the roster could hash it and
    match. It exists so the repository carries no names, not to make the mapping
    unrecoverable by someone who already has the data.
    """
    digest = hashlib.sha256(name.strip().upper().encode("utf-8")).hexdigest()
    return f"emp-{digest[:ID_LENGTH]}"
