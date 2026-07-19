/**
 * API module - handles communication with the FastAPI backend.
 */

export async function uploadPDF(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
}

export async function fetchPageImage(sessionId, pageNum) {
    const res = await fetch(`/api/page/${sessionId}/${pageNum}`);
    if (!res.ok) throw new Error('Failed to fetch page');
    return res.blob();
}

export async function fetchPageText(sessionId, pageNum) {
    const res = await fetch(`/api/text/${sessionId}/${pageNum}`);
    if (!res.ok) throw new Error('Failed to fetch text');
    return res.json();
}

export async function submitEdits(sessionId, edits) {
    const res = await fetch('/api/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, edits }),
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Edit failed');
    }
    return res.blob();
}
