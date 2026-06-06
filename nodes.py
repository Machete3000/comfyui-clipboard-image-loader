import hashlib
import os

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

import folder_paths
import node_helpers
import comfy.model_management


def _resolve_clipboard_path(clipboard_file):
    """Resolve the JS-managed filename to a path inside the temp directory.

    The frontend stores a plain filename (e.g. ``clipboard_ab12cd34.png``) that the
    poll route saved into ComfyUI's temp directory. We resolve against temp by default
    while still honouring an explicit ``[temp]``/``[input]`` annotation if present.
    """
    if not clipboard_file:
        return None
    return folder_paths.get_annotated_filepath(
        clipboard_file, default_dir=folder_paths.get_temp_directory()
    )


class ClipboardImageLoader:
    """Load whatever image is currently on the OS clipboard.

    A frontend extension polls the backend; when the clipboard image changes it is
    saved into the temp directory and its filename written into the (hidden)
    ``clipboard_file`` widget. At run time this node simply loads that file and
    converts it to an IMAGE/MASK pair using the same pipeline as the built-in
    LoadImage node, so the thumbnail shown on the node matches the output exactly.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # Managed by web/clipboard_image_loader.js; hidden in the UI.
                "clipboard_file": ("STRING", {"default": ""}),
            },
            "optional": {
                "error_if_empty": ("BOOLEAN", {"default": True}),
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load"

    def load(self, clipboard_file, error_if_empty=True):
        image_path = _resolve_clipboard_path(clipboard_file)

        if not image_path or not os.path.isfile(image_path):
            if error_if_empty:
                raise ValueError(
                    "No clipboard image captured yet. Copy an image (e.g. with the "
                    "Snipping Tool or right-click → Copy image) and wait for the "
                    "node's thumbnail to update, then run again."
                )
            # Soft fallback: a 64x64 black image and empty mask.
            return (
                torch.zeros((1, 64, 64, 3), dtype=torch.float32),
                torch.zeros((1, 64, 64), dtype=torch.float32),
            )

        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None

        dtype = comfy.model_management.intermediate_dtype()

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)

            if i.mode == "I":
                i = i.point(lambda i: i * (1 / 255))
            image = i.convert("RGB")

            if len(output_images) == 0:
                w = image.size[0]
                h = image.size[1]

            if image.size[0] != w or image.size[1] != h:
                continue

            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            if "A" in i.getbands():
                mask = np.array(i.getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            elif i.mode == "P" and "transparency" in i.info:
                mask = np.array(i.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            output_images.append(image.to(dtype=dtype))
            output_masks.append(mask.unsqueeze(0).to(dtype=dtype))

            if img.format == "MPO":
                break

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        return (output_image, output_mask)

    @classmethod
    def IS_CHANGED(s, clipboard_file, error_if_empty=True):
        image_path = _resolve_clipboard_path(clipboard_file)
        if not image_path or not os.path.isfile(image_path):
            return ""
        m = hashlib.sha256()
        with open(image_path, "rb") as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(s, clipboard_file, error_if_empty=True):
        # Allow an empty value (nothing captured yet); load() reports a clear error.
        image_path = _resolve_clipboard_path(clipboard_file)
        if clipboard_file and (not image_path or not os.path.isfile(image_path)):
            return "Clipboard image file no longer exists: {}".format(clipboard_file)
        return True


NODE_CLASS_MAPPINGS = {
    "ClipboardImageLoader": ClipboardImageLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ClipboardImageLoader": "Load Image (Clipboard)",
}
