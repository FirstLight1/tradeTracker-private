import { renderAlert, downloadFile, updateInventoryValueAndTotalProfit } from "./utils/renderUtil.js";
import { csrfFetch } from "./utils/sanitizers.js";

function bindSoldReportButton() {
    const salesBtn = document.querySelector('.sales-btn');
    if (!salesBtn || salesBtn.dataset.headerReportBound === 'true') return;

    salesBtn.dataset.headerReportBound = 'true';
    salesBtn.addEventListener('click', () => {
        const div = document.createElement('div');
        div.classList.add('sold-report-container');
        div.innerHTML = `
            <div class="sold-report-content">
                <form class="sold-report-form" method="get">
                <div>
                    <label for="sold-month">Month:</label>
                    <input type="number" id="sold-month" name="sold-month" min="1" max="12" required value=${new Date().getMonth() + 1}>
                </div>
                <div>
                    <label for="sold-year">Year:</label>
                    <input type="number" id="sold-year" name="sold-year" min="2000" max="2100" required value=${new Date().getFullYear()}>
                </div>
                <div class="generate-report-button">
                    <button type="submit">Generate Report</button>
                </div>
                </form>
            </div>
        `;
        document.body.appendChild(div);

        const form = div.querySelector('.sold-report-form');
        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const monthInput = form.querySelector('#sold-month');
                const yearInput = form.querySelector('#sold-year');
                if (!monthInput || !yearInput) return;
                await generateSoldReport(monthInput.value, yearInput.value, div);
            });
        }

        div.addEventListener('click', (event) => {
            if (event.target === div) div.remove();
        });
    });
}

async function generateSoldReport(month, year, div) {
    try {
        const response = await csrfFetch(`/generateSoldReport?month=${month}&year=${year}`);
        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            const err = await response.json();
            renderHeaderAlert(`Error generating sold report: ${err}`, 'error');
            return;
        }
        downloadFile(response);
        div.remove();
    } catch (e) {
        renderHeaderAlert('Error: ' + e, 'error');
    }
}

function bindUploadCSVButton() {
    const uploadBtn = document.querySelector('.upload-csv-btn');
    if (!uploadBtn || uploadBtn.dataset.headerUploadBound === 'true') return;

    uploadBtn.dataset.headerUploadBound = 'true';
    uploadBtn.addEventListener('click', () => {
        const div = document.createElement('div');
        div.classList.add('reciever-div');
        div.innerHTML = `
            <div class="modal-content upload-modal">
                <span class="close-modal">&times;</span>
                <div class="upload-option upload-option-disabled">
                    <p>CM sold CSV</p>
                    <label class="upload-file-label">
                        <span>Choose file</span>
                        <input type="file" accept=".csv" class="import-cm-sold-csv" disabled>
                    </label>
                </div>
                <div class="upload-option">
                    <p>Sold CSV</p>
                    <label class="upload-file-label">
                        <span>Choose files</span>
                        <input type="file" accept=".csv" class="import-sold-csv" multiple>
                    </label>
                </div>
                <div class="upload-option">
                    <p>Inventory CSV</p>
                    <label class="upload-file-label">
                        <span>Choose file</span>
                        <input type="file" accept=".csv" class="import-inventory-csv" multiple>
                    </label>
                </div>
            </div>
        `;
        document.body.appendChild(div);

        bindImportCSV('.import-inventory-csv', 'inventory', div);
        bindImportCSV('.import-sold-csv', 'sold', div);

        const closeButton = div.querySelector('.close-modal');
        if (closeButton) closeButton.addEventListener('click', () => div.remove());
        div.addEventListener('click', (event) => {
            if (event.target === div) div.remove();
        });
    });
}

function bindImportCSV(selector, type, root = document) {
    if (!root || !root.querySelector) return;
    const input = root.querySelector(selector);
    if (!input || input.dataset.csvImportBound === 'true') return;

    input.dataset.csvImportBound = 'true';
    input.addEventListener('change', async (event) => {
        const files = event.target.files;
        if (!files || !files.length) return;

        const formData = new FormData();
        for (const file of files) {
            formData.append('csv-upload', file);
        }
        formData.append('type', type);

        const spinner = showProcessingSpinner(root);
        try {
            const response = await csrfFetch('/importCSV', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            switch (data.status) {
                case 'success': {
                    if (data.download_url) {
                        const downloadResponse = await fetch(data.download_url);
                        if (!downloadResponse.ok) throw new Error('download failed');
                        const blob = await downloadResponse.blob();
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = 'processed.zip';
                        link.click();
                        URL.revokeObjectURL(url);
                    }

                    const failed = Array.isArray(data.failed) ? data.failed : [];
                    const rejected = Array.isArray(data.rejected) ? data.rejected : [];
                    if (failed.length || rejected.length) {
                        const lines = [];
                        if (failed.length) {
                            lines.push(`${failed.length} order(s) failed to process:`);
                            failed.forEach(item => lines.push(`- #${item.idOrder} ${item.name || ''} - ${item.reason || 'unknown error'}`));
                        }
                        if (rejected.length) {
                            lines.push(`${rejected.length} order(s) skipped (items not in inventory):`);
                            rejected.forEach(item => lines.push(`- #${item.idOrder} ${item.name || ''}`));
                        }
                        renderHeaderAlert(lines.join('\n'), 'error');
                    } else {
                        window.location.reload();
                    }
                    break;
                }
                case 'missing':
                    renderHeaderAlert('No file uploaded', 'error');
                    break;
                case 'file':
                    renderHeaderAlert('No file selected', 'error');
                    break;
                case 'extension':
                    renderHeaderAlert('Please upload valid CSV file', 'error');
                    break;
                case 'duplicate':
                    renderHeaderAlert('File already uploaded', 'error');
                    break;
                case 'error':
                    renderHeaderAlert('Error processing CSV: ' + (data.message || ''), 'error');
                    break;
            }
        } catch (e) {
            renderHeaderAlert('Error processing CSV: ' + e, 'error');
        } finally {
            hideProcessingSpinner(spinner);
        }
    });
}

function showProcessingSpinner(root, delay = 400) {
    const modal = root && root.querySelector ? root.querySelector('.modal-content') : null;
    const container = modal || document.body;
    const handle = { overlay: null, timer: null };
    handle.timer = setTimeout(() => {
        const overlay = document.createElement('div');
        overlay.className = 'processing-spinner-overlay';
        overlay.innerHTML = `
            <div class="processing-spinner"></div>
            <p class="processing-spinner-text">Processing CSV...</p>
        `;
        container.appendChild(overlay);
        handle.overlay = overlay;
    }, delay);
    return handle;
}

function hideProcessingSpinner(handle) {
    if (!handle) return;
    clearTimeout(handle.timer);
    if (handle.overlay) handle.overlay.remove();
}

function renderHeaderAlert(message, type) {
    ensureAlertContainer();
    renderAlert(message, type);
}

function ensureAlertContainer() {
    if (!document.querySelector('#alert-div')) {
        const alertContainer = document.createElement('div');
        alertContainer.id = 'alert-div';
        document.body.appendChild(alertContainer);
    }
}

function initializeHeaderActions() {
    bindSoldReportButton();
    bindUploadCSVButton();

    const inventoryValue = document.querySelector('.inventory-value-value');
    if (inventoryValue && inventoryValue.dataset.headerInventoryLoaded !== 'true') {
        inventoryValue.dataset.headerInventoryLoaded = 'true';
        ensureAlertContainer();
        updateInventoryValueAndTotalProfit();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeHeaderActions, { once: true });
} else {
    initializeHeaderActions();
}
