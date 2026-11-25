"""
Compatibility shim: the client now lives in the clockify_utils package.
`from clockify_client import ClockifyClient` keeps working.
"""

from clockify_utils.client import ClockifyAPIError, ClockifyClient  # noqa: F401
