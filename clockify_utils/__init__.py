"""
clockify_utils: shared Clockify helpers for every project.

    from clockify_utils import ClockifyClient
    client = ClockifyClient.from_env()   # key/workspace from the shared settings
"""

__version__ = "1.0.0"

from .client import AmbiguousMatchError, ClockifyAPIError, ClockifyClient  # noqa: E402
from .descriptions import DescriptionGenerator  # noqa: E402
from .settings import Settings, SettingsError, get_settings  # noqa: E402

__all__ = [
    "ClockifyClient",
    "ClockifyAPIError",
    "AmbiguousMatchError",
    "DescriptionGenerator",
    "Settings",
    "SettingsError",
    "get_settings",
]
