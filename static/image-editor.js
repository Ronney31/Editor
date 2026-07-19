/**
 * Image Editor - Inline text editing with OCR detection and filled-data removal.
 */

// --- State ---
const imgState = {
    sessionId: null,
    textBlocks: [],
    selectedBlocks: new Set(),
    modifications: {},  // blockId -> new text
};

// --- DOM ---
const uploadScreen = document.getElementById('img-editor-upload');
const workspace = document.getElementById('img-editor-workspace');
const dropZone = document.getElementById('img-editor-drop-zone');
const fileInput = document.getElementById('img-editor-file-input');
const progress = document.getElementById('img-editor-progress');
const editorImage = document.getElementById('img-editor-image');
const textLayer = document.getElementById('img-editor-text-layer');
const container = document.getElementById('img-editor-container');

// ============ UPLOAD ============

async function handleImageUpload(file) {
    if (!file || !file.type.startsWith('image/')) {
        alert('Please select an image file.');
        return;
    }

    progress.classList.remove('hidden');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/image-editor/upload', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await res.json();
        imgState.sessionId = data.session_id;
        imgState.textBlocks = data.text_blocks;
        imgState.selectedBlocks = new Set();
        imgState.modifications = {};

        showWorkspace();
        await loadImage();
        renderTextOverlays();
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        progress.classList.add('hidden');
    }
}

function showWorkspace() {
    uploadScreen.classList.remove('active');
    workspace.classList.add('active');
}

function showUpload() {
    workspace.classList.remove('active');
    uploadScreen.classList.add('active');
}

// Drag & drop
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleImageUpload(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', (e) => handleImageUpload(e.target.files[0]));

// ============ IMAGE LOADING ============

async function loadImage() {
    const url = `/api/image-editor/image/${imgState.sessionId}`;
    editorImage.src = url;
    await new Promise(resolve => { editorImage.onload = resolve; });

    container.style.width = editorImage.naturalWidth + 'px';
    container.style.height = editorImage.naturalHeight + 'px';
}

// ============ TEXT OVERLAYS ============

function renderTextOverlays() {
    textLayer.innerHTML = '';

    for (const block of imgState.textBlocks) {
        const div = document.createElement('div');
        div.className = 'img-text-block';
        div.dataset.blockId = block.id;

        // Mark as filled or printed
        if (block.is_filled) {
            div.classList.add('filled');
        } else {
            div.classList.add('printed');
        }

        // Position directly on image
        div.style.left = block.x + 'px';
        div.style.top = block.y + 'px';
        div.style.width = block.width + 'px';
        div.style.height = block.height + 'px';

        // Make contenteditable for inline editing
        div.contentEditable = 'true';
        div.spellcheck = false;
        div.textContent = block.text;
        div.title = `[${block.category}] "${block.text}" (${block.confidence}% conf)\nCtrl+Click to select for removal`;

        // Approximate font size from block height
        const fontSize = Math.max(10, block.height * 0.75);
        div.style.fontSize = fontSize + 'px';

        // Selection toggle on ctrl+click
        div.addEventListener('mousedown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                toggleBlockSelection(block.id, div);
            }
        });

        // Track text edits
        div.addEventListener('blur', () => {
            const newText = div.textContent.trim();
            if (newText !== block.text) {
                imgState.modifications[block.id] = {
                    type: 'replace_text',
                    x: block.x,
                    y: block.y,
                    width: block.width,
                    height: block.height,
                    text: newText,
                    fontSize: block.height * 0.75,
                    color: '#000000',
                };
                div.classList.add('modified');
            } else {
                delete imgState.modifications[block.id];
                div.classList.remove('modified');
            }
        });

        // Mark if selected
        if (imgState.selectedBlocks.has(block.id)) {
            div.classList.add('selected');
        }

        textLayer.appendChild(div);
    }
}

function toggleBlockSelection(blockId, div) {
    if (imgState.selectedBlocks.has(blockId)) {
        imgState.selectedBlocks.delete(blockId);
        div.classList.remove('selected');
    } else {
        imgState.selectedBlocks.add(blockId);
        div.classList.add('selected');
    }
}

// ============ ACTIONS ============

// Back
document.getElementById('img-editor-back').addEventListener('click', () => {
    if (confirm('Go back? Unsaved changes will be lost.')) {
        showUpload();
        imgState.sessionId = null;
    }
});

// Rotate Left
document.getElementById('img-editor-rotate-left').addEventListener('click', () => rotateImage('left'));

// Rotate Right
document.getElementById('img-editor-rotate-right').addEventListener('click', () => rotateImage('right'));

async function rotateImage(direction) {
    if (!imgState.sessionId) return;

    try {
        const res = await fetch(`/api/image-editor/rotate?session_id=${imgState.sessionId}&direction=${direction}`, {
            method: 'POST',
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Rotation failed');
        }

        const data = await res.json();
        imgState.textBlocks = data.text_blocks;
        imgState.selectedBlocks = new Set();
        imgState.modifications = {};

        await loadImage();
        renderTextOverlays();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Remove All Filled Data
document.getElementById('img-editor-remove-all').addEventListener('click', async () => {
    if (!imgState.sessionId) return;
    if (!confirm('Remove ALL detected text/filled data from the image?')) return;

    try {
        const edits = imgState.textBlocks.map(block => ({
            type: 'remove_text',
            block_ids: [block.id],
        }));

        const blob = await applyEdits(edits);
        downloadBlob(blob, 'cleaned_image.png');
    } catch (err) {
        alert('Error: ' + err.message);
    }
});

// Remove Selected
document.getElementById('img-editor-remove-selected').addEventListener('click', async () => {
    if (!imgState.sessionId) return;
    if (imgState.selectedBlocks.size === 0) {
        alert('No blocks selected. Ctrl+Click on text blocks to select them.');
        return;
    }

    try {
        const edits = [{
            type: 'remove_text',
            block_ids: Array.from(imgState.selectedBlocks),
        }];

        const blob = await applyEdits(edits);
        downloadBlob(blob, 'edited_image.png');
    } catch (err) {
        alert('Error: ' + err.message);
    }
});

// Download (with inline text edits applied)
document.getElementById('img-editor-download').addEventListener('click', async () => {
    if (!imgState.sessionId) return;

    const edits = Object.values(imgState.modifications);
    if (edits.length === 0) {
        // No edits, just download original
        const res = await fetch(`/api/image-editor/image/${imgState.sessionId}`);
        const blob = await res.blob();
        downloadBlob(blob, 'image.png');
        return;
    }

    try {
        const blob = await applyEdits(edits);
        downloadBlob(blob, 'edited_image.png');
    } catch (err) {
        alert('Error: ' + err.message);
    }
});

// ============ API ============

async function applyEdits(edits) {
    const res = await fetch('/api/image-editor/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: imgState.sessionId,
            edits: edits,
        }),
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Edit failed');
    }
    return res.blob();
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
