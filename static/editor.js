/**
 * PDF Editor - Inline text editing
 * Renders PDF as image, overlays editable text fields at exact positions.
 */

import { uploadPDF, fetchPageImage, fetchPageText, submitEdits } from './api.js';

// --- State ---
const state = {
    sessionId: null,
    pageCount: 0,
    currentPage: 0,
    pageDimensions: [],  // original PDF dimensions in points
    zoom: 2.0,           // must match backend render zoom
    textBlocks: {},      // per-page: { pageNum: [{id, text, originalText, ...}] }
    modifications: {},   // tracks modified blocks: { blockId: editData }
    deletedPages: [],
    drawPaths: [],       // [{page, points, color, lineWidth}]
    activeTool: null,    // null = inline edit mode, 'draw', 'addtext', 'image'
};

// --- DOM ---
const uploadScreen = document.getElementById('upload-screen');
const editorScreen = document.getElementById('editor-screen');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadProgress = document.getElementById('upload-progress');
const pdfImage = document.getElementById('pdf-image');
const textLayer = document.getElementById('text-layer');
const drawCanvas = document.getElementById('draw-canvas');
const pageContainer = document.getElementById('page-container');
const pageIndicator = document.getElementById('page-indicator');

// ============ UPLOAD ============

function showEditor() {
    uploadScreen.classList.remove('active');
    editorScreen.classList.add('active');
}

async function handleFile(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please select a PDF file.');
        return;
    }
    uploadProgress.classList.remove('hidden');

    try {
        const result = await uploadPDF(file);
        state.sessionId = result.session_id;
        state.pageCount = result.page_count;
        state.pageDimensions = result.pages;
        state.currentPage = 0;
        state.textBlocks = {};
        state.modifications = {};
        state.deletedPages = [];
        state.drawPaths = [];

        showEditor();
        await loadPage(state.currentPage);
    } catch (err) {
        alert('Upload failed: ' + err.message);
    } finally {
        uploadProgress.classList.add('hidden');
    }
}

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFile(e.dataTransfer.files[0]); });
fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));

// ============ PAGE LOADING ============

async function loadPage(pageNum) {
    // Fetch page image
    const imgBlob = await fetchPageImage(state.sessionId, pageNum);
    const imgUrl = URL.createObjectURL(imgBlob);
    pdfImage.src = imgUrl;

    await new Promise(resolve => { pdfImage.onload = resolve; });

    const imgW = pdfImage.naturalWidth;
    const imgH = pdfImage.naturalHeight;

    // Size the container to match the image
    pageContainer.style.width = imgW + 'px';
    pageContainer.style.height = imgH + 'px';

    // Setup draw canvas
    drawCanvas.width = imgW;
    drawCanvas.height = imgH;

    // Fetch text blocks and create editable overlays
    await loadTextLayer(pageNum, imgW, imgH);

    // Redraw any existing draw paths for this page
    redrawPaths();

    pageIndicator.textContent = `Page ${pageNum + 1} / ${state.pageCount}`;
}

async function loadTextLayer(pageNum, canvasW, canvasH) {
    textLayer.innerHTML = '';

    // Fetch text with positions if not cached
    if (!state.textBlocks[pageNum]) {
        const data = await fetchPageText(state.sessionId, pageNum);
        state.textBlocks[pageNum] = data.blocks;
    }

    const blocks = state.textBlocks[pageNum];
    const dims = state.pageDimensions[pageNum];

    // Scale factor: PDF points → rendered pixels
    const scaleX = canvasW / dims.width;
    const scaleY = canvasH / dims.height;

    for (const block of blocks) {
        const div = document.createElement('div');
        div.className = 'text-block';
        div.contentEditable = 'true';
        div.spellcheck = false;
        div.dataset.blockId = block.id;

        // Position and size (scaled from PDF points to pixels)
        const left = block.x * scaleX;
        const top = block.y * scaleY;
        const width = block.width * scaleX;
        const height = block.height * scaleY;

        div.style.left = left + 'px';
        div.style.top = top + 'px';
        div.style.width = (width + 10) + 'px';  // slight padding for editing comfort
        div.style.height = height + 'px';

        // Match font styling
        const fontSize = block.fontSize * scaleY;
        div.style.fontSize = fontSize + 'px';
        div.style.color = block.color;
        div.style.fontFamily = mapFontToCSS(block.fontName);

        if (block.flags & 16) div.style.fontWeight = 'bold';  // bit 4 = bold
        if (block.flags & 2) div.style.fontStyle = 'italic';  // bit 1 = italic

        // Set the text content
        const modKey = `${pageNum}_${block.id}`;
        if (state.modifications[modKey]) {
            div.textContent = state.modifications[modKey].text;
            div.classList.add('modified');
        } else {
            div.textContent = block.text;
        }

        // Store original text for change detection
        div.dataset.originalText = block.text;
        div.dataset.page = pageNum;

        // Track modifications on blur
        div.addEventListener('blur', () => onTextEdited(div, block, pageNum));
        div.addEventListener('focus', () => {
            // Auto-expand width when editing
            div.style.width = 'auto';
            div.style.minWidth = (width + 10) + 'px';
        });
        div.addEventListener('blur', () => {
            div.style.width = (width + 10) + 'px';
        });

        textLayer.appendChild(div);
    }
}

function onTextEdited(div, block, pageNum) {
    const newText = div.textContent;
    const modKey = `${pageNum}_${block.id}`;

    if (newText !== block.text) {
        // Mark as modified
        state.modifications[modKey] = {
            type: 'inline_text',
            page: pageNum,
            x: block.x,
            y: block.y,
            width: block.width,
            height: block.height,
            text: newText,
            fontSize: block.fontSize,
            fontName: block.fontName,
            color: block.color,
        };
        div.classList.add('modified');
    } else {
        // Reverted back to original
        delete state.modifications[modKey];
        div.classList.remove('modified');
    }
}

function mapFontToCSS(fontName) {
    const name = fontName.toLowerCase();
    if (name.includes('courier') || name.includes('mono')) return "'Courier New', monospace";
    if (name.includes('times')) return "'Times New Roman', serif";
    if (name.includes('arial') || name.includes('helv')) return "Arial, Helvetica, sans-serif";
    return "Arial, Helvetica, sans-serif";
}

// ============ PAGE NAVIGATION ============

document.getElementById('btn-prev-page').addEventListener('click', async () => {
    if (state.currentPage > 0) { state.currentPage--; await loadPage(state.currentPage); }
});
document.getElementById('btn-next-page').addEventListener('click', async () => {
    if (state.currentPage < state.pageCount - 1) { state.currentPage++; await loadPage(state.currentPage); }
});

// ============ TOOLS ============

const toolButtons = document.querySelectorAll('[data-tool]');
toolButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.classList.contains('active')) {
            // Deactivate
            btn.classList.remove('active');
            state.activeTool = null;
            drawCanvas.classList.remove('active');
        } else {
            toolButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeTool = btn.dataset.tool;
            drawCanvas.classList.toggle('active', state.activeTool === 'draw');
        }
    });
});

// --- Drawing ---
let isDrawing = false;
let currentPath = [];

drawCanvas.addEventListener('mousedown', (e) => {
    if (state.activeTool !== 'draw') return;
    isDrawing = true;
    const coords = getCanvasCoords(e);
    currentPath = [coords];
});

drawCanvas.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;
    const coords = getCanvasCoords(e);
    currentPath.push(coords);
    redrawPaths(currentPath);
});

drawCanvas.addEventListener('mouseup', () => {
    if (!isDrawing) return;
    isDrawing = false;
    if (currentPath.length > 1) {
        state.drawPaths.push({
            page: state.currentPage,
            points: currentPath,
            color: '#000000',
            lineWidth: 2,
        });
    }
    currentPath = [];
    redrawPaths();
});

function getCanvasCoords(e) {
    const rect = drawCanvas.getBoundingClientRect();
    const scaleX = drawCanvas.width / rect.width;
    const scaleY = drawCanvas.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
}

function redrawPaths(livePath) {
    const ctx = drawCanvas.getContext('2d');
    ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);

    // Draw saved paths for current page
    for (const path of state.drawPaths) {
        if (path.page !== state.currentPage) continue;
        drawPath(ctx, path.points, path.color, path.lineWidth);
    }

    // Draw live path
    if (livePath && livePath.length > 1) {
        drawPath(ctx, livePath, '#000000', 2);
    }
}

function drawPath(ctx, points, color, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
}

// ============ DELETE PAGE ============

document.getElementById('btn-delete-page').addEventListener('click', () => {
    if (state.pageCount <= 1) { alert('Cannot delete the only page.'); return; }
    if (!confirm(`Delete page ${state.currentPage + 1}?`)) return;
    state.deletedPages.push(state.currentPage);
    state.pageCount--;
    if (state.currentPage >= state.pageCount) state.currentPage = state.pageCount - 1;
    loadPage(state.currentPage);
});

// ============ BACK ============

document.getElementById('btn-back').addEventListener('click', () => {
    if (confirm('Go back? Unsaved edits will be lost.')) {
        editorScreen.classList.remove('active');
        uploadScreen.classList.add('active');
        state.sessionId = null;
    }
});

// ============ DOWNLOAD ============

document.getElementById('btn-download').addEventListener('click', async () => {
    if (!state.sessionId) return;

    const edits = [];

    // Collect inline text modifications
    for (const mod of Object.values(state.modifications)) {
        edits.push(mod);
    }

    // Collect draw paths (convert pixel coords back to PDF points)
    for (const path of state.drawPaths) {
        const dims = state.pageDimensions[path.page];
        // We need the image dimensions for that page to compute scale
        // Use zoom factor directly since image = PDF_points * zoom
        edits.push({
            type: 'draw',
            page: path.page,
            points: path.points.map(p => ({ x: p.x / state.zoom, y: p.y / state.zoom })),
            color: path.color,
            lineWidth: path.lineWidth / state.zoom,
        });
    }

    // Deleted pages
    for (const pg of state.deletedPages) {
        edits.push({ type: 'delete_page', page: pg });
    }

    try {
        const blob = await submitEdits(state.sessionId, edits);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'edited.pdf';
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert('Download failed: ' + err.message);
    }
});
