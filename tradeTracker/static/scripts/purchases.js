import { renderField, renderAlert, scrollOnLoad, updateInventoryValueAndTotalProfit, downloadFile } from "./utils/renderUtil.js";
import { escapeHtml, sanitizeNumericId, sanitizeClassToken, csrfFetch } from "./utils/sanitizers.js";


function parsePaymentMethods(paymentMethodData) {
    if (!paymentMethodData) return [];

    try {
        const parsed = JSON.parse(paymentMethodData);
        if (Array.isArray(parsed)) return parsed;
    } catch (e) {
        return paymentMethodData.trim().split(' ').map(type => ({ type: type, amount: 0 }));
    }

    return [];
}

function formatPaymentDisplay(payments) {
    if (!payments || payments.length === 0) return 'No payment method';

    return payments.map(p => {
        const type = escapeHtml(p.type || '');
        const amount = parseFloat(p.amount || 0).toFixed(2);
        return `${type}: ${amount}€`;
    }).join('<br>');
}

function isEmpty(obj) {
    return Object.keys(obj).length === 0;
}

function soldReportBtn() {
    const salesBtn = document.querySelector('.sales-btn');
    salesBtn.addEventListener('click', () => {
        const div = document.createElement('div');
        div.classList.add('sold-report-container');
        div.innerHTML = `
            <div class="sold-report-content">
                <form class="sold-report-form" method="get">
                <div>
                    <label for="sold-month">Month:</label>
                    <input type="number" id="sold-month" name="sold-month" min="1" max="12" required value=${new Date().getMonth()}>
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
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const month = form.querySelector('#sold-month').value;
            const year = form.querySelector('#sold-year').value;
            generateSoldReport(month, year, div);
        });
        div.addEventListener('click', (event) => {
            if (event.target === div) {
                div.remove();
            }
        });
    });
}

async function generateSoldReport(month, year, div) {
    const response = await csrfFetch(`/generateSoldReport?month=${month}&year=${year}`);
    const contentType = response.headers.get('content-type') || '';

    if (!response.ok || contentType.includes('application/json')) {
        const err = await response.json();
        renderAlert(`Error generating sold report: ${err}`, 'error');
        return;
    }
    try {
        downloadFile(response)
        div.remove();
    } catch (e) {
        renderAlert('Error: ' + e, 'error');
    }
}

function uploadCSVModal() {
    const uploadBtn = document.querySelector('.upload-csv-btn');
    if (!uploadBtn) return;
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
                <div class="upload-option ">
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

        const close = () => div.remove();
        div.querySelector('.close-modal').addEventListener('click', close);
        div.addEventListener('click', (event) => {
            if (event.target === div) close();
        });
    });
}

function bindImportCSV(selector, type, root = document) {
    const input = root.querySelector(selector);
    if (!input) return;
    input.addEventListener('change', async (event) => {
        const files = event.target.files;
        if (files && files.length) {
            const formData = new FormData();
            for (const file of files) {
                formData.append("csv-upload", file);
            }
            formData.append("type", type);
            const spinner = showProcessingSpinner(root);
            try {
                const response = await csrfFetch('/importCSV', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                switch (data.status) {
                    case "success": {
                        if (data.download_url) {
                            const resp = await fetch(data.download_url);
                            if (!resp.ok) throw new Error("download failed");
                            const blob = await resp.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = "processed.zip";
                            a.click();
                            URL.revokeObjectURL(url);
                        }
                        const failed = Array.isArray(data.failed) ? data.failed : [];
                        const rejected = Array.isArray(data.rejected) ? data.rejected : [];
                        if (failed.length || rejected.length) {
                            const lines = [];
                            if (failed.length) {
                                lines.push(`${failed.length} order(s) failed to process:`);
                                failed.forEach(f => lines.push(`• #${f.idOrder} ${f.name || ''} — ${f.reason || 'unknown error'}`));
                            }
                            if (rejected.length) {
                                lines.push(`${rejected.length} order(s) skipped (items not in inventory):`);
                                rejected.forEach(r => lines.push(`• #${r.idOrder} ${r.name || ''}`));
                            }
                            renderAlert(lines.join('\n'), 'error');
                        } else {
                            window.location.reload();
                        }
                        break;
                    }
                    case "missing":
                        renderAlert('No file uploaded', 'error')
                        break;
                    case "file":
                        renderAlert('No file selected', 'error')
                        break;
                    case "extension":
                        renderAlert('Please upload valid CSV file', 'error')
                        break;
                    case "duplicate":
                        renderAlert('File already uploaded', 'error')
                        break;
                    case "error":
                        renderAlert('Error processing CSV: ' + (data.message || ''), 'error')
                        break;
                }
            } catch (e) {
                renderAlert('Error processing CSV: ' + e + ', Error code: Px18', 'error')
            } finally {
                hideProcessingSpinner(spinner);
            }
        }
    })
}

function showProcessingSpinner(root, delay = 400) {
    const container = (root && root.querySelector && root.querySelector('.modal-content')) || document.body;
    const handle = { overlay: null, timer: null };
    handle.timer = setTimeout(() => {
        const overlay = document.createElement('div');
        overlay.className = 'processing-spinner-overlay';
        overlay.innerHTML = `
            <div class="processing-spinner"></div>
            <p class="processing-spinner-text">Processing CSV…</p>
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

function formatSealedDate(rawDate) {
    if (!rawDate) return '';
    const timeStamp = String(rawDate).replace('Z', '');
    const date = new Date(timeStamp);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

async function loadAuctionContent(button) {
    const auctionId = Number(button.getAttribute('data-id'));
    const cardsUrl = '/loadAllCards/' + auctionId;
    const sealedUrl = '/loadAllSealed/' + auctionId;
    const auctionDiv = button.closest('.auction-tab');
    const cardsContainer = auctionDiv.querySelector('.cards-container');
    try {
        if (cardsContainer.childElementCount === 0 || cardsContainer.hidden) {
            cardsContainer.hidden = false;
            button.textContent = 'Hide';

            if (cardsContainer.childElementCount === 0) {
                const response = await csrfFetch(cardsUrl);
                const cards = await response.json();
                if (isEmpty(cards)) {
                    cardsContainer.innerHTML = '';
                } else {
                    cardsContainer.innerHTML = `
                    <div class="cards-header">
                        <p>Card name</p>
                        <p>Card number</p>
                        <p>Condition</p>
                        <p>Buy price</p>
                        <p>Market value</p>
                        <p>Margin</p>
                        <p></p>
                        <p></p>
                        <p></p>
                    </div>
                `;
                    cards.forEach(card => {
                        const safeCardConditionClass = sanitizeClassToken(card.condition || 'Unknown');
                        const cardDiv = document.createElement('div');
                        cardDiv.classList.add('card');
                        cardDiv.innerHTML = `
                        ${renderField(card.card_name != null ? DOMPurify.sanitize(card.card_name) : '', 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                        ${renderField(card.card_num != null ? DOMPurify.sanitize(card.card_num) : '', 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                        <p class='card-info condition ${safeCardConditionClass}' data-field="condition">${DOMPurify.sanitize(card.condition) ? DOMPurify.sanitize(card.condition) : 'Unknown'}</p>
                        ${renderField(card.card_price != null ? DOMPurify.sanitize(card.card_price) + '€' : '', 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                        ${renderField(card.market_value != null ? DOMPurify.sanitize(card.market_value) + '€' : '', 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                        ${renderField(card.card_price !== null && card.market_value !== null ? (card.market_value - card.card_price).toFixed(2) + '€' : '', 'text', ['card-info', 'profit'], 'profit', true)}
                        <p></p>
                        <p></p>
                        <p></p>
                    `;
                        cardsContainer.appendChild(cardDiv);
                    });
                }

                try {
                    const responseSealed = await csrfFetch(sealedUrl);
                    const sealedData = await responseSealed.json();

                    sealedData.forEach(sealedItem => {
                        const sealedDiv = document.createElement('div');
                        sealedDiv.classList.add('sealed-item');

                        const margin = (Number(sealedItem.market_value) - Number(sealedItem.price)).toFixed(2);
                        const formatedDate = formatSealedDate(sealedItem.date);

                        sealedDiv.innerHTML = `
                            <p class='sealed-quantity'>${DOMPurify.sanitize(sealedItem.quantity)}</p>
                            <p class="sealed-name">${DOMPurify.sanitize(sealedItem.name)}</p>
                            <p class="sealed-price">${DOMPurify.sanitize(sealedItem.price)}€</p>
                            <p class="VAT-sealed">${(Number(DOMPurify.sanitize(sealedItem.price)) / 1.23).toFixed(2)}</p>
                            <p class="sealed-market-value">${DOMPurify.sanitize(sealedItem.market_value)}€</p>
                            <p class="sealed-margin">${DOMPurify.sanitize(margin)}€</p>
                            <p class="sealed-date">${DOMPurify.sanitize(formatedDate)}</p>
                            <p></p>
                            <p></p>
                            <p></p>
                        `;

                        cardsContainer.appendChild(sealedDiv);
                    });
                } catch (error) {
                    renderAlert('Error loading sealed items: ' + error, 'error');
                }
            }
        } else {
            cardsContainer.hidden = true;
            button.textContent = 'View';
        }
    } catch (error) {
        renderAlert('Error loading cards: ' + error, 'error');
    }
}

async function loadAuctions() {
    const auctionContainer = document.querySelector('.auction-container');
    try {
        const response = await csrfFetch('/loadPurchases');
        const data = await response.json();
        data.forEach(auction => {
            const safeAuctionId = sanitizeNumericId(auction.id);
            const auctionDiv = document.createElement('div');
            auctionDiv.classList.add('auction-tab');
            auctionDiv.id = safeAuctionId;
            if (auction.auction_name === 'Singles') {
                auctionDiv.classList.add('singles');
            }
            auctionDiv.setAttribute('data-id', safeAuctionId);
            let auctionName = auction.auction_name || "Auction " + (auction.id - 1);
            let auctionPrice = auction.auction_price;
            const buyDate = new Date(auction.date_created);
            let formatedDate = buyDate.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
            if (formatedDate === 'Invalid Date') {
                formatedDate = new Date(String(auction.date_created).split('T')[0]).toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
            }

            const payments = parsePaymentMethods(auction.payment_method);
            const paymentDisplay = formatPaymentDisplay(payments);

            auctionDiv.innerHTML = `
                <p class="auction-name">${DOMPurify.sanitize(auctionName)}</p>
                <p class="auction-price" data-field="auction_price">${auctionPrice != null ? DOMPurify.sanitize(auctionPrice) + '€' : ''}</p>
                <p class="buy-date">${DOMPurify.sanitize(formatedDate)}</p>
                <div class="payment-method-container">
                    <div class="payment-method">${paymentDisplay}</div>
                </div>
                <button class="view-auction" data-id="${safeAuctionId}">View</button>
                <div class="cards-container">
                    <!-- Cards will be loaded here -->
                </div>
            `;
            auctionContainer.appendChild(auctionDiv);
        });

        const viewButtons = document.querySelectorAll('.auction-container .view-auction');
        viewButtons.forEach(button => {
            button.addEventListener('click', () => loadAuctionContent(button));
        });

        const auctionsTabs = document.querySelectorAll('.auction-container .auction-tab');
        auctionsTabs.forEach(tab => {
            tab.addEventListener('click', async (event) => {
                if (event.target === tab) {
                    const viewButton = tab.querySelector('.view-auction');
                    if (viewButton) {
                        loadAuctionContent(viewButton);
                    }
                }
            });
        });
    } catch (error) {
        renderAlert('Error loading auctions: ' + error, 'error');
    }
}

async function initializeSealed() {
    const sealedContainer = document.querySelector('.sealed-container');
    const viewButton = sealedContainer.querySelector('.view-sealed');
    viewButton.addEventListener('click', () => {
        loadSealed(viewButton);
    });
}

async function loadSealed(viewButton) {
    const sealedTab = document.querySelector('.sealed-tab');
    const contentDiv = document.querySelector('.sealed-tab-content');
    if (sealedTab.hidden || sealedTab.childElementCount === 0) {
        sealedTab.hidden = false;
        viewButton.innerHTML = 'Hide';

        if (contentDiv.childElementCount === 0) {
            try {
                const response = await csrfFetch('/loadSealed');
                const data = await response.json();
                if (data.status != 'success') {
                    renderAlert('Failed to load sealed products', 'error');
                    return;
                }

                data.data.forEach((sealedData) => {
                    const sealedDiv = document.createElement('div');
                    sealedDiv.classList.add('sealed-item');
                    const margin = (Number(DOMPurify.sanitize(sealedData.market_value)) - Number(DOMPurify.sanitize(sealedData.price))).toFixed(2);
                    const formatedDate = formatSealedDate(sealedData.date);
                    sealedDiv.innerHTML = `
                        <p class='sealed-quantity'>${DOMPurify.sanitize(sealedData.quantity)}</p>
                        <p class='sealed-name'>${DOMPurify.sanitize(sealedData.name)}</p>
                        <p class='unit-price'>${DOMPurify.sanitize(sealedData.price)}</p>
                        <p class='VAT-sealed sealed-market-value'>${(DOMPurify.sanitize(sealedData.price) / 1.23).toFixed(2)}</p>
                        <p class='market-value-sealed'>${DOMPurify.sanitize(sealedData.market_value)}</p>
                        <p class='margin'>${margin}</p>
                        <p class='add-date'>${formatedDate}</p>
                        <p></p>
                        <p></p>
                        <p></p>
                    `;
                    contentDiv.append(sealedDiv);
                });
            } catch (e) {
                renderAlert('Error loading sealed: ' + e, 'error');
            }
        }
    } else {
        sealedTab.hidden = true;
        viewButton.innerHTML = 'View';
    }
}

uploadCSVModal();
soldReportBtn();
loadAuctions();
initializeSealed();
scrollOnLoad();
document.addEventListener('DOMContentLoaded', async () => {
    await updateInventoryValueAndTotalProfit();
}, false);
