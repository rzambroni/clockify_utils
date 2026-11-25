"""
Compatibility shim: the generator now lives in clockify_utils.descriptions.
`from description_generator import DescriptionGenerator` keeps working.
"""

from clockify_utils.descriptions import DescriptionGenerator  # noqa: F401
