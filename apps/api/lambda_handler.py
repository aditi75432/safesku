"""Stable SAM Lambda entrypoint.

The application handler lives inside the app package.
This thin module keeps the container entrypoint stable.
"""

from app.lambda_handler import handler

__all__ = ["handler"]
