from __future__ import annotations

from .db import Base

# The map view is backed by normalized entity metadata. The SQLAlchemy metadata
# remains the source of truth; this module provides a stable domain boundary for
# adding a spatial database (PostGIS or a dedicated tile service) later.
assert Base is not None
