/* DreamCam Remote — vanilla JS */

// --- State ---
let currentStyle = '';
let previewVersion = -1;
let eventSource = null;
let busy = false;

// --- DOM refs ---
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// --- SSE ---
function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource('/api/events');

    eventSource.addEventListener('status', (e) => {
        updateStatus(e.data);
    });

    eventSource.addEventListener('preview', (e) => {
        const v = parseInt(e.data, 10);
        if (v > previewVersion) {
            previewVersion = v;
            refreshPreview();
        }
    });

    eventSource.addEventListener('error', (e) => {
        if (e.data) showToast('Error: ' + e.data);
    });

    eventSource.onerror = () => {
        setTimeout(connectSSE, 3000);
    };
}

// --- Status ---
function updateStatus(status) {
    const banner = $('#status-banner');
    const labels = {
        idle: 'Ready',
        capturing: 'Capturing...',
        dreaming: 'Dreaming...',
        done: 'Done!',
        error: 'Error',
    };

    banner.textContent = labels[status] || status;
    banner.className = 'status-' + status;

    busy = (status === 'capturing' || status === 'dreaming');
    $('#shutter-btn').disabled = busy;

    // Auto-refresh gallery when done
    if (status === 'done') {
        loadGallery();
        refreshPreview();
        // Return to idle after 2s
        setTimeout(() => {
            if ($('#status-banner').className === 'status-done') {
                updateStatus('idle');
            }
        }, 2000);
    }
}

// --- API calls ---
async function capture() {
    if (busy) return;
    try {
        const res = await fetch('/api/capture', { method: 'POST' });
        if (res.status === 409) showToast('Camera is busy');
        else if (!res.ok) showToast('Capture failed');
    } catch (e) {
        showToast('Connection error');
    }
}

async function setStyle(name) {
    try {
        const res = await fetch('/api/style/' + encodeURIComponent(name), { method: 'POST' });
        if (res.ok) {
            currentStyle = name;
            highlightActiveStyle();
            $('#style-current').textContent = name;
        } else {
            showToast('Failed to set style');
        }
    } catch (e) {
        showToast('Connection error');
    }
}

async function uploadPhoto(file) {
    if (busy) return;
    const form = new FormData();
    form.append('file', file);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: form });
        if (res.status === 409) showToast('Camera is busy');
        else if (!res.ok) showToast('Upload failed');
    } catch (e) {
        showToast('Connection error');
    }
}

function refreshPreview() {
    const img = $('#preview-img');
    if (img) {
        img.src = '/api/preview?v=' + previewVersion;
    }
}

// --- Styles ---
async function loadStyles() {
    try {
        const res = await fetch('/api/styles');
        const styles = await res.json();
        renderStyles(styles);

        // Also get current style
        const statusRes = await fetch('/api/status');
        const status = await statusRes.json();
        currentStyle = status.style;
        $('#style-current').textContent = currentStyle;
        highlightActiveStyle();
    } catch (e) {
        console.error('Failed to load styles:', e);
    }
}

function renderStyles(styles) {
    const container = $('#style-categories');
    const categories = {};
    const categoryLabels = {
        art: 'Art Styles',
        frame: 'Creative Frames',
        env: 'Environments',
        text: 'Text Modes',
    };

    for (const s of styles) {
        if (!categories[s.category]) categories[s.category] = [];
        categories[s.category].push(s);
    }

    container.innerHTML = '';
    for (const [cat, catStyles] of Object.entries(categories)) {
        const div = document.createElement('div');
        div.className = 'style-category';
        div.innerHTML = `<div class="style-category-label">${categoryLabels[cat] || cat}</div>`;

        const chips = document.createElement('div');
        chips.className = 'style-chips';

        for (const s of catStyles) {
            const chip = document.createElement('button');
            chip.className = 'style-chip';
            chip.textContent = s.name;
            chip.dataset.style = s.name;
            chip.title = s.prompt;
            chip.onclick = () => setStyle(s.name);
            chips.appendChild(chip);
        }

        div.appendChild(chips);
        container.appendChild(div);
    }
}

function highlightActiveStyle() {
    $$('.style-chip').forEach((chip) => {
        chip.classList.toggle('active', chip.dataset.style === currentStyle);
    });
}

// --- Gallery ---
async function loadGallery() {
    try {
        const res = await fetch('/api/gallery');
        const images = await res.json();
        renderGallery(images);
    } catch (e) {
        console.error('Failed to load gallery:', e);
    }
}

function renderGallery(images) {
    const grid = $('#gallery-grid');
    const empty = $('#gallery-empty');

    if (images.length === 0) {
        grid.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');
    grid.innerHTML = '';

    for (const img of images) {
        const el = document.createElement('img');
        el.className = 'gallery-thumb';
        el.src = '/api/gallery/' + encodeURIComponent(img.filename);
        el.alt = img.filename;
        el.loading = 'lazy';
        el.onclick = () => openViewer(img.filename);
        grid.appendChild(el);
    }
}

function openViewer(filename) {
    const viewer = $('#gallery-viewer');
    const img = $('#gallery-full');
    const dl = $('#gallery-download');
    const url = '/api/gallery/' + encodeURIComponent(filename);

    img.src = url;
    dl.href = url;
    dl.download = filename;
    viewer.classList.remove('hidden');
}

function closeViewer() {
    $('#gallery-viewer').classList.add('hidden');
}

// --- Toast ---
let toastTimer = null;

function showToast(msg) {
    let toast = $('#toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2500);
}

// --- Tabs ---
function initTabs() {
    $$('.tab').forEach((tab) => {
        tab.onclick = () => {
            $$('.tab').forEach((t) => t.classList.remove('active'));
            $$('.tab-content').forEach((c) => c.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            $(`#${target}-tab`).classList.add('active');

            if (target === 'gallery') loadGallery();
            if (target === 'preview') refreshPreview();
        };
    });
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    connectSSE();
    loadStyles();
    loadGallery();

    $('#shutter-btn').onclick = capture;

    $('#upload-input').onchange = (e) => {
        if (e.target.files[0]) {
            uploadPhoto(e.target.files[0]);
            e.target.value = '';  // allow re-upload of same file
        }
    };

    $('#gallery-close').onclick = closeViewer;

    // Initial preview
    refreshPreview();
});
