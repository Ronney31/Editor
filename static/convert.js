/**
 * Conversion module: Image to PDF and PDF to Image
 */

// ============ TAB NAVIGATION ============
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        tabButtons.forEach(b => b.classList.remove('active'));
        tabContents.forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

// ============ IMAGE TO PDF ============
const imgDropZone = document.getElementById('img-drop-zone');
const imgFileInput = document.getElementById('img-file-input');
const imgPreviewArea = document.getElementById('img-preview-area');
const imgPreviewList = document.getElementById('img-preview-list');
const imgCount = document.getElementById('img-count');
const imgClearBtn = document.getElementById('img-clear-btn');
const imgConvertBtn = document.getElementById('img-convert-btn');

let selectedImages = []; // File objects

function addImages(files) {
    for (const file of files) {
        if (file.type.startsWith('image/')) {
            selectedImages.push(file);
        }
    }
    renderImagePreviews();
}

function renderImagePreviews() {
    if (selectedImages.length === 0) {
        imgPreviewArea.classList.add('hidden');
        return;
    }

    imgPreviewArea.classList.remove('hidden');
    imgCount.textContent = `(${selectedImages.length})`;
    imgPreviewList.innerHTML = '';

    selectedImages.forEach((file, index) => {
        const div = document.createElement('div');
        div.className = 'preview-item';

        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        img.alt = file.name;

        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-btn';
        removeBtn.textContent = '✕';
        removeBtn.addEventListener('click', () => {
            selectedImages.splice(index, 1);
            renderImagePreviews();
        });

        div.appendChild(img);
        div.appendChild(removeBtn);
        imgPreviewList.appendChild(div);
    });
}

// Drag & drop
imgDropZone.addEventListener('dragover', (e) => { e.preventDefault(); imgDropZone.classList.add('dragover'); });
imgDropZone.addEventListener('dragleave', () => imgDropZone.classList.remove('dragover'));
imgDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    imgDropZone.classList.remove('dragover');
    addImages(e.dataTransfer.files);
});
imgFileInput.addEventListener('change', (e) => addImages(e.target.files));

// Clear
imgClearBtn.addEventListener('click', () => {
    selectedImages = [];
    renderImagePreviews();
});

// Convert
imgConvertBtn.addEventListener('click', async () => {
    if (selectedImages.length === 0) {
        alert('Please select at least one image.');
        return;
    }

    imgConvertBtn.textContent = '⏳ Converting...';
    imgConvertBtn.disabled = true;

    try {
        const formData = new FormData();
        selectedImages.forEach(file => formData.append('files', file));

        const res = await fetch('/api/convert/images-to-pdf', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Conversion failed');
        }

        const blob = await res.blob();
        downloadBlob(blob, 'images_converted.pdf');
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        imgConvertBtn.textContent = '⬇️ Convert & Download PDF';
        imgConvertBtn.disabled = false;
    }
});

// ============ PDF TO IMAGE ============
const pdfDropZone = document.getElementById('pdf-drop-zone');
const pdfFileInput = document.getElementById('pdf-file-input');
const pdfOptions = document.getElementById('pdf-options');
const pdfFileInfo = document.getElementById('pdf-file-info');
const pdfConvertBtn = document.getElementById('pdf-convert-btn');
const pdfImgFormat = document.getElementById('pdf-img-format');
const pdfImgZoom = document.getElementById('pdf-img-zoom');

let selectedPDF = null;

function setPDFFile(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please select a PDF file.');
        return;
    }
    selectedPDF = file;
    pdfOptions.classList.remove('hidden');
    pdfFileInfo.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
}

// Drag & drop
pdfDropZone.addEventListener('dragover', (e) => { e.preventDefault(); pdfDropZone.classList.add('dragover'); });
pdfDropZone.addEventListener('dragleave', () => pdfDropZone.classList.remove('dragover'));
pdfDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    pdfDropZone.classList.remove('dragover');
    setPDFFile(e.dataTransfer.files[0]);
});
pdfFileInput.addEventListener('change', (e) => setPDFFile(e.target.files[0]));

// Convert
pdfConvertBtn.addEventListener('click', async () => {
    if (!selectedPDF) {
        alert('Please select a PDF file.');
        return;
    }

    pdfConvertBtn.textContent = '⏳ Converting...';
    pdfConvertBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', selectedPDF);
        formData.append('format', pdfImgFormat.value);
        formData.append('zoom', pdfImgZoom.value);

        const res = await fetch('/api/convert/pdf-to-images', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Conversion failed');
        }

        const blob = await res.blob();
        downloadBlob(blob, 'pdf_pages.zip');
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        pdfConvertBtn.textContent = '⬇️ Convert & Download ZIP';
        pdfConvertBtn.disabled = false;
    }
});

// ============ UTILS ============
function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
