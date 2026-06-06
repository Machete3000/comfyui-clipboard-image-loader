"""Backend route that detects clipboard images and saves them to the temp dir.

The frontend polls ``/clipboard_image_loader/poll`` on an interval. We use the cheap
Win32 clipboard sequence number to avoid grabbing the full bitmap on every poll, and
only call ``PIL.ImageGrab.grabclipboard()`` when the clipboard actually changed.
"""

import hashlib
import logging
import os
import sys

from aiohttp import web

import folder_paths
from server import PromptServer

try:
    from PIL import Image, ImageGrab

    _HAS_IMAGEGRAB = True
except Exception:  # pragma: no cover - Pillow is a hard ComfyUI dep, but be safe
    _HAS_IMAGEGRAB = False

log = logging.getLogger("comfyui-clipboard-image-loader")

# Process-wide poll state.
_state = {
    "seq": None,        # last observed clipboard sequence number (Windows only)
    "filename": None,   # last saved temp filename
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _get_clipboard_seq():
    """Return the Windows clipboard sequence number, or None on other platforms.

    The sequence number increments on every clipboard change, so comparing it lets us
    skip the expensive bitmap grab when nothing changed.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        # The API returns 0 when the process lacks clipboard access; treat that as
        # "unavailable" so callers fall back to always grabbing (correct, just less
        # efficient) rather than getting stuck on a constant 0.
        return seq or None
    except Exception:
        return None


def _grab_clipboard_image():
    """Return a PIL Image from the clipboard, or None.

    Handles the two useful ``grabclipboard()`` return shapes: an Image (a copied
    bitmap) or a list of file paths (files copied in Explorer) — in which case we open
    the first path that looks like an image.
    """
    if not _HAS_IMAGEGRAB:
        return None
    try:
        grabbed = ImageGrab.grabclipboard()
    except Exception as e:
        log.debug("grabclipboard failed: %s", e)
        return None

    if grabbed is None:
        return None

    if isinstance(grabbed, list):
        for path in grabbed:
            if (
                isinstance(path, str)
                and os.path.splitext(path)[1].lower() in _IMAGE_EXTS
                and os.path.isfile(path)
            ):
                try:
                    return Image.open(path)
                except Exception:
                    continue
        return None

    return grabbed


@PromptServer.instance.routes.get("/clipboard_image_loader/poll")
async def poll_clipboard(request):
    seq = _get_clipboard_seq()

    # Fast path: sequence number unchanged → nothing to do.
    if seq is not None and seq == _state["seq"]:
        return web.json_response(
            {"changed": False, "seq": seq, "filename": _state["filename"]}
        )

    img = _grab_clipboard_image()
    if seq is not None:
        _state["seq"] = seq  # remember even when clipboard holds non-image data

    if img is None:
        return web.json_response({"changed": False, "empty": True, "seq": seq})

    try:
        # Normalise to a mode PNG can save losslessly while preserving alpha.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

        raw = img.tobytes()
        digest = hashlib.sha256(raw + str(img.size).encode()).hexdigest()[:8]
        filename = "clipboard_{}.png".format(digest)

        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, filename)

        if not os.path.exists(filepath):
            img.save(filepath, format="PNG", compress_level=4)

        _state["filename"] = filename

        return web.json_response(
            {
                "changed": True,
                "filename": filename,
                "subfolder": "",
                "type": "temp",
                "seq": seq,
            }
        )
    except Exception as e:
        log.warning("Failed to save clipboard image: %s", e)
        return web.json_response({"changed": False, "error": str(e)}, status=200)
