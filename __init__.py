"""ComfyUI Clipboard Image Loader.

A LoadImage-style node that auto-detects the current OS clipboard image, shows a live
thumbnail, and outputs it as an IMAGE/MASK pair.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Importing this module registers the /clipboard_image_loader/poll route.
from . import clipboard_routes  # noqa: F401

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
