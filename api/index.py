"""Vercel Python serverless entrypoint.

Vercel rewrites every /api/* request here (see vercel.json) and looks for a
module-level ASGI app named `app`.
"""

import os
import sys

# Vercel runs this file with api/ as the working directory, so the repo root
# (which holds the `backend` package) is not importable by default.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app  # noqa: E402

__all__ = ["app"]
