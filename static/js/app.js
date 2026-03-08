/**
 * ShelfMark — Frontend Logic
 */

// State
const state = {
    absUrl: '',
    apiKey: '',
    csvFile: null,
    libraries: [],
    selectedLibraryId: null,
    previewData: null,
    activeFilter: 'all'
};

// DOM refs
const views = {
    connect: document.getElementById('view-connect'),
    library: document.getElementById('view-library'),
    preview: document.getElementById('view-preview'),
    summary: document.getElementById('view-summary')
};

const elems = {
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingText: document.getElementById('loading-text'),

    connectForm: document.getElementById('connect-form'),
    absUrl: document.getElementById('abs-url'),
    apiKey: document.getElementById('abs-api-key'),
    togglePasswordBtn: document.querySelector('.toggle-password'),
    fileDropZone: document.getElementById('file-drop-zone'),
    fileInput: document.getElementById('csv-file'),
    fileNameDisplay: document.getElementById('file-name-display'),

    librariesGrid: document.getElementById('libraries-grid'),
    btnBackToConnect: document.getElementById('back-to-connect'),

    btnBackToLibrary: document.getElementById('back-to-library'),
    btnApplyMigration: document.getElementById('btn-apply-migration'),
    statExact: document.getElementById('stat-exact'),
    statFuzzy: document.getElementById('stat-fuzzy'),
    statUnmatched: document.getElementById('stat-unmatched'),
    matchesTbody: document.getElementById('matches-tbody'),

    filterAll: document.getElementById('filter-all'),
    filterExact: document.getElementById('filter-exact'),
    filterFuzzy: document.getElementById('filter-fuzzy'),
    filterUnmatched: document.getElementById('filter-unmatched'),

    summaryMessage: document.getElementById('summary-message'),
    summaryError: document.getElementById('summary-failed-count'),
    summaryErrorBadge: document.getElementById('summary-error-badge'),
    btnRestart: document.getElementById('btn-restart'),
    
    snackbar: document.getElementById('snackbar'),
    snackbarText: document.getElementById('snackbar-text'),
    snackbarClose: document.querySelector('.snackbar-close')
};

// Initialize feather icons
feather.replace();

// View switching
function showView(viewName) {
    Object.values(views).forEach(v => {
        v.classList.remove('active-view');
        v.classList.add('hidden-view');
    });
    views[viewName].classList.remove('hidden-view');
    views[viewName].classList.add('active-view');
}

function showLoading(text = "Processing...") {
    elems.loadingText.textContent = text;
    elems.loadingOverlay.classList.remove('hidden');
    elems.loadingOverlay.setAttribute('aria-hidden', 'false');
}

function hideLoading() {
    elems.loadingOverlay.classList.add('hidden');
    elems.loadingOverlay.setAttribute('aria-hidden', 'true');
}

let snackbarTimeout;

function showSnackbar(message, type = 'error') {
    elems.snackbarText.textContent = message;
    elems.snackbar.className = '';
    elems.snackbar.classList.add('show', type);
    
    if (snackbarTimeout) clearTimeout(snackbarTimeout);
    
    snackbarTimeout = setTimeout(() => {
        elems.snackbar.classList.remove('show');
    }, 4000);
}

elems.snackbarClose.addEventListener('click', () => {
    elems.snackbar.classList.remove('show');
    if (snackbarTimeout) clearTimeout(snackbarTimeout);
});

function setFieldError(fieldId, message) {
    const wrap = fieldId === 'csv-file' ? elems.fileDropZone : document.getElementById(`wrap-${fieldId}`);
    const errorSpan = document.getElementById(`error-${fieldId}`);
    
    if (wrap) wrap.classList.add('input-error');
    if (errorSpan) {
        errorSpan.textContent = message;
        errorSpan.classList.add('show');
    }
}

function clearFieldError(fieldId) {
    const wrap = fieldId === 'csv-file' ? elems.fileDropZone : document.getElementById(`wrap-${fieldId}`);
    const errorSpan = document.getElementById(`error-${fieldId}`);
    
    if (wrap) wrap.classList.remove('input-error');
    if (errorSpan) {
        errorSpan.textContent = '';
        errorSpan.classList.remove('show');
    }
}

function validateUrl(val) {
    if (!val) return "Server URL is required";
    try {
        const url = new URL(val);
        if (!['http:', 'https:'].includes(url.protocol) || val.endsWith('/')) {
            return "Enter a valid URL (e.g., http://localhost:13378)";
        }
    } catch {
        return "Enter a valid URL (e.g., http://localhost:13378)";
    }
    return null;
}

function validateApiKey(val) {
    if (!val) return "API Key is required";
    return null;
}

function validateCsvFile() {
    if (!state.csvFile) return "Please upload a Goodreads CSV export";
    return null;
}

function validateConnectForm() {
    const urlVal = elems.absUrl.value.trim();
    const apiKeyVal = elems.apiKey.value.trim();
    
    clearFieldError('abs-url');
    clearFieldError('abs-api-key');
    clearFieldError('csv-file');
    
    let isValid = true;
    
    const urlErr = validateUrl(urlVal);
    if (urlErr) { setFieldError('abs-url', urlErr); isValid = false; }
    
    const apiKeyErr = validateApiKey(apiKeyVal);
    if (apiKeyErr) { setFieldError('abs-api-key', apiKeyErr); isValid = false; }
    
    const csvErr = validateCsvFile();
    if (csvErr) { setFieldError('csv-file', csvErr); isValid = false; }
    
    if (!isValid) {
        showSnackbar(`Please fix the errors in the form.`, 'warning');
    }
    
    return isValid;
}

// Blur listeners
elems.absUrl.addEventListener('blur', () => {
    clearFieldError('abs-url');
    const err = validateUrl(elems.absUrl.value.trim());
    if (err) setFieldError('abs-url', err);
});
elems.absUrl.addEventListener('input', () => clearFieldError('abs-url'));

elems.apiKey.addEventListener('blur', () => {
    clearFieldError('abs-api-key');
    const err = validateApiKey(elems.apiKey.value.trim());
    if (err) setFieldError('abs-api-key', err);
});
elems.apiKey.addEventListener('input', () => clearFieldError('abs-api-key'));

// ─── View 1: Connect ────────────────────────────────────────────────────

// Password toggle
elems.togglePasswordBtn.addEventListener('click', () => {
    const type = elems.apiKey.getAttribute('type') === 'password' ? 'text' : 'password';
    elems.apiKey.setAttribute('type', type);
    const icon = type === 'password' ? 'eye' : 'eye-off';
    elems.togglePasswordBtn.innerHTML = `<i data-feather="${icon}"></i>`;
    feather.replace();
});

// File drop zone
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    elems.fileDropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
});

['dragenter', 'dragover'].forEach(evt => {
    elems.fileDropZone.addEventListener(evt, () => elems.fileDropZone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(evt => {
    elems.fileDropZone.addEventListener(evt, () => elems.fileDropZone.classList.remove('dragover'), false);
});

elems.fileDropZone.addEventListener('drop', e => handleFiles(e.dataTransfer.files), false);
elems.fileInput.addEventListener('change', e => handleFiles(e.target.files), false);
elems.fileDropZone.addEventListener('click', () => elems.fileInput.click());

function handleFiles(files) {
    if (files.length === 0) return;
    const file = files[0];
    if (!file.name.endsWith('.csv')) {
        clearFieldError('csv-file');
        setFieldError('csv-file', "Only .csv files are accepted");
        showSnackbar("Only .csv files are accepted", "error");
        return;
    }
    clearFieldError('csv-file');
    state.csvFile = file;
    elems.fileNameDisplay.textContent = '';
    const icon = document.createElement('i');
    icon.setAttribute('data-feather', 'file-text');
    icon.style.cssText = 'width:14px;height:14px;';
    elems.fileNameDisplay.appendChild(icon);
    elems.fileNameDisplay.appendChild(document.createTextNode(' ' + file.name));
    feather.replace();
}

// Connect submit
elems.connectForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!validateConnectForm()) {
        return;
    }

    state.absUrl = elems.absUrl.value.trim();
    state.apiKey = elems.apiKey.value.trim();

    showLoading("Connecting to Audiobookshelf...");

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ abs_url: state.absUrl, api_key: state.apiKey })
        });

        const data = await response.json();

        if (response.ok) {
            state.libraries = data.libraries;
            renderLibraries();
            showView('library');
        } else {
            showSnackbar(data.detail || "Failed to connect.", 'error');
        }
    } catch (err) {
        showSnackbar("Could not reach the local server.", 'error');
        console.error(err);
    } finally {
        hideLoading();
    }
});

// ─── View 2: Library ────────────────────────────────────────────────────

elems.btnBackToConnect.addEventListener('click', () => showView('connect'));

function renderLibraries() {
    elems.librariesGrid.innerHTML = '';

    if (state.libraries.length === 0) {
        elems.librariesGrid.innerHTML = '<p class="card-desc" style="grid-column:1/-1;">No libraries found on this server.</p>';
        return;
    }

    state.libraries.forEach(lib => {
        const card = document.createElement('div');
        card.className = 'lib-card';

        const iconWrap = document.createElement('div');
        iconWrap.className = 'lib-card-icon';
        const icon = document.createElement('i');
        icon.setAttribute('data-feather', 'book');
        iconWrap.appendChild(icon);
        card.appendChild(iconWrap);

        const h3 = document.createElement('h3');
        h3.textContent = lib.name;
        card.appendChild(h3);

        card.addEventListener('click', () => selectLibrary(lib.id));
        elems.librariesGrid.appendChild(card);
    });
    feather.replace();
}

async function selectLibrary(libraryId) {
    state.selectedLibraryId = libraryId;
    showLoading("Analyzing matching books...");

    const formData = new FormData();
    formData.append("file", state.csvFile);
    formData.append("abs_url", state.absUrl);
    formData.append("api_key", state.apiKey);
    formData.append("library_id", libraryId);

    try {
        const response = await fetch('/api/analyze', { method: 'POST', body: formData });
        const resData = await response.json();

        if (response.ok) {
            state.previewData = resData.data;
            state.activeFilter = 'all';
            renderPreviewDashboard();
            showView('preview');
        } else {
            showSnackbar(resData.detail || "Analysis failed.", 'error');
        }
    } catch (err) {
        showSnackbar("Failed to perform analysis.", 'error');
        console.error(err);
    } finally {
        hideLoading();
    }
}

// ─── View 3: Preview ────────────────────────────────────────────────────

elems.btnBackToLibrary.addEventListener('click', () => showView('library'));

// Filter buttons
function setActiveFilter(filter) {
    state.activeFilter = filter;
    [elems.filterAll, elems.filterExact, elems.filterFuzzy, elems.filterUnmatched].forEach(btn => {
        btn.classList.remove('active');
    });
    const map = { all: elems.filterAll, exact: elems.filterExact, fuzzy: elems.filterFuzzy, unmatched: elems.filterUnmatched };
    map[filter].classList.add('active');
    applyFilter();
}

elems.filterAll.addEventListener('click', () => setActiveFilter('all'));
elems.filterExact.addEventListener('click', () => setActiveFilter('exact'));
elems.filterFuzzy.addEventListener('click', () => setActiveFilter('fuzzy'));
elems.filterUnmatched.addEventListener('click', () => setActiveFilter('unmatched'));

function applyFilter() {
    const rows = elems.matchesTbody.querySelectorAll('tr[data-match-type]');
    rows.forEach(row => {
        const type = row.dataset.matchType;
        if (state.activeFilter === 'all') {
            row.style.display = '';
        } else if (state.activeFilter === 'exact') {
            row.style.display = (type === 'exact_isbn' || type === 'exact_title_author') ? '' : 'none';
        } else if (state.activeFilter === 'fuzzy') {
            row.style.display = type === 'fuzzy' ? '' : 'none';
        } else if (state.activeFilter === 'unmatched') {
            row.style.display = type === 'unmatched' ? '' : 'none';
        }
    });
}

function renderPreviewDashboard() {
    const data = state.previewData;
    const stats = data.stats;

    elems.statExact.textContent = stats.exact_isbn + stats.exact_title_author;
    elems.statFuzzy.textContent = stats.fuzzy;
    elems.statUnmatched.textContent = stats.unmatched;

    // Reset filter UI
    setActiveFilter('all');

    elems.matchesTbody.innerHTML = '';

    const hasMatches = data.matches.length > 0;
    const hasUnmatched = data.unmatched && data.unmatched.length > 0;

    if (!hasMatches && !hasUnmatched) {
        elems.matchesTbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:2rem;color:var(--text-muted);">No matches found in this library.</td></tr>';
        elems.btnApplyMigration.disabled = true;
        elems.btnApplyMigration.style.opacity = '0.4';
        return;
    }

    elems.btnApplyMigration.disabled = !hasMatches;
    elems.btnApplyMigration.style.opacity = hasMatches ? '1' : '0.4';

    function createBadge(type) {
        const badgeMap = {
            exact_isbn: { cls: 'badge exact', text: 'ISBN' },
            exact_title_author: { cls: 'badge exact', text: 'Title/Author' },
            fuzzy: { cls: 'badge fuzzy', text: 'Fuzzy' }
        };
        const info = badgeMap[type];
        if (!info) return null;
        const span = document.createElement('span');
        span.className = info.cls;
        span.textContent = info.text;
        return span;
    }

    // Render matched rows
    data.matches.forEach((match) => {
        const tr = document.createElement('tr');
        tr.dataset.matchType = match.type;

        // Checkbox
        const tdCheck = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'custom-checkbox match-checkbox';
        checkbox.setAttribute('data-abs-id', match.abs.id);
        checkbox.checked = true;
        tdCheck.appendChild(checkbox);
        tr.appendChild(tdCheck);

        // Goodreads
        const tdGr = document.createElement('td');
        tdGr.innerHTML = `<div class="book-meta"><span class="book-title">${escapeHtml(match.goodreads.title)}</span><span class="book-author">${escapeHtml(match.goodreads.author)}</span></div>`;
        tr.appendChild(tdGr);

        // ABS
        const tdAbs = document.createElement('td');
        tdAbs.innerHTML = `<div class="book-meta"><span class="book-title">${escapeHtml(match.abs.title)}</span><span class="book-author">${escapeHtml(match.abs.author)}</span></div>`;
        tr.appendChild(tdAbs);

        // Badge
        const tdBadge = document.createElement('td');
        const badge = createBadge(match.type);
        if (badge) tdBadge.appendChild(badge);
        tr.appendChild(tdBadge);

        elems.matchesTbody.appendChild(tr);
    });

    // Render unmatched rows
    if (data.unmatched) {
        data.unmatched.forEach((item) => {
            const tr = document.createElement('tr');
            tr.dataset.matchType = 'unmatched';
            tr.style.display = state.activeFilter === 'all' || state.activeFilter === 'unmatched' ? '' : 'none';

            // Empty checkbox cell
            const tdCheck = document.createElement('td');
            tr.appendChild(tdCheck);

            // Goodreads
            const tdGr = document.createElement('td');
            tdGr.innerHTML = `<div class="book-meta"><span class="book-title">${escapeHtml(item.title)}</span><span class="book-author">${escapeHtml(item.author)}</span></div>`;
            tr.appendChild(tdGr);

            // No ABS match
            const tdAbs = document.createElement('td');
            tdAbs.style.color = 'var(--text-muted)';
            tdAbs.textContent = 'No match found';
            tr.appendChild(tdAbs);

            // Badge
            const tdBadge = document.createElement('td');
            const span = document.createElement('span');
            span.className = 'badge unmatched';
            span.textContent = 'Unmatched';
            tdBadge.appendChild(span);
            tr.appendChild(tdBadge);

            elems.matchesTbody.appendChild(tr);
        });
    }
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Apply migration
elems.btnApplyMigration.addEventListener('click', async () => {
    const checkboxes = document.querySelectorAll('.match-checkbox:checked');
    const itemsToApply = Array.from(checkboxes).map(cb => ({ id: cb.getAttribute('data-abs-id') }));

    if (itemsToApply.length === 0) {
        showSnackbar("No items selected.", "warning");
        return;
    }

    showLoading(`Marking ${itemsToApply.length} book(s) as read...`);

    try {
        const response = await fetch('/api/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ abs_url: state.absUrl, api_key: state.apiKey, items: itemsToApply })
        });

        const data = await response.json();

        if (response.ok) {
            showSummary(data.summary);
            showSnackbar("Migration completed successfully!", "success");
        } else {
            showSnackbar(data.detail || "Application failed.", "error");
        }
    } catch (err) {
        showSnackbar("Failed to apply changes.", "error");
        console.error(err);
    } finally {
        hideLoading();
    }
});

// ─── View 4: Summary ────────────────────────────────────────────────────

function showSummary(summary) {
    const count = summary.success;
    const bookWord = count === 1 ? 'book' : 'books';
    elems.summaryMessage.textContent = `${count} ${bookWord} marked as read in Audiobookshelf.`;

    if (summary.failed > 0) {
        elems.summaryErrorBadge.style.display = 'flex';
        elems.summaryError.textContent = summary.failed;
    } else {
        elems.summaryErrorBadge.style.display = 'none';
    }

    // Clear sensitive data
    state.apiKey = '';
    elems.apiKey.value = '';

    showView('summary');
    feather.replace();
}

elems.btnRestart.addEventListener('click', () => {
    state.csvFile = null;
    state.libraries = [];
    state.selectedLibraryId = null;
    state.previewData = null;
    state.activeFilter = 'all';
    elems.fileNameDisplay.textContent = '';
    elems.fileInput.value = '';
    elems.matchesTbody.innerHTML = '';
    elems.btnApplyMigration.disabled = false;
    elems.btnApplyMigration.style.opacity = '1';
    showView('connect');
});
