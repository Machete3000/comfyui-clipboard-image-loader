# ComfyUI Clipboard Image Loader

A `LoadImage`-style node that **automatically detects the image currently on your OS
clipboard**, shows a live thumbnail on the node, and outputs it as an `IMAGE` / `MASK`
pair. Copy an image anywhere on your machine and the node picks it up — no upload, no
`Ctrl+V`.

## Node

**Load Image (Clipboard)** — category `image`

| Output | Type    | Notes                                                   |
| ------ | ------- | ------------------------------------------------------- |
| IMAGE  | `IMAGE` | RGB tensor, same conversion as the built-in LoadImage.  |
| MASK   | `MASK`  | Alpha channel as a mask (zeros if the image is opaque). |

Optional input `error_if_empty` (default **on**): when nothing has been captured yet,
the node raises a clear error. Turn it off to instead output a 64×64 black image.

## How it works

- A small frontend extension polls the backend every ~1.5 s.
- The backend uses the Windows clipboard **sequence number** as a cheap change check and
  only grabs the bitmap (via `PIL.ImageGrab.grabclipboard()`) when the clipboard actually
  changed. The captured image is saved into ComfyUI's **temp** directory.
- The node's filename is stored in a hidden widget; at run time the node loads that file,
  so the thumbnail you see is exactly what flows downstream.
- `IS_CHANGED` returns the file hash, so re-running with the same clipboard image is
  cached, and copying a new image causes the node to re-run.

When you copy a new image, the thumbnail updates automatically; the new image is used the
next time **you** run the workflow (it does not auto-queue).

## Requirements / platform notes

- **Pillow** (already required by ComfyUI). On Windows, **pywin32** is used for the cheap
  sequence-number check (optional — falls back gracefully).
- Clipboard reading happens on the **server**, so this assumes ComfyUI runs on the same
  machine you copy images on (the normal local setup).
- Works on Windows and macOS via `ImageGrab`. On Linux, `ImageGrab.grabclipboard()`
  requires `xclip` or `wl-paste` to be installed.

## Install

Clone into `ComfyUI/custom_nodes/` and restart ComfyUI:

```
ComfyUI/custom_nodes/comfyui-clipboard-image-loader/
```

Then add **Load Image (Clipboard)** from the `image` category.
