const API_BASE = '';

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        tab.classList.add('active');
        const tabId = tab.dataset.tab + '-tab';
        document.getElementById(tabId).classList.add('active');
    });
});

// Search form
document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const query = document.getElementById('search-query').value.trim();
    const maxResults = parseInt(document.getElementById('max-results').value) || 5;
    const extract = document.getElementById('extract-content').checked;
    const summarize = document.getElementById('summarize-content').checked;
    const bypassCache = document.getElementById('bypass-cache').checked;

    const statusEl = document.getElementById('search-status');
    const resultsEl = document.getElementById('search-results');
    const submitBtn = e.target.querySelector('button[type="submit"]');

    statusEl.className = 'status-message loading';
    statusEl.textContent = summarize
        ? 'Searching, extracting, and summarizing...'
        : extract
        ? 'Searching and extracting content...'
        : 'Searching...';
    resultsEl.innerHTML = '';
    submitBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                max_results: maxResults,
                extract,
                summarize,
                bypass_cache: bypassCache,
            }),
        });

        if (!response.ok) {
            throw new Error(`Search failed: ${response.status}`);
        }

        const data = await response.json();

        let timing = `Search: ${data.search_time_ms}ms`;
        if (data.extract_time_ms) timing += ` | Extract: ${data.extract_time_ms}ms`;
        if (data.summarize_time_ms) timing += ` | Summarize: ${data.summarize_time_ms}ms`;

        statusEl.className = 'status-message success';
        statusEl.textContent = `Found ${data.total_results} results (${timing})`;

        resultsEl.innerHTML = data.results.map((result, index) => `
            <div class="result-card">
                <div class="result-header">
                    <div>
                        <div class="result-title">
                            <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener">
                                ${index + 1}. ${escapeHtml(result.title || 'Untitled')}
                            </a>
                        </div>
                        <div class="result-url">${escapeHtml(result.url)}</div>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        ${result.from_cache ? '<span class="result-badge cached">Cached</span>' : ''}
                        ${result.engine ? `<span class="result-badge engine">${escapeHtml(result.engine)}</span>` : ''}
                    </div>
                </div>
                <div class="result-snippet">${escapeHtml(result.snippet || '')}</div>
                ${result.summary ? `
                    <div class="result-summary">
                        <div class="result-summary-label">AI Summary</div>
                        ${escapeHtml(result.summary)}
                    </div>
                ` : ''}
                ${result.markdown ? `
                    <div class="result-content">${escapeHtml(result.markdown.slice(0, 500))}${result.markdown.length > 500 ? '...' : ''}</div>
                    <div class="result-actions">
                        <button class="btn secondary" onclick="showFullContent('${escapeHtml(result.title || 'Content')}', ${index}, 'search')">
                            View Full Content
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');

        window.lastSearchResults = data.results;

    } catch (error) {
        statusEl.className = 'status-message error';
        statusEl.textContent = error.message;
    } finally {
        submitBtn.disabled = false;
    }
});

// Fetch form
document.getElementById('fetch-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = document.getElementById('fetch-url').value.trim();
    const forceJs = document.getElementById('force-js').checked;
    const summarize = document.getElementById('fetch-summarize').checked;
    const bypassCache = document.getElementById('fetch-bypass-cache').checked;

    const statusEl = document.getElementById('fetch-status');
    const resultEl = document.getElementById('fetch-result');
    const submitBtn = e.target.querySelector('button[type="submit"]');

    statusEl.className = 'status-message loading';
    statusEl.textContent = summarize
        ? 'Fetching and summarizing...'
        : forceJs
        ? 'Fetching with JavaScript rendering...'
        : 'Fetching...';
    resultEl.innerHTML = '';
    submitBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                force_js: forceJs,
                summarize,
                bypass_cache: bypassCache,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Fetch failed: ${response.status}`);
        }

        const data = await response.json();

        statusEl.className = 'status-message success';
        statusEl.textContent = data.from_cache ? 'Loaded from cache' : 'Fetched successfully';

        resultEl.innerHTML = `
            <div class="result-card">
                <div class="result-header">
                    <div>
                        <div class="result-title">
                            <a href="${escapeHtml(data.canonical_url)}" target="_blank" rel="noopener">
                                ${escapeHtml(data.canonical_url)}
                            </a>
                        </div>
                        <div class="result-url">
                            Hash: ${escapeHtml(data.content_hash)}
                            ${data.changed_since_last !== null ? ` | Changed: ${data.changed_since_last ? 'Yes' : 'No'}` : ''}
                        </div>
                    </div>
                    ${data.from_cache ? '<span class="result-badge cached">Cached</span>' : ''}
                </div>
                ${data.summary ? `
                    <div class="result-summary">
                        <div class="result-summary-label">AI Summary</div>
                        ${escapeHtml(data.summary)}
                    </div>
                ` : ''}
                <div class="result-content">${escapeHtml(data.markdown.slice(0, 1000))}${data.markdown.length > 1000 ? '...' : ''}</div>
                <div class="result-actions">
                    <button class="btn secondary" onclick="showFetchContent()">
                        View Full Content
                    </button>
                </div>
            </div>
        `;

        window.lastFetchResult = data;

    } catch (error) {
        statusEl.className = 'status-message error';
        statusEl.textContent = error.message;
    } finally {
        submitBtn.disabled = false;
    }
});

// Health check
document.getElementById('refresh-status').addEventListener('click', async () => {
    const statusEl = document.getElementById('health-status');
    const btn = document.getElementById('refresh-status');

    btn.disabled = true;
    statusEl.innerHTML = '<p>Checking...</p>';

    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();

        statusEl.innerHTML = `
            <h3 style="color: var(--${data.status === 'healthy' ? 'success' : 'warning'}-color); margin-bottom: 1rem;">
                Status: ${data.status.toUpperCase()}
            </h3>
            <div class="status-grid">
                <div class="status-item">
                    <span class="label">SearXNG</span>
                    <span class="value ${data.searxng ? 'ok' : 'error'}">
                        ${data.searxng ? 'Connected' : 'Disconnected'}
                    </span>
                </div>
                <div class="status-item">
                    <span class="label">Ollama</span>
                    <span class="value ${data.ollama ? 'ok' : 'error'}">
                        ${data.ollama ? 'Available' : 'Unavailable'}
                    </span>
                </div>
                <div class="status-item">
                    <span class="label">Playwright Contexts</span>
                    <span class="value">${data.playwright_contexts}</span>
                </div>
            </div>
        `;
    } catch (error) {
        statusEl.innerHTML = `<p style="color: var(--error-color);">Failed to fetch status: ${error.message}</p>`;
    } finally {
        btn.disabled = false;
    }
});

// Modal functions
function showFullContent(title, index, type) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');

    let content = '';
    if (type === 'search' && window.lastSearchResults && window.lastSearchResults[index]) {
        content = window.lastSearchResults[index].markdown || 'No content available';
    }

    modalTitle.textContent = title;
    modalBody.textContent = content;
    modal.classList.add('active');
}

function showFetchContent() {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');

    if (window.lastFetchResult) {
        modalTitle.textContent = window.lastFetchResult.canonical_url;
        modalBody.textContent = window.lastFetchResult.markdown || 'No content available';
        modal.classList.add('active');
    }
}

// Close modal
document.querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('modal').classList.remove('active');
});

document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        e.currentTarget.classList.remove('active');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.getElementById('modal').classList.remove('active');
    }
});

// Utility
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
