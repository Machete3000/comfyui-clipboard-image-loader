import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "ClipboardImageLoader";
const POLL_INTERVAL_MS = 1500;

// Hide the backend-managed filename widget so the user never edits it by hand.
function hideWidget(node, name) {
    const w = node.widgets?.find((w) => w.name === name);
    if (!w) return;
    w.type = "hidden";
    w.computeSize = () => [0, -4]; // collapse its row
    w.hidden = true;
}

function viewUrl(filename, type, cacheBust) {
    return api.apiURL(
        `/view?filename=${encodeURIComponent(filename)}&type=${type ?? "temp"}` +
            `&subfolder=&r=${cacheBust ?? 0}`
    );
}

// Load the thumbnail into node.imgs; ComfyUI draws node.imgs on the node body.
function showThumbnail(node, filename, type, seq) {
    const img = new Image();
    img.onload = () => {
        node.imgs = [img];
        app.graph.setDirtyCanvas(true, true);
    };
    img.onerror = () => {
        // File may have been cleared (e.g. server restart wiped temp). Ignore;
        // the next poll that detects a change will repopulate it.
    };
    img.src = viewUrl(filename, type, seq);
}

async function poll(node) {
    if (document.hidden) return; // don't poll while the tab is in the background
    let data;
    try {
        const resp = await fetch(api.apiURL("/clipboard_image_loader/poll"));
        if (!resp.ok) return;
        data = await resp.json();
    } catch (e) {
        return; // transient; try again next tick
    }

    if (!data || !data.changed || !data.filename) return;

    const widget = node.widgets?.find((w) => w.name === "clipboard_file");
    if (widget) widget.value = data.filename;

    showThumbnail(node, data.filename, data.type, data.seq);
}

app.registerExtension({
    name: "ClipboardImageLoader.AutoThumbnail",
    async nodeCreated(node) {
        if (node.comfyClass !== NODE_CLASS) return;

        hideWidget(node, "clipboard_file");

        // Restore a thumbnail for a value loaded from a saved workflow.
        const existing = node.widgets?.find((w) => w.name === "clipboard_file");
        if (existing?.value) {
            showThumbnail(node, existing.value, "temp", 0);
        }

        // Start polling and ensure cleanup when the node is removed.
        node._clipboardPoll = setInterval(() => poll(node), POLL_INTERVAL_MS);
        // Kick off an immediate poll so the thumbnail appears without waiting.
        poll(node);

        const onRemoved = node.onRemoved;
        node.onRemoved = function () {
            if (node._clipboardPoll) {
                clearInterval(node._clipboardPoll);
                node._clipboardPoll = null;
            }
            return onRemoved?.apply(this, arguments);
        };
    },
});
