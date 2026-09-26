"""Pytest bootstrap.

The test suite must never write to the developer database or the developer
evidence storage. Point the application at a throwaway SQLite file and upload
directory before any application module is imported, so `app.db` builds its
engine against the temporary location.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="cni-tests-"))
os.environ["CNI_DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'cni-test.db').as_posix()}"
os.environ["CNI_UPLOAD_DIR"] = str(_TEST_ROOT / "uploads")
os.environ["CNI_CAMERA_AUTO_START"] = "false"
os.environ["CNI_CAMERA_DEMO_MODE"] = "false"


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ANN001, ANN201, ARG001
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)
