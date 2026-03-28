class struct {
    constructor() {
        this.cardName = null;
        this.cardNum = null;
        this.condition = null;
        this.buyPrice = null;
        this.marketValue = null;
        this.sellPrice = null;
        this.soldDate = null;
    }
}

class queue {
    constructor(size) {
        this.items = [];
        this.size = size;
        this.curr = 0;
        this.next = 1;
        this.prev = size - 1;
    }
    moveNext() {
        this.prev = this.curr;
        this.curr = this.next;
        this.next = (this.next + 1) % this.size;
    }
    movePrev() {
        this.next = this.curr;
        this.curr = this.prev;
        this.prev = (this.prev - 1 + this.size) % this.size;
    }

    enqueue(item) {
        if (this.items.length < this.size) {
            this.items.push(item);
        } else {
            this.items[this.curr] = item;
        }
    }
    getCurrent() {
        return this.items[this.curr];
    }
    getItem() {
        return this.items[this.curr];
    }
    printQueue() {
        console.log(this.items);
    }
}

class CartLine {
    constructor(cardName, cardNum, condition, auctionName, marketValue, allIds) {
        this.cardName = cardName;
        this.cardNum = cardNum;
        this.condition = condition;
        this.auctionName = auctionName;
        this.marketValue = marketValue;
        this.cardIds = [allIds[0]];
        this.reservableIds = allIds.slice(1);
        this.element = null;
    }

    get quantity() { return this.cardIds.length; }
    get canIncrement() { return this.reservableIds.length > 0; }
    get canDecrement() { return this.cardIds.length > 0; }

    increment() {
        if (!this.canIncrement) { return null; }
        const id = this.reservableIds.shift();
        this.cardIds.push(id);
        return id;
    }

    decrement() {
        if (!this.canDecrement) { return null; }
        const id = this.cardIds.pop();
        this.reservableIds.unshift(id);
        return id;
    }

    removeAll() {
        return [...this.cardIds];
    }

    matches(cardName, cardNum, condition) {
        return this.cardName === cardName
            && this.cardNum === cardNum
            && this.condition === condition;
    }

    maxQuantity() {
        const quantity = this.cardIds.push(...this.reservableIds);
        this.reservableIds.length = 0;
        return quantity;
    }

    // For sessionStorage
    toJSON() {
        return {
            cardName: this.cardName,
            cardNum: this.cardNum,
            condition: this.condition,
            auctionName: this.auctionName,
            marketValue: this.marketValue,
            cardIds: this.cardIds,
            reservableIds: this.reservableIds
        };
    }

    // Restore from sessionStorage
    static fromJSON(data) {
        const line = new CartLine(
            data.cardName, data.cardNum, data.condition,
            data.auctionName, data.marketValue,
            [...data.cardIds, ...(data.reservableIds || [])]
        );
        // Override the constructor's default split
        line.cardIds = data.cardIds;
        line.reservableIds = data.reservableIds || [];
        return line;
    }

    // Expand for /invoice payload
    toInvoiceItems() {
        return this.cardIds.map(id => ({
            cardId: id,
            cardName: this.cardName,
            cardNum: this.cardNum,
            condition: this.condition,
            marketValue: this.marketValue
        }));
    }

    // Lazy backfill: fetch more IDs from server when reservableIds is empty
    async backfillPool(excludeIds) {
        if (this.reservableIds.length > 0) return;
        try {
            const response = await fetch('/getCardIds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    card_name: this.cardName,
                    card_num: this.cardNum,
                    condition: this.condition,
                    exclude_ids: [...excludeIds]
                })
            });
            if (!response.ok) {
                renderAlert('Failed to fetch card IDs: ' + response.status, 'error');
                return;
            }
            const data = await response.json();
            if (data.status === 'success' && data.card_ids) {
                this.reservableIds = data.card_ids.filter(id => !this.cardIds.includes(id));
            }
        } catch (e) {
            renderAlert('Error fetching card IDs: ' + e, 'error');
        }
    }
}


export function renderField(value, inputType, classList, placeholder, datafield) {
    const safeInputType = sanitizeAttrValue(inputType || 'text');
    const safeClassList = Array.isArray(classList)
        ? classList.map(token => sanitizeClassToken(token)).filter(Boolean).join(' ')
        : '';
    const safePlaceholder = sanitizeAttrValue(placeholder || '');
    const safeDataField = sanitizeAttrValue(datafield || '');

    if (value === null) {
        return `<input type="${safeInputType}" class="${safeClassList}" placeholder="${safePlaceholder}" data-field="${safeDataField}" autocomplete="off">`;
    } else {
        const safeValue = sanitizePlainText(value);
        return `<p class=" ${safeClassList}" data-field="${safeDataField}">${safeValue}</p>`;
    }
}

export function renderAlert(text, type) {
    const alertDiv = document.querySelector('#alert-div');

    if (type === 'error') {
        alertDiv.classList.add('alert-error')
    } else {
        alertDiv.classList.add('alert-message')
    }

    const escaped = String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/\r\n|\r|\n/g, '<br>');

    alertDiv.innerHTML = escaped;
    setTimeout(() => {
        alertDiv.innerHTML = '';
        alertDiv.classList.remove(...alertDiv.classList)
    }, 6000)
}

export function scrollOnLoad() {
    window.addEventListener('load', () => {
        const hash = window.location.hash;
        console.log(hash);
        const id = hash.startsWith('#') ? hash.slice(1) : hash;
        if (id) {
            const interval = setInterval(() => {
                const el = document.getElementById(id);
                if (el) {
                    el.scrollIntoView({ behavior: 'instant', block: 'center' });
                    clearInterval(interval);
                }
            }, 100);
        }
    })
}

function paymentTypeSelect(className, defaultValue = '') {
    return `
    <select class="${className}">
        <option value=' ' ${defaultValue === '' || defaultValue === ' ' ? 'selected' : ''}>Select payment method</option>
        <option value="Hotovosť" ${defaultValue === 'Hotovosť' ? 'selected' : ''}>Hotovosť</option>
        <option value="Karta" ${defaultValue === 'Karta' ? 'selected' : ''}>Karta</option>
        <option value="Barter" ${defaultValue === 'Barter' ? 'selected' : ''}>Barter</option>
        <option value="Bankový prevod" ${defaultValue === 'Bankový prevod' ? 'selected' : ''}>Bankový prevod</option>
        <option value="Online platba" ${defaultValue === 'Online platba' ? 'selected' : ''}>Online platba</option>
        <option value="Dobierka" ${defaultValue === 'Dobierka' ? 'selected' : ''}>Dobierka</option>
        <option value="Online platobný systém" ${defaultValue === 'Online platobný systém' ? 'selected' : ''}>Online platobný systém</option>
        </select>
    `
}

function paymentTypeRow(type = '', amount = 0, className = 'payment-row') {
    return `
    <div class="${className}">
        <select class="payment-type-select">
            <option value=''>Select payment method</option>
            <option value="Hotovosť" ${type === 'Hotovosť' ? 'selected' : ''}>Hotovosť</option>
            <option value="Karta" ${type === 'Karta' ? 'selected' : ''}>Karta</option>
            <option value="Barter" ${type === 'Barter' ? 'selected' : ''}>Barter</option>
            <option value="Bankový prevod" ${type === 'Bankový prevod' ? 'selected' : ''}>Bankový prevod</option>
            <option value="Online platba" ${type === 'Online platba' ? 'selected' : ''}>Online platba</option>
            <option value="Dobierka" ${type === 'Dobierka' ? 'selected' : ''}>Dobierka</option>
            <option value="Online platobný systém" ${type === 'Online platobný systém' ? 'selected' : ''}>Online platobný systém</option>
        </select>
        <input type="number" class="payment-amount-input" step="0.01" min="0" placeholder="Amount" value="${amount}" autocomplete="off">
        <button class="remove-payment-btn">×</button>
    </div>
    `
}

function parsePaymentMethods(paymentMethodData) {
    if (!paymentMethodData) return [];

    try {
        const parsed = JSON.parse(paymentMethodData);
        if (Array.isArray(parsed)) return parsed;
    } catch (e) {
        // Old format - space separated
        return paymentMethodData.trim().split(' ').map(type => ({ type: type, amount: 0 }));
    }

    return [];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sanitizePlainText(value) {
    return DOMPurify.sanitize(String(value ?? ''), { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
}

function sanitizeAttrValue(value) {
    return sanitizePlainText(value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function sanitizeClassToken(value) {
    return sanitizePlainText(value)
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_-]/g, '');
}

function sanitizeNumericId(value) {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) && parsed >= 0 ? String(parsed) : '';
}

const ALLOWED_PAYMENT_TYPES = new Set([
    'Hotovosť',
    'Karta',
    'Barter',
    'Bankový prevod',
    'Online platba',
    'Dobierka',
    'Online platobný systém'
]);

function validatePayments(payments) {
    if (!Array.isArray(payments) || payments.length === 0) {
        return { valid: false, error: 'At least one payment method required' };
    }

    if (payments.length > 10) {
        return { valid: false, error: 'Too many payment methods (max 10)' };
    }

    for (const payment of payments) {
        if (!payment.type || !ALLOWED_PAYMENT_TYPES.has(payment.type)) {
            return { valid: false, error: 'Invalid payment type selected' };
        }

        const amount = parseFloat(payment.amount);
        if (isNaN(amount) || amount < 0) {
            return { valid: false, error: 'Invalid payment amount' };
        }

        if (amount > 1000000) {
            return { valid: false, error: 'Payment amount too large' };
        }
    }

    return { valid: true };
}

function formatPaymentDisplay(payments) {
    if (!payments || payments.length === 0) return 'No payment method';

    // Escape HTML to prevent XSS, then join with <br>
    return payments.map(p => {
        const type = escapeHtml(p.type || '');
        const amount = parseFloat(p.amount || 0).toFixed(2);
        return `${type}: ${amount}€`;
    }).join('<br>');
}

async function updatePaymentMethod(auctionId, payments) {
    try {
        const response = await fetch(`/updatePaymentMethod/${auctionId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ payments: payments })
        })
        const data = await response.json();
        if (data.status === 'success') {
            return true;
        }
    }
    catch (error) {
        renderAlert('Error updating payment method: ' + error, 'error');
        return false;
    }
}

function calculateCardBuyPrice(cards) {
    let totalBuyPrice = 0;
    cards.forEach(card => {
        const buyPrice = Number(card.querySelector('.card-price').textContent.replace('€', '').trim());
        totalBuyPrice += buyPrice;
    });
    return totalBuyPrice.toFixed(2);
}

function calculateSealedBuyPrice(sealed) {
    let totalBuyPrice = 0;
    console.log(sealed);
    sealed.forEach(s => {
        const buyPrice = Number(s.price);
        totalBuyPrice += buyPrice;
    });
    return totalBuyPrice.toFixed(2);
}

function appendEuroSign(value, dataset) {
    if (dataset === 'card_num' || dataset === 'card_name') {
        return value;
    }
    if (isNaN(value)) {
        return value;
    } else {
        return value + '€';
    }
}

export function replaceWithPElement(dataset, value, element) {
    if (dataset === undefined) {
        return;
    }
    if (value === null) {
        const p = document.createElement('p');
        p.dataset.field = dataset;
        p.classList.add('card-info', dataset.replace('_', '-'));
        element.replaceWith(p);
        return
    }
    const p = document.createElement('p');
    p.dataset.field = dataset;
    p.classList.add('card-info', dataset.replace('_', '-'));
    p.textContent = appendEuroSign(value, dataset);
    element.replaceWith(p);
}

function getInputValueAndPatch(value, element, dataset, cardId) {
    if (!Boolean(value)) {
        return null;
    }
    replaceWithPElement(dataset, value, element);
    patchValue(cardId, value, dataset);
}


async function updateSoldStatus(cardId, isChecked, field) {
    try {
        const response = await fetch(`/update/${cardId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ field: field, value: isChecked })
        });
        const data = await response.json();
        if (!(data.status === 'success')) {
            renderAlert('Error updating sold status: ' + JSON.stringify(data), 'error');
            return;
        } else {
            return
        }
    } catch (e) {
        renderAlert('Error updating sold status: ' + e, 'error');
        return;
    }
}

//These two are the same

async function patchValue(id, value, dataset) {
    if (value === " ") {
        value = null;
    }
    if (!value === null || !value === undefined) {
        value = String(value);
        value = value.replace('€', '');

    }
    try {
        const response = await fetch(`/update/${id}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ field: dataset, value: value })
        });
        const data = await response.json();
        if (!(data.status === 'success')) {
            renderAlert('Failed to update: ' + dataset, 'error');
            return;
        } else {
            return
        }
    } catch (e) {
        renderAlert('Error updating value: ' + e, 'error');
    }
}

function deleteAuction(id, div) {
    fetch(`/deleteAuction/${id}`, {
        method: 'DELETE',
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                div.remove();
            } else {
                renderAlert('Error deleting auction: ' + JSON.stringify(data), 'error');
            }
        })
        .catch(error => {
            renderAlert('Error deleting auction: ' + error, 'error');
        });
}



async function setAuctionBuyPrice(cards, sealed, auctionTab) {
    const auctionBuyPriceElement = auctionTab.querySelector('.auction-price');
    const cardBuyPrice = calculateCardBuyPrice(cards);
    const sealedCardPrice = calculateSealedBuyPrice(sealed);
    const newAuctionBuyPrice = Number(cardBuyPrice) + Number(sealedCardPrice);
    auctionBuyPriceElement.textContent = appendEuroSign(newAuctionBuyPrice, 'auction-price');
    const auctionId = auctionTab.getAttribute('data-id');
    await updateAuction(auctionId, newAuctionBuyPrice, 'auction_price');
}




async function removeCard(id, div) {
    try {
        const response = await fetch(`/deleteCard/${id}`, {
            method: 'DELETE',
        });
        const data = await response.json();

        if (data.status === 'success') {
            div.remove();
            return true;
        } else {
            renderAlert('Error deleting card: ' + JSON.stringify(data), 'error');
            return false;
        }
    } catch (error) {
        renderAlert('Error deleting card: ' + error, 'error');
        return false;
    }
}

async function removeBulkItem(bulkId, bulkDiv) {
    try {
        const response = await fetch(`/deleteBulkItem/${bulkId}`, {
            method: 'DELETE',
        });
        const data = await response.json();
        if (data.status === 'success') {
            bulkDiv.remove();
            return true;
        } else {
            renderAlert('Error deleting bulk item: ' + JSON.stringify(data), 'error');
            return false;
        }
    } catch (error) {
        renderAlert('Error deleting bulk item: ' + error, 'error');
        return false;
    }
}

async function updateAuction(auctionId, value, field) {
    try {
        const response = await fetch(`/updateAuction/${auctionId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ field: field, value: value })
        });
        const data = await response.json();
        if (!(data.status === 'success')) {
            renderAlert('Error updating auction: ' + JSON.stringify(data), 'error');
            return;
        } else {
            return
        }
    } catch (error) {
        renderAlert('Error updating auction: ' + error, 'error');
        return
    }
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
    const response = await fetch(`/generateSoldReport?month=${month}&year=${year}`);
    const data = await response.json();
    if (data.status === 'success') {
        console.log('Sold report generated successfully');
        div.remove();
        renderAlert(`Sold report:\n${data.pdf_path}\n Buy report:\n${data.xls_path}`, 'message');
        // Handle successful report generation (e.g., display a success message)
    } else {
        // Handle errors (e.g., display an error message)
        renderAlert(`Error generating sold report: ${data.message}`, 'error');
    }
}

function importCSV() {
    const input = document.querySelector('.import-sold-csv');
    input.style.opacity = 0;
    input.addEventListener('change', async (event) => {
        const file = event.target.files;
        if (file && file.length === 1) {
            const formData = new FormData();
            formData.append("csv-upload", file[0]);
            const response = await fetch('/importSoldCSV', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            switch (data.status) {
                case "success":
                    window.location.reload()
                    break;
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
            }
        }
    })
}

async function getInventoryValue() {
    try {
        const response = await fetch('/inventoryValue');
        const data = await response.json();
        return data.value;
    } catch (e) {
        renderAlert('Error loading inventory value: ' + e, 'error');
    }
}



export async function updateInventoryValueAndTotalProfit() {
    const value = await getInventoryValue();
    const inventoryValueElement = document.querySelector('.inventory-value-value');
    if (value != null) {
        inventoryValueElement.textContent = appendEuroSign(value.toFixed(2));
    } else {
        inventoryValueElement.textContent = '0.00 €';
    }
}

function cartValue(cartContent) {
    let sum = 0.0;
    if (cartContent.cards) {
        cartContent.cards.forEach(card => {
            if (card.marketValue) {
                sum += Number(card.marketValue);
            }
        });
    }

    if (cartContent.sealed) {
        cartContent.sealed.forEach(item => {
            sum += Number(item.marketValue);
        })
    };


    if (cartContent.bulkItem) {
        sum += Number(cartContent.bulkItem.sell_price);
    }

    if (cartContent.holoItem) {
        sum += Number(cartContent.holoItem.sell_price);
    }

    if (cartContent.exItem) {
        sum += Number(cartContent.exItem.sell_price);
    }
    return sum.toFixed(2);
}

async function changeCardPricesBasedOnAuctionPrice(auctionTab) {
    const auctionId = auctionTab.getAttribute('data-id');
    let auctionPrice = auctionTab.querySelector('.auction-price').textContent.replace('€', '');
    const response = await fetch(`/recalculateCardPrices/${auctionId}/${auctionPrice}`, { method: 'GET' });
    const data = await response.json();
    if (data.status == 'success') {
        window.location.reload();
    } else if (data.status == 'error') {
        renderAlert('Error recalculating card prices: ' + data.message, 'error');
    } else if (data.status == 'no_cards') {
        renderAlert('No cards found in this auction to recalculate prices.', 'message');
    }

}

const existingIDs = new Set();
const cartLines = [];

function rebuildExistingIDs() {
    existingIDs.clear();
    cartLines.forEach(line => {
        line.cardIds.forEach(id => existingIDs.add(id));
    });
}

function renderCartLine(line) {
    const contentDiv = document.querySelector('.cart-content');
    if (contentDiv.childElementCount === 1 && contentDiv.children[0].tagName === 'P') {
        contentDiv.innerHTML = '';
    }

    const cardDiv = document.createElement('div');
    cardDiv.classList.add('cart-line');
    line.element = cardDiv;

    const updateDisplay = () => {
        const minusDisabled = line.cardIds.length <= 1 ? 'disabled' : '';
        const plusDisabled = !line.canIncrement ? 'disabled' : '';
        cardDiv.innerHTML = `
            <p class="cart-card-name">${DOMPurify.sanitize(line.cardName)}</p>
            <p class="cart-card-num">${DOMPurify.sanitize(line.cardNum)}</p>
            <p class="cart-condition">${DOMPurify.sanitize(line.condition)}</p>
            <p class='market-value-invoice'>${DOMPurify.sanitize(line.marketValue)}€</p>
            <div class="qty-controls">
                <button class="qty-minus" ${minusDisabled}>-</button>
                <span class="qty-display">${DOMPurify.sanitize(line.quantity)}</span>
                <button class="qty-plus" ${plusDisabled}>+</button>
            </div>
            <button class='remove-from-cart'>Remove</button>
        `;
        attachCartLineListeners(cardDiv, line, updateDisplay);
    };

    updateDisplay();
    contentDiv.appendChild(cardDiv);
    contentDiv.scrollTop = contentDiv.scrollHeight;
    contentDiv.appendChild(cardDiv);
    saveCartContentToSession();
}

function attachCartLineListeners(cardDiv, line, updateDisplay) {
    // Market value double-click editing
    const marketValueEl = cardDiv.querySelector('.market-value-invoice');
    marketValueEl.addEventListener('dblclick', () => {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = String(line.marketValue).replace('€', '');
        marketValueEl.replaceWith(input);
        input.focus();
        input.addEventListener('blur', () => {
            let newValue = input.value.replace(',', '.');
            if (isNaN(newValue) || newValue.trim() === '') {
                newValue = line.marketValue;
            }
            line.marketValue = newValue;
            updateDisplay();
            saveCartContentToSession();
        });
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') input.blur();
        });
    });

    // Minus button
    const minusBtn = cardDiv.querySelector('.qty-minus');
    minusBtn.addEventListener('click', () => {
        if (line.cardIds.length <= 1) {
            // Remove entire line
            const removedIds = line.removeAll();
            removedIds.forEach(id => existingIDs.delete(id));
            const idx = cartLines.indexOf(line);
            if (idx !== -1) cartLines.splice(idx, 1);
            cardDiv.remove();
            const contentDiv = document.querySelector('.cart-content');
            if (contentDiv.childElementCount === 0) {
                contentDiv.innerHTML = '<p>Your cart is empty</p>';
            }
            saveCartContentToSession();
            return;
        }
        const id = line.decrement();
        if (id !== null) {
            existingIDs.delete(id);
            updateDisplay();
            saveCartContentToSession();
        }
    });

    // Plus button
    const plusBtn = cardDiv.querySelector('.qty-plus');
    plusBtn.addEventListener('click', async () => {
        if (!line.canIncrement) {
            await line.backfillPool(existingIDs);
        }
        if (line.canIncrement) {
            const id = line.increment();
            if (id !== null) {
                existingIDs.add(id);
                updateDisplay();
                saveCartContentToSession();
            }
        }
    });

    // Remove button
    const removeBtn = cardDiv.querySelector('.remove-from-cart');
    removeBtn.addEventListener('click', () => {
        const removedIds = line.removeAll();
        removedIds.forEach(id => existingIDs.delete(id));
        const idx = cartLines.indexOf(line);
        if (idx !== -1) cartLines.splice(idx, 1);
        cardDiv.remove();
        const contentDiv = document.querySelector('.cart-content');
        if (contentDiv.childElementCount === 0) {
            contentDiv.innerHTML = '<p>Your cart is empty</p>';
        }
        saveCartContentToSession();
    });
}

function saveCartContentToSession() {
    const sealedEl = document.querySelector('.sealed-content').children;
    const bulkEl = document.querySelector('.bulk-cart-content');
    const holoEl = document.querySelector('.holo-cart-content');
    const exEl = document.querySelector('.ex-cart-content');

    // Persist cartLines via toJSON
    let cartLinesData = cartLines.map(line => line.toJSON());

    let sealedData = [];
    if (sealedEl.length > 0) {
        for (const item of sealedEl) {
            const sealed = {
                sid: item.getAttribute('sid'),
                auctionId: item.getAttribute('auction_id'),
                name: item.querySelector('.sealed-name').textContent,
                price: item.querySelector('.sealed-price').textContent
            }
            sealedData.push(sealed);
        }
    }
    let bulkData = {}
    if (bulkEl.children.length > 0) {
        bulkData = {
            type: 'bulk',
            quantity: bulkEl.querySelector('.bulk-quantity').textContent.replace('q: ', ''),
            price: bulkEl.querySelector('.bulk-sell-price').value || ''
        }
    }

    let holoData = {}
    if (holoEl.children.length > 0) {
        holoData = {
            type: 'holo',
            quantity: holoEl.querySelector('.holo-quantity').textContent.replace('q: ', ''),
            price: holoEl.querySelector('.holo-sell-price').value || ''
        }
    }

    let exData = {}
    if (exEl.children.length > 0) {
        exData = {
            type: 'ex',
            quantity: exEl.querySelector('.ex-quantity').textContent.replace('q: ', ''),
            price: exEl.querySelector('.ex-sell-price').value || ''
        }
    }

    const cartData = {
        cartLines: cartLinesData,
        sealed: sealedData,
        bulk: bulkData,
        holo: holoData,
        ex: exData
    };

    sessionStorage.setItem('cartData', JSON.stringify(cartData));
}

function loadCartContentFromSession() {
    const savedData = sessionStorage.getItem('cartData');
    if (!savedData) return;

    try {
        const cartData = JSON.parse(savedData);

        // Clear cartLines and existingIDs - we'll rebuild from saved data
        cartLines.length = 0;
        existingIDs.clear();

        // Restore cart lines
        if (cartData.cartLines && cartData.cartLines.length > 0) {
            cartData.cartLines.forEach(data => {
                const line = CartLine.fromJSON(data);
                cartLines.push(line);
                renderCartLine(line);
            });
            rebuildExistingIDs();
        }

        // Restore sealed items
        if (cartData.sealed && cartData.sealed.length > 0) {
            const sealedContent = document.querySelector('.sealed-content');

            cartData.sealed.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.classList.add('sealed-item-cart');
                itemDiv.setAttribute('sid', item.sid);
                if (item.auctionId) {
                    itemDiv.setAttribute('auction_id', item.auctionId);
                }

                // Add ID to existingIDs Set
                if (item.sid) {
                    existingIDs.add(item.sid);
                }

                itemDiv.innerHTML = `
                    <p class='sealed-name'>${DOMPurify.sanitize(item.name)}</p>
                    <p class='sealed-price'>${DOMPurify.sanitize(item.price)}</p>
                    <button class='remove-from-cart'>Remove</button>
                `;

                const removeFromCart = itemDiv.querySelector('.remove-from-cart');
                removeFromCart.addEventListener('click', () => {
                    const sid = itemDiv.getAttribute('sid');
                    if (sid) {
                        existingIDs.delete(sid);
                    }
                    itemDiv.remove();
                    saveCartContentToSession();
                });

                sealedContent.appendChild(itemDiv);
            });
        }

        // Restore bulk items
        if (cartData.bulk && !isEmpty(cartData.bulk)) {
            const bulkCartDiv = document.querySelector('.bulk-cart-content');
            const div = document.createElement('div');
            div.classList.add('bulk-cart-item-bulk');
            div.innerHTML = `
                <p>Bulk</p>
                <p class='bulk-quantity'>q: ${DOMPurify.sanitize(cartData.bulk.quantity)}</p>
                <input type='text' class='bulk-sell-price' style='width:70px' value='${DOMPurify.sanitize(cartData.bulk.price)}'>
                <button class='remove-from-cart'>Remove</button>
            `;
            bulkCartDiv.appendChild(div);

            const sellPriceInput = div.querySelector('.bulk-sell-price');
            sellPriceInput.addEventListener('blur', saveCartContentToSession);

            const removeButton = div.querySelector('.remove-from-cart');
            removeButton.addEventListener('click', () => {
                bulkCartDiv.innerHTML = '';
                saveCartContentToSession();
            });
        }

        // Restore holo items
        if (cartData.holo && !isEmpty(cartData.holo)) {
            const holoCartDiv = document.querySelector('.holo-cart-content');
            const div = document.createElement('div');
            div.classList.add('holo-cart-item-holo');
            div.innerHTML = `
                <p>Holo</p>
                <p class='holo-quantity'>q: ${DOMPurify.sanitize(cartData.holo.quantity)}</p>
                <input type='text' class='holo-sell-price' style='width:70px' value='${DOMPurify.sanitize(cartData.holo.price)}'>
                <button class='remove-from-cart'>Remove</button>
            `;
            holoCartDiv.appendChild(div);

            const sellPriceInput = div.querySelector('.holo-sell-price');
            sellPriceInput.addEventListener('blur', saveCartContentToSession);

            const removeButton = div.querySelector('.remove-from-cart');
            removeButton.addEventListener('click', () => {
                holoCartDiv.innerHTML = '';
                saveCartContentToSession();
            });
        }

        // Restore ex items
        if (cartData.ex && !isEmpty(cartData.ex)) {
            const exCartDiv = document.querySelector('.ex-cart-content');
            const div = document.createElement('div');
            div.classList.add('ex-cart-item-ex');
            div.innerHTML = `
                <p>Ex</p>
                <p class='ex-quantity'>q: ${DOMPurify.sanitize(cartData.ex.quantity)}</p>
                <input type='text' class='ex-sell-price' style='width:70px' value='${DOMPurify.sanitize(cartData.ex.price)}'>
                <button class='remove-from-cart'>Remove</button>
            `;
            exCartDiv.appendChild(div);

            const sellPriceInput = div.querySelector('.ex-sell-price');
            sellPriceInput.addEventListener('blur', saveCartContentToSession);

            const removeButton = div.querySelector('.remove-from-cart');
            removeButton.addEventListener('click', () => {
                exCartDiv.innerHTML = '';
                saveCartContentToSession();
            });
        }

    } catch (e) {
        renderAlert('Error loading cart data from sessionStorage: ' + e, 'error');
    }
}

function removeCartContentFromSession() {
    sessionStorage.removeItem('cartData');
}

// SessionStorage helper functions for modal persistence
function saveModalDataToSession() {
    const modalData = {
        clientName: document.querySelector('.client-name')?.value || '',
        clientAddress: document.querySelector('.client-address')?.value || '',
        clientCity: document.querySelector('.client-city')?.value || '',
        clientCountry: document.querySelector('.client-country')?.value || '',
        paybackDate: document.querySelector('.date-input')?.value || '',
        price: document.querySelector('.price-input')?.value || '',
        shippingPrice: document.querySelector('.shipping-price')?.value || '',
        paymentMethods: []
    };

    // Collect all payment methods
    const paymentDivs = document.querySelectorAll('.payment-div');
    paymentDivs.forEach(div => {
        const paymentType = div.querySelector('.payment-type')?.value || '';
        const amount = div.querySelector('.amount, .amunt')?.value || '';
        modalData.paymentMethods.push({ type: paymentType, amount: amount });
    });

    sessionStorage.setItem('invoiceModalData', JSON.stringify(modalData));
}

function loadModalDataFromSession(recieverDiv) {
    const savedData = sessionStorage.getItem('invoiceModalData');
    if (!savedData) return;

    try {
        const modalData = JSON.parse(savedData);

        // Restore simple fields
        const clientName = recieverDiv.querySelector('.client-name');
        const clientAddress = recieverDiv.querySelector('.client-address');
        const clientCity = recieverDiv.querySelector('.client-city');
        const clientCountry = recieverDiv.querySelector('.client-country');
        const paybackDate = recieverDiv.querySelector('.date-input');
        const priceInput = recieverDiv.querySelector('.price-input');
        const shippingPrice = recieverDiv.querySelector('.shipping-price');

        if (clientName) clientName.value = DOMPurify.sanitize(modalData.clientName);
        if (clientAddress) clientAddress.value = DOMPurify.sanitize(modalData.clientAddress);
        if (clientCity) clientCity.value = DOMPurify.sanitize(modalData.clientCity);
        if (clientCountry) clientCountry.value = DOMPurify.sanitize(modalData.clientCountry);
        if (paybackDate && modalData.paybackDate) paybackDate.value = DOMPurify.sanitize(modalData.paybackDate);
        if (priceInput) priceInput.value = DOMPurify.sanitize(modalData.price);
        if (shippingPrice) shippingPrice.value = DOMPurify.sanitize(modalData.shippingPrice);

        // Restore payment methods
        if (modalData.paymentMethods && modalData.paymentMethods.length > 0) {
            const paymentContainer = recieverDiv.querySelector('.payment-container');
            const firstPaymentDiv = paymentContainer.querySelector('.payment-div');

            // Set first payment method (already exists in HTML)
            if (firstPaymentDiv && modalData.paymentMethods[0]) {
                const firstSelect = firstPaymentDiv.querySelector('.payment-type');
                const firstAmount = firstPaymentDiv.querySelector('.amount');
                if (firstSelect) firstSelect.value = modalData.paymentMethods[0].type;
                if (firstAmount) firstAmount.value = DOMPurify.sanitize(modalData.paymentMethods[0].amount);
            }

            // Add additional payment methods (if any)
            for (let i = 1; i < modalData.paymentMethods.length; i++) {
                const newSelectDiv = document.createElement('div');
                newSelectDiv.classList.add('payment-div');
                newSelectDiv.innerHTML = `
                    ${paymentTypeSelect('payment-type')}
                    <input type='number' class='amount' value='${DOMPurify.sanitize(modalData.paymentMethods[i].amount)}'></input>
                `;

                // Set the payment type after adding to DOM
                paymentContainer.append(newSelectDiv);
                const select = newSelectDiv.querySelector('.payment-type');
                if (select) select.value = DOMPurify.sanitize(modalData.paymentMethods[i].type);

                // Add event listeners to restored inputs
                const newInputs = newSelectDiv.querySelectorAll('input, select');
                newInputs.forEach(input => {
                    input.addEventListener('input', saveModalDataToSession);
                    input.addEventListener('change', saveModalDataToSession);
                });
            }
        }
    } catch (e) {
        renderAlert('Error loading modal data from sessionStorage: ' + e, 'error');
    }
}

function clearModalDataFromSession() {
    sessionStorage.removeItem('invoiceModalData');
}

function deleteCartContent(contentDiv, bulkCartContent, holoCartContent, exCartContent, sealedContent, recieverDiv = null) {
    contentDiv.innerHTML = '<p>Your cart is empty</p>';
    bulkCartContent.innerHTML = '';
    holoCartContent.innerHTML = '';
    exCartContent.innerHTML = '';
    sealedContent.innerHTML = '';
    loadBulkHoloValues();
    cartLines.length = 0;
    existingIDs.clear();
    if (recieverDiv != null) {
        recieverDiv.remove();
        recieverDiv = null;
    }
}

function initializeCart() {
    shoppingCart();
    addBulkToCart();
    addHoloToCart();
    addExToCart();
}

function shoppingCart() {
    const contentDiv = document.querySelector(".cart-content");
    const bulkCartDiv = document.querySelector(".bulk-cart-content");
    const holoCartDiv = document.querySelector(".holo-cart-content");
    const exCartDiv = document.querySelector(".ex-cart-content");
    const sealedContent = document.querySelector('.sealed-content');

    if (contentDiv.childElementCount === 0) {
        contentDiv.innerHTML = '<p>Your cart is empty</p>';
    }
    const cartDiv = document.querySelector(".shopping-cart");
    if (cartDiv) {
        cartDiv.addEventListener('click', (e) => {
            if (e.target === cartDiv) {
                cartDiv.classList.toggle('expanded');
            }
        });
    }

    const deleteCart = document.querySelector('.delete-cart');
    if (deleteCart) {
        let confirmResetTimeout = null;
        deleteCart.addEventListener('click', () => {
            const isConfirmState = deleteCart.dataset.confirmState === 'true';

            if (!isConfirmState) {
                deleteCart.textContent = 'Confirm';
                deleteCart.dataset.confirmState = 'true';
                if (confirmResetTimeout) {
                    clearTimeout(confirmResetTimeout);
                }
                confirmResetTimeout = setTimeout(() => {
                    deleteCart.textContent = 'Delete Cart';
                    deleteCart.dataset.confirmState = 'false';
                    confirmResetTimeout = null;
                }, 3000);
                return;
            }

            if (confirmResetTimeout) {
                clearTimeout(confirmResetTimeout);
                confirmResetTimeout = null;
            }
            sessionStorage.removeItem('invoiceModalData');
            sessionStorage.removeItem('cartData');
            deleteCartContent(contentDiv, bulkCartDiv, holoCartDiv, exCartDiv, sealedContent);
            deleteCart.textContent = 'Delete Cart';
            deleteCart.dataset.confirmState = 'false';
        });
    }


    const confirmButton = document.querySelector(".confirm-btn");
    confirmButton.addEventListener('click', async () => {
        const cartContent = {};
        if (contentDiv.childElementCount === 1 && contentDiv.children[0].tagName === 'P' && bulkCartDiv.childElementCount === 0 && holoCartDiv.childElementCount === 0 && exCartDiv.childElementCount === 0 && sealedContent.childElementCount === 0) {
            console.log("cart empty");
            return;
        }
        let recieverDiv = document.querySelector('.reciever-div');
        if (recieverDiv) {
            return
        }
        // Expand cartLines into flat cards array for invoice
        let cards = [];
        cartLines.forEach(line => {
            cards.push(...line.toInvoiceItems());
        });
        cartContent.cards = cards;

        const sealedItem = sealedContent.querySelectorAll(".sealed-item-cart");
        if (sealedItem) {
            let sealed = [];
            sealedItem.forEach(item => {
                const sid = item.getAttribute('sid');
                const auctionId = item.getAttribute('auction_id') || null;

                const paragraphs = item.querySelectorAll('p');

                const sealedData = {
                    sid: sid,
                    auctionId: auctionId,
                    sealedName: paragraphs[0]?.textContent || '',
                    marketValue: paragraphs[1]?.textContent.replace('€', '').replace(',', '.').trim() || ''
                };
                sealed.push(sealedData);
            });
            cartContent.sealed = sealed;
        }

        const bulkCartContent = document.querySelector(".bulk-cart-content");
        const bulkItems = bulkCartContent.querySelector('.bulk-cart-item-bulk');
        const holoCartContent = document.querySelector(".holo-cart-content");
        const holoItems = holoCartContent.querySelector('.holo-cart-item-holo');
        const exCartContent = document.querySelector(".ex-cart-content");
        const exItems = exCartContent.querySelector('.ex-cart-item-ex');
        if (bulkItems) {
            let bulkQuantity = Number(bulkItems.querySelectorAll('p')[1].textContent.replace('q: ', ''));
            if (bulkQuantity === 0) {
                bulkQuantity = 1
            }

            //this is bad I need to think about this shit cause no way this is correct

            const sellPriceInput = bulkItems.querySelector('.bulk-sell-price').value.replace(',', '.');
            const bulk = {
                counter_name: 'bulk',
                quantity: bulkQuantity,
                unit_price: sellPriceInput && bulkQuantity ? (Number(sellPriceInput) / bulkQuantity).toFixed(2) : 0.01,
                sell_price: sellPriceInput ? Number(sellPriceInput) : 0.01,
                buy_price: 0.01
            };
            cartContent.bulkItem = bulk;
        }

        if (holoItems) {
            let holoQuantity = Number(holoItems.querySelectorAll('p')[1].textContent.replace('q: ', ''));
            holoQuantity = holoQuantity === 0 ? 1 : holoQuantity;
            const sellPriceInput = holoItems.querySelector('.holo-sell-price').value.replace(',', '.');
            const holo = {
                counter_name: 'holo',
                quantity: holoQuantity,
                unit_price: sellPriceInput && holoQuantity ? (Number(sellPriceInput) / holoQuantity).toFixed(2) : 0.03,
                sell_price: sellPriceInput ? Number(sellPriceInput) : 0.03,
                buy_price: 0.03
            };
            cartContent.holoItem = holo;
        }

        if (exItems) {
            let exQuantity = Number(exItems.querySelectorAll('p')[1].textContent.replace('q: ', ''));
            exQuantity = exQuantity === 0 ? 1 : exQuantity;
            const sellPriceInput = exItems.querySelector('.ex-sell-price').value.replace(',', '.');
            const ex = {
                counter_name: 'ex',
                quantity: exQuantity,
                unit_price: sellPriceInput && exQuantity ? (Number(sellPriceInput) / exQuantity).toFixed(2) : 0.15,
                sell_price: sellPriceInput ? Number(sellPriceInput) : 0.15,
                buy_price: 0.15
            };
            cartContent.exItem = ex;
        }


        const cartVal = Number(cartValue(cartContent));

        if (!recieverDiv && Object.keys(cartContent).length != 0) {
            const body = document.querySelector('body');
            recieverDiv = document.createElement('div');
            recieverDiv.classList.add('reciever-div');
            recieverDiv.innerHTML = `
                <div class="modal-content">
                    <span class="close-modal">&times;</span>
                    <div class='complete-invoice-info'>
                        <p>Forma uhrady</p>
                        <div class='payment-container'>
                            <div class='payment-div'>
                                ${paymentTypeSelect('payment-type', 'Bankový prevod')}
                                <input type='number' class='amount'></input>
                            </div>
                        </div>
                        <button class='add-another-payment-method'>Add another payment method</button>
                    </div>
                    <div>
                        <p>Client name and surname</p>
                        <input type='text' class='client-name'>
                    </div>
                    <div>
                        <p>Address</p>
                        <input type='text' class='client-address'>
                    </div>
                    <div>
                        <p>City</p>
                        <input type='text' class='client-city'>
                    <div>
                    <div>
                        <p>Country</p>
                        <input type='text' class='client-country'>
                    </div>
                    <div>
                        <p>Payback date</p>
                        <input type='date' class='date-input'>
                    </div>
                    <div>
                        <p>Price</p>
                        <input type=text placeholder="${cartVal}" class="price-input">
                    </div>
                    <div>
                    <p>Shipping</p>
                    <p class='shipping-way'>Doprava / Poštovné – samostatná služba</p>
                    <input type=text placeholder="Price of shipping" class="shipping-price">
                    </div>
                    <button class="generate-invoice">Confirm</button>
                </div>
                `;
            body.append(recieverDiv);

            // Load saved data from sessionStorage if exists
            loadModalDataFromSession(recieverDiv);

            // Add event listeners to save data on input
            const modalInputs = recieverDiv.querySelectorAll('input, select');
            modalInputs.forEach(input => {
                input.addEventListener('input', saveModalDataToSession);
                input.addEventListener('change', saveModalDataToSession);
            });

            const closeModal = recieverDiv.querySelector('.close-modal');
            closeModal.addEventListener('click', () => {
                recieverDiv.remove();
                recieverDiv = null;
            });

            const button = document.querySelector('.add-another-payment-method');
            button.addEventListener('click', () => {
                const paymentContainer = document.querySelector('.payment-container');
                const newSelectDiv = document.createElement('div');
                newSelectDiv.classList.add('payment-div');
                newSelectDiv.innerHTML = `
                ${paymentTypeSelect('payment-type')}
                <input type='number' class='amount'></input>                            
                `;
                paymentContainer.append(newSelectDiv);

                // Add event listeners to new inputs for sessionStorage
                const newInputs = newSelectDiv.querySelectorAll('input, select');
                newInputs.forEach(input => {
                    input.addEventListener('input', saveModalDataToSession);
                    input.addEventListener('change', saveModalDataToSession);
                });
            });

            const dateInput = document.querySelector('.date-input');
            dateInput.value = new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        }

        const generateInvoiceBtn = document.querySelector('.generate-invoice');
        {
            generateInvoiceBtn.addEventListener('click', async () => {

                // Collect all payment methods (every time Confirm is clicked)
                const paymentDivs = recieverDiv.querySelectorAll('.payment-div');
                const paymentMethods = [];
                paymentDivs.forEach(div => {
                    const paymentType = div.querySelector('.payment-type')?.value;
                    if (!paymentType || paymentType === '' || paymentType === ' ') {
                        return;
                    }
                    const payment = {
                        type: paymentType,
                        amount: parseFloat(div.querySelector('.amount')?.value.replace(',', '.')) || 0
                    };
                    paymentMethods.push(payment);
                })

                // Get values by specific class names (every time)
                const clientName = DOMPurify.sanitize(recieverDiv.querySelector('.client-name')?.value) || '';
                const clientAddress = DOMPurify.sanitize(recieverDiv.querySelector('.client-address')?.value) || '';
                const clientCity = DOMPurify.sanitize(recieverDiv.querySelector('.client-city')?.value) || '';
                const clientCountry = DOMPurify.sanitize(recieverDiv.querySelector('.client-country')?.value) || '';
                const paybackDate = DOMPurify.sanitize(recieverDiv.querySelector('.date-input')?.value) || '';
                const shippingWay = 'Doprava / Poštovné – samostatná služba';
                const shippingPrice = DOMPurify.sanitize(recieverDiv.querySelector('.shipping-price')?.value.replace(',', '.')) || '';

                // Calculate total payment amount from payment methods
                const paymentTotal = paymentMethods.reduce((sum, payment) => sum + payment.amount, 0);
                const cartValueInput = DOMPurify.sanitize(document.querySelector('.price-input').value.replace(',', '.')) || cartVal;
                const expectedTotal = parseFloat(cartValueInput) + Number(shippingPrice);

                // Validate payment amounts match cart total
                if (paymentMethods.length > 1) {
                    // If multiple payment methods, check that sum matches total
                    if (Math.abs(paymentTotal - expectedTotal) > 0.01) { // Allow 1 cent tolerance for rounding
                        renderAlert(`Payment amount (${paymentTotal.toFixed(2)}€) is not equal to total cart value (${expectedTotal.toFixed(2)}€)`, 'error');
                        return;
                    }
                } else if (paymentMethods.length === 1) {
                    // If single payment method, auto-set amount to cart total
                    paymentMethods[0].amount = expectedTotal;
                } else {
                    renderAlert('Please select at least one payment method', 'error');
                    return;
                }
                cartContent.paymentMethods = paymentMethods;
                // Update or create recieverInfo (always update payment methods)
                const recieverInfo = {
                    nameAndSurname: clientName,
                    address: clientAddress,
                    city: clientCity,
                    state: clientCountry,
                    paybackDate: paybackDate,
                    total: null,
                };
                cartContent.recieverInfo = recieverInfo;

                if (shippingPrice !== "") {
                    const shipping = {
                        shippingWay: shippingWay,
                        shippingPrice: shippingPrice.replace(',', '.'),
                    };
                    cartContent.shipping = shipping;
                }

                // Apply price adjustment if cart value was manually changed
                if (cartValueInput != cartVal) {
                    const bulkSub = cartContent.bulkItem ? Number(cartContent.bulkItem.sell_price) : 0;
                    const holoSub = cartContent.holoItem ? Number(cartContent.holoItem.sell_price) : 0;
                    const exSub = cartContent.exItem ? Number(cartContent.exItem.sell_price) : 0;
                    const fixedSubtotal = bulkSub + holoSub + exSub;
                    const cardsSub = cartContent.cards ? cartContent.cards.reduce((sum, c) => sum + Number(c.marketValue), 0) : 0;
                    const sealedSub = cartContent.sealed ? cartContent.sealed.reduce((sum, c) => sum + Number(c.marketValue.replace('€', '')), 0) : 0;

                    const adjustableSubtotal = cardsSub + sealedSub;
                    const targetAdjustable = cartValueInput - fixedSubtotal;

                    if (adjustableSubtotal > 0) {
                        const scale = targetAdjustable / adjustableSubtotal;
                        const allItems = [...(cartContent.cards || 0), ...(cartContent.sealed || 0)];

                        let distributed = 0;
                        for (let i = 0; i < allItems.length; i++) {
                            if (i === allItems.length - 1) {
                                allItems[i].marketValue = (targetAdjustable - distributed).toFixed(2);
                            } else {
                                const scaled = parseFloat((allItems[i].marketValue * scale).toFixed(2));
                                allItems[i].marketValue = scaled.toFixed(2);
                                distributed += scaled;
                            }
                        }
                    }
                }
                cartContent.recieverInfo.total = Number(cartValue(cartContent));
                if (Object.keys(cartContent).length !== 0) {
                    const response = await fetch(`/invoice`,
                        {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(cartContent),
                        });
                    const data = await response.json();
                    if (data.status === 'success') {
                        cards = [];
                        for (const key in cartContent) {
                            delete cartContent[key];
                        }
                        deleteCartContent(contentDiv, bulkCartContent, holoCartContent, exCartContent, sealedContent, recieverDiv)
                        loadBulkHoloValues();

                        // Clear sessionStorage on successful invoice generation
                        clearModalDataFromSession();
                        removeCartContentFromSession();

                        renderAlert(data.pdf_path, 'message')
                        //recalculate auction price and profit
                    } else if (data.status === 'error') {
                        // Display error message for insufficient inventory
                        renderAlert('Error: ' + data.message, 'error');
                    } else {
                        renderAlert('Something went wrong generating the invoice', 'error');
                    }
                }
            });
        }
    });
}

async function addToShoppingCart(card, auctionId, cardId = null) {
    // Entry B: From auction tab (cardId provided)
    if (cardId !== null) {
        if (existingIDs.has(cardId)) {
            renderAlert('This card is already in cart', 'error');
            return;
        }

        // Check if a matching CartLine already exists
        const existing = cartLines.find(l => l.matches(card.cardName, card.cardNum, card.condition));
        if (existing) {
            existing.cardIds.push(cardId);
            existingIDs.add(cardId);
            // Update display
            if (existing.element) {
                const qtyDisplay = existing.element.querySelector('.qty-display');
                if (qtyDisplay) qtyDisplay.textContent = existing.quantity;
                // Update +/- button states
                const plusBtn = existing.element.querySelector('.qty-plus');
                if (plusBtn) plusBtn.disabled = !existing.canIncrement;
            }
            saveCartContentToSession();
        } else {
            // Create new CartLine with just this one cardId, empty pool
            const line = new CartLine(
                card.cardName, card.cardNum, card.condition,
                card.auctionName || '', card.marketValue || '',
                [cardId]
            );
            cartLines.push(line);
            existingIDs.add(cardId);
            renderCartLine(line);
        }
        return;
    }

    // Entry A: From search results (no cardId)
    const existing = cartLines.find(l => l.matches(card.cardName, card.cardNum, card.condition));
    if (existing) {
        // Try to increment existing line
        if (!existing.canIncrement) {
            await existing.backfillPool(existingIDs);
        }
        if (existing.canIncrement) {
            const id = existing.increment();
            if (id !== null) {
                existingIDs.add(id);
                if (existing.element) {
                    const qtyDisplay = existing.element.querySelector('.qty-display');
                    if (qtyDisplay) qtyDisplay.textContent = existing.quantity;
                    const plusBtn = existing.element.querySelector('.qty-plus');
                    if (plusBtn) plusBtn.disabled = !existing.canIncrement;
                    const minusBtn = existing.element.querySelector('.qty-minus');
                    if (minusBtn) minusBtn.disabled = existing.cardIds.length <= 1;
                }
                saveCartContentToSession();
            }
        } else {
            renderAlert('No more available copies of this card', 'error');
        }
        return;
    }

    // No existing line — fetch full pool from server
    try {
        const response = await fetch('/getCardIds', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_name: card.cardName,
                card_num: card.cardNum,
                condition: card.condition,
                exclude_ids: [...existingIDs]
            })
        });
        if (!response.ok) {
            renderAlert('Failed to fetch card IDs', 'error');
            return;
        }
        const data = await response.json();
        if (data.status !== 'success' || !data.card_ids || data.card_ids.length === 0) {
            renderAlert('Card no longer available', 'error');
            return;
        }
        const line = new CartLine(
            card.cardName, card.cardNum, card.condition,
            card.auctionName || '', card.marketValue || '',
            data.card_ids
        );
        cartLines.push(line);
        existingIDs.add(line.cardIds[0]);
        renderCartLine(line);
    } catch (e) {
        renderAlert('Error adding card to cart: ' + e, 'error');
    }
}

function currentCartValue(type) {
    const contentDiv = document.querySelector(`.${type}-cart-content`);
    const cartQuantity = contentDiv.querySelector(`.${type}-quantity`);
    if (cartQuantity) {
        return Number(cartQuantity.textContent.replace('q: ', ''));
    } else {
        return 0;
    }
}

function addSealedToCart(sealed, sid, auctionId = null) {
    if (!existingIDs.has(sid)) {
        existingIDs.add(sid);
        const sealedDiv = document.querySelector('.sealed-content');
        const itemDiv = document.createElement('div');
        itemDiv.setAttribute('sid', sid);
        itemDiv.classList.add('sealed-item-cart');
        if (auctionId != null) {
            itemDiv.setAttribute('auction_id', auctionId)
        }
        itemDiv.innerHTML = `
        <p class='sealed-name'>${DOMPurify.sanitize(sealed.name)}</p>
        <p class='sealed-price'>${DOMPurify.sanitize(sealed.market_value)}€</p>
        <button class='remove-from-cart'>Remove</button>
        `

        const removeFromCart = itemDiv.querySelector('.remove-from-cart');
        removeFromCart.addEventListener('click', () => {
            existingIDs.delete(sid);
            itemDiv.remove();
            saveCartContentToSession();
        });

        sealedDiv.appendChild(itemDiv);
        saveCartContentToSession();
    }
    return;
}


function addBulkToCart() {
    const button = document.querySelector('.card-add-bulk');
    const input = document.querySelector('.cart-bulk-input');
    const contentDiv = document.querySelector(".bulk-cart-content");
    button.addEventListener('click', () => {
        const value = input.value;
        const bulkItems = contentDiv.querySelector('.bulk-cart-item-bulk');
        const inventorySize = document.querySelector('.bulk-value').textContent;
        const maxBulk = Number(inventorySize);
        if (Number(value) + currentCartValue('bulk') > maxBulk) {
            renderAlert(`You can not add more than ${maxBulk} bulk items to the cart`, 'error');
            return;
        }

        if (!bulkItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('bulk-cart-item-bulk');
                div.innerHTML = `
                    <p>Bulk</p>
                    <p class='bulk-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='bulk-sell-price' style='width:70px'>
                    <button class='remove-from-cart'>Remove</button>`

                contentDiv.appendChild(div);
                const sellPriceInput = contentDiv.querySelector('.bulk-sell-price')
                sellPriceInput.addEventListener("blur", saveCartContentToSession)
                saveCartContentToSession();
            }
        } else {
            const quantityP = bulkItems.querySelectorAll('p')[1];
            let currentQuantity = Number(quantityP.textContent.replace('q: ', ''));
            if (value && !isNaN(value)) {
                currentQuantity += Number(value);
                quantityP.textContent = `q: ${currentQuantity}`;
                saveCartContentToSession();
            }
        }
        const removeButton = contentDiv.querySelector('.remove-from-cart');
        removeButton.addEventListener('click', () => {
            contentDiv.innerHTML = '';
            saveCartContentToSession();
        });
    });
    input.addEventListener('keydown', (event) => {
        if (event.key == 'Enter') {
            button.click();
        }
    });
}

function addHoloToCart() {
    const button = document.querySelector('.card-add-holo');
    const input = document.querySelector('.cart-holo-input');
    const contentDiv = document.querySelector(".holo-cart-content");

    button.addEventListener('click', () => {
        const value = input.value;
        const holoItems = contentDiv.querySelector('.holo-cart-item-holo');
        const inventorySize = document.querySelector('.holo-value').textContent;
        const maxHolo = Number(inventorySize);
        if (Number(value) + currentCartValue('holo') > maxHolo) {
            renderAlert(`You can not add more than ${maxHolo} holo items to the cart`, 'error');
            return;
        }

        if (!holoItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('holo-cart-item-holo');
                div.innerHTML = `
                    <p>Holo</p>
                    <p class='holo-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='holo-sell-price' style='width:70px'>
                    <button class='remove-from-cart'>Remove</button>`
                contentDiv.appendChild(div);
                const sellPriceInput = contentDiv.querySelector('.holo-sell-price')
                sellPriceInput.addEventListener("blur", saveCartContentToSession)

                saveCartContentToSession();
            }
        } else {
            const quantityP = holoItems.querySelectorAll('p')[1];
            let currentQuantity = Number(quantityP.textContent.replace('q: ', ''));
            if (value && !isNaN(value)) {
                currentQuantity += Number(value);
                quantityP.textContent = `q: ${currentQuantity}`;
                saveCartContentToSession();
            }
        }
        const removeButton = contentDiv.querySelector('.remove-from-cart');
        removeButton.addEventListener('click', () => {
            contentDiv.innerHTML = '';
            saveCartContentToSession();
        });
    });
    input.addEventListener('keydown', (event) => {
        if (event.key == 'Enter') {
            button.click();
        }
    });
}

function addExToCart() {
    const button = document.querySelector('.card-add-ex');
    const input = document.querySelector('.cart-ex-input');
    const contentDiv = document.querySelector('.ex-cart-content');

    button.addEventListener('click', () => {
        const value = input.value;
        const exItems = contentDiv.querySelector('.ex-cart-item-ex');
        const inventorySize = document.querySelector('.ex-value').textContent;
        const maxEx = Number(inventorySize);
        if (Number(value) + currentCartValue('ex') > maxEx) {
            renderAlert(`You can not add more than ${maxEx} ex items to the cart`, 'error');
            return;
        }

        if (!exItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('ex-cart-item-ex');
                div.innerHTML = `
                    <p>Ex</p>
                    <p class='ex-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='ex-sell-price' style='width:70px'>
                    <button class='remove-from-cart'>Remove</button>`;
                contentDiv.appendChild(div);
                const sellPriceInput = contentDiv.querySelector('.ex-sell-price');
                sellPriceInput.addEventListener('blur', saveCartContentToSession);
                saveCartContentToSession();
            }
        } else {
            const quantityP = exItems.querySelectorAll('p')[1];
            let currentQuantity = Number(quantityP.textContent.replace('q: ', ''));
            if (value && !isNaN(value)) {
                currentQuantity += Number(value);
                quantityP.textContent = `q: ${currentQuantity}`;
                saveCartContentToSession();
            }
        }
        const removeButton = contentDiv.querySelector('.remove-from-cart');
        removeButton.addEventListener('click', () => {
            contentDiv.innerHTML = '';
            saveCartContentToSession();
        });
    });
    input.addEventListener('keydown', (event) => {
        if (event.key == 'Enter') {
            button.click();
        }
    });
}

function startPolling() {
    setInterval(async () => {
        try {
            const response = await fetch('/getLatest');
            const data = await response.json();
            if (data.status === 'success') {
                const shippingInfo = data.message.shipping_info;
                const cards = data.message.cards;
                const sealed = data.message.sealed;

                sessionStorage.removeItem('invoiceModalData');
                deleteCartContent(
                    document.querySelector('.cart-content'),
                    document.querySelector('.bulk-cart-content'),
                    document.querySelector('.holo-cart-content'),
                    document.querySelector('.ex-cart-content'),
                    document.querySelector('.sealed-content')
                );
                sessionStorage.setItem('invoiceModalData', JSON.stringify(shippingInfo));
                cards.forEach((card) => {
                    const validIds = [];
                    const cardIds = Array.isArray(card.cardId) ? card.cardId : [card.id];
                    cardIds.forEach((id) => {
                        if (id === null) {
                            spawnMissingIdModal(card);
                        } else {
                            validIds.push(id);
                        }
                    });

                    if (validIds.length === 0) return;
                    if (validIds.some(id => existingIDs.has(id))) return;

                    const line = new CartLine(card.name, card.num, card.condition, null, card.marketValue, validIds);
                    line.maxQuantity();
                    cartLines.push(line);
                    renderCartLine(line);
                    validIds.forEach(id => existingIDs.add(id));
                });

                sealed.forEach((item) => {
                    const sealedIds = Array.isArray(item.id) ? item.id : [item.id];
                    if (sealedIds.every(id => id === null)) {
                        spawnMissingIdModal(item);
                        return;
                    }
                    const count = item.count || sealedIds.length || 1;
                    for (let i = 0; i < count; i++) {
                        addSealedToCart({ name: item.name, market_value: item.market_value }, sealedIds[i]);
                    }
                });
            }
        } catch (error) {
            renderAlert(error, 'error');
        }
    }, 5000);
}

function spawnMissingIdModal(card) {
    let modal = document.querySelector('.missingIdModal');
    if (!modal) {
        modal = document.createElement("div");
        modal.classList.add('missingIdModal');
        modal.innerHTML = `
            <div class="modal-card-list">
                <div class="missingId-header">
                    <p>Could not find these cards in unsold cards</p>
                    <button class='close-missingId-modal'>X</button>
                </div>
                <div class="missingId-list"></div>
            </div>
        `;

        const close = modal.querySelector('.close-missingId-modal');
        close.addEventListener('click', () => {
            modal.remove();
        });
    }

    const cardDiv = document.createElement("div");
    cardDiv.innerHTML = `
        <p>${DOMPurify.sanitize(card.name || "")}</p>
        <p>${DOMPurify.sanitize(card.num || "")}</p>
        <p>${DOMPurify.sanitize(card.condition || "")}</p>
        <p>${DOMPurify.sanitize(card.marketValue || card.market_value || "")}€</p>
    `;
    cardDiv.classList.add('missingId-item');
    modal.querySelector('.missingId-list').append(cardDiv);

    document.body.appendChild(modal);
}


function addResultScrollingWithArrows(searchInput, resultsQueue) {
    searchInput.addEventListener('keydown', (event) => {
        if (event.key == 'ArrowDown') {
            event.preventDefault();
            resultsQueue.moveNext();
            resultsQueue.getCurrent().focus();
        }
        if (event.key == 'ArrowUp') {
            event.preventDefault();
            resultsQueue.movePrev();
            resultsQueue.getCurrent().focus();
        }
    });
}


function searchBar() {
    const searchInput = document.querySelector('.search-field');

    const searchBtn = document.querySelector('.search-btn');
    let results = null;
    searchInput.addEventListener('keydown', async (event) => {
        if (event.key == 'Enter') {
            if (searchInput.value == "") {

                const searchContainer = document.querySelector('.search-results');
                searchContainer.innerHTML = ''; // Clear previous results
                return;
            }
            results = await search(searchInput.value.toUpperCase());
            const resultsQueue = new queue(results.length + 1) //if no results it thows error;
            resultsQueue.enqueue(searchInput)
            displaySearchResults(results, resultsQueue, searchInput);
            addResultScrollingWithArrows(searchInput, resultsQueue, searchInput);

        }
    })
    searchBtn.addEventListener('click', async () => {
        if (searchInput.value == "") {
            const searchContainer = document.querySelector('.search-results');
            searchContainer.innerHTML = ''; // Clear previous results
        }
        results = await search(searchInput.value.toUpperCase().trim());
        const resultsQueue = new queue(results.length + 1);
        resultsQueue.enqueue(searchInput)
        displaySearchResults(results, resultsQueue);
        searchInput.focus();
        addResultScrollingWithArrows(searchInput, resultsQueue);
    });
}

async function search(searchPrompt) {

    const jsonbody = JSON.stringify({ query: searchPrompt, cartIds: [...existingIDs] });
    const response = await fetch('/searchCard',
        {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: jsonbody,
        }
    )
    const data = await response.json();
    if (data.status == "success") {
        return data.value;
    } else {
        renderAlert('Search failed', 'error');
    }
}

function displaySearchResults(results, resultsQueue, searchInput) {

    const searchContainer = document.querySelector('.search-results');
    searchContainer.innerHTML = ''; // Clear previous results

    if (!results || results.length === 0) {
        const div = document.createElement('div');
        div.classList.add('search-result-item');
        div.innerHTML = '<p>No results found</p>';
        searchContainer.appendChild(div);
        return;
    }

    results.forEach(result => {
        const div = document.createElement('div');
        div.classList.add('search-result-item');
        div.tabIndex = 0;
        const safeAuctionId = sanitizeNumericId(result.auction_id);

        // Check if this is a sealed item (has 'sid' field) or a card
        const isSealed = result.hasOwnProperty('sid');

        if (isSealed) {
            // Handle sealed item display
            const sealed = {
                name: result.name,
                market_value: result.market_value
            };

            div.innerHTML = `
                <p class="result result-sealed-name">${DOMPurify.sanitize(result.name || 'N/A')}</p>
                <p class="result result-market-value">${DOMPurify.sanitize(result.market_value ? result.market_value + '€' : 'N/A')}</p>
                <p class="result result-auction-name">${DOMPurify.sanitize(result.auction_name || (result.auction_id ? result.auction_id - 1 : 'Unassigned'))}</p>
                <span class="result-type-badge sealed-badge">Sealed</span>
                ${result.auction_id || result.auction_name ? `<p class="result result-auction-name">${DOMPurify.sanitize(result.auction_name || result.auction_id - 1)}</p>` : `<p></p>`}
                <button class="add-to-cart-btn">Add to cart</button>
                ${safeAuctionId ? `<button class="view-auction" data-id="${safeAuctionId}">View</button>` : ''}
            `;

            resultsQueue.enqueue(div);

            div.addEventListener('keydown', (event) => {
                event.preventDefault();
                if (event.key == 'ArrowDown') {
                    resultsQueue.moveNext();
                    resultsQueue.getCurrent().focus();
                } else if (event.key == 'ArrowUp') {
                    resultsQueue.movePrev();
                    resultsQueue.getCurrent().focus();
                } else if (event.key == 'Enter') {
                    div.click();
                    searchInput.value = '';
                    searchInput.focus();
                }
            });

            // View auction button (if exists)
            if (result.auction_id) {
                const viewButton = div.querySelector('.view-auction');
                viewButton.addEventListener('click', async (event) => {
                    event.stopPropagation();
                    const element = document.getElementById(safeAuctionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth' });
                    }
                    searchContainer.innerHTML = '';
                });
            }

            // Add to cart handler for sealed items
            div.addEventListener('click', async () => {
                addSealedToCart(sealed, result.sid, result.auction_id);
                searchContainer.innerHTML = '';
            });

        } else {
            // Handle card display
            let card = new struct()
            card.cardName = result.card_name;
            card.cardNum = result.card_num;
            card.condition = result.condition;
            card.marketValue = result.market_value;
            const safeConditionClass = sanitizeClassToken(result.condition || 'Unknown');

            const availableCount = result.available_count ? result.available_count : 1;
            let pendingQty = 1;

            // Display in desired order, with proper formatting
            div.innerHTML = `
                <p class="result result-card-name">${DOMPurify.sanitize(result.card_name || 'N/A')}</p>
                <p class="result result-card-num">${DOMPurify.sanitize(result.card_num || 'N/A')}</p>
                <p class="result result-condition ${safeConditionClass}">${DOMPurify.sanitize(result.condition || 'Unknown')}</p>
                <p class="result result-market-value">${DOMPurify.sanitize(result.market_value ? result.market_value + '€' : 'N/A')}</p>
                <p class="result result-quantity">${pendingQty} / ${availableCount}</p>
                <p class="result result-auction-name">${DOMPurify.sanitize(result.auction_name || result.auction_id - 1)}</p>
                <button class="add-to-cart-btn">Add to cart</button>
                ${safeAuctionId ? `<button class="view-auction" data-id="${safeAuctionId}">View</button>` : ''}
            `;
            resultsQueue.enqueue(div);

            div.addEventListener('keydown', async (event) => {
                event.preventDefault();
                if (event.key == 'ArrowDown') {
                    resultsQueue.moveNext();
                    resultsQueue.getCurrent().focus();
                } else if (event.key == 'ArrowUp') {
                    resultsQueue.movePrev();
                    resultsQueue.getCurrent().focus();
                } else if (event.key == 'ArrowRight') {
                    pendingQty = Math.min(pendingQty + 1, availableCount);
                    div.querySelector('.result-quantity').textContent = `${pendingQty} / ${availableCount}`;
                } else if (event.key == 'ArrowLeft') {
                    pendingQty = Math.max(pendingQty - 1, 1);
                    div.querySelector('.result-quantity').textContent = `${pendingQty} / ${availableCount}`;
                } else if (event.key == 'Enter') {
                    for (let i = 0; i < pendingQty; i++) {
                        await addToShoppingCart(card);
                    }
                    searchInput.value = '';
                    searchInput.focus();
                    document.querySelector('.search-results').innerHTML = '';
                }
            });

            const viewButton = div.querySelector('.view-auction');
            viewButton.addEventListener('click', async (event) => {
                event.stopPropagation();
                const element = document.getElementById(`${result.auction_id}`);
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth' });
                }
                const auctionTab = element.closest('.auction-tab');
                if (auctionTab) {
                    const viewButton = auctionTab.querySelector('.view-auction');
                    if (viewButton && viewButton.textContent === 'View') {
                        await loadAuctionContent(viewButton);
                    }
                    const card = auctionTab.querySelector(`.card[data-id='${result.id}']`);
                    const sealed = auctionTab.querySelector(`.sealed-item[sid='${result.sid}']`);
                    if (card) {
                        card.scrollIntoView({ behavior: 'smooth' });
                        card.classList.add('highlighted-search-result');
                        setTimeout(() => {
                            card.classList.remove('highlighted-search-result');
                        }, 2000);
                    }
                    if (sealed) {
                        sealed.scrollIntoView({ behavior: 'smooth' });
                        sealed.classList.add('highlighted-search-result');
                        setTimeout(() => {
                            sealed.classList.remove('highlighted-search-result');
                        }, 2000);
                    }
                }
                searchContainer.innerHTML = '';
            });

            div.addEventListener('click', async () => {
                await addToShoppingCart(card);
                searchContainer.innerHTML = '';
            });
        }

        searchContainer.appendChild(div);
    });
}

async function loadBulkHoloValues() {
    let holoVal = document.querySelector('.holo-value');
    let bulkVal = document.querySelector('.bulk-value');
    let exVal = document.querySelector('.ex-value');
    try {
        const response = await fetch('/bulkCounterValue');
        const data = await response.json();
        if (data.status == 'success') {
            bulkVal.textContent = data.bulk_counter;
            holoVal.textContent = data.holo_counter;
            exVal.textContent = data.ex_counter;
        } else {
            renderAlert('There was a problem loading bulk, holo and ex values', 'error');
        }
    } catch (e) {
        renderAlert('Error loading bulk/holo/ex values: ' + e, 'error');
    }
}

function initializeBulkHolo() {
    loadBulkHoloValues();
}


async function loadAuctionContent(button) {
    const auctionId = button.getAttribute('data-id');
    //TODO - make this into a single endpoint
    const cardsUrl = '/loadCards/' + auctionId;
    const bulkUrl = '/loadBulk/' + auctionId;
    const sealedUrl = '/loadSealed/' + auctionId;
    const auctionDiv = button.closest('.auction-tab');
    const cardsContainer = auctionDiv.querySelector('.cards-container');
    try {
        if (cardsContainer.childElementCount === 0 || cardsContainer.style.display === 'none') {
            cardsContainer.style.display = 'flex';
            button.textContent = 'Hide';

            // Only fetch if we don't have content already
            if (cardsContainer.childElementCount === 0) {
                const response = await fetch(cardsUrl);
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
                        <p>Sell price</p>
                        <p>Margin</p>
                        <p></p>
                        <p></p>
                    </div>
                `;
                    cards.forEach(card => {
                        const safeCardId = sanitizeNumericId(card.id);
                        const safeCardConditionClass = sanitizeClassToken(card.condition || 'Unknown');
                        const cardDiv = document.createElement('div');
                        cardDiv.classList.add('card');
                        cardDiv.setAttribute('data-id', safeCardId);
                        cardDiv.innerHTML = `
                        ${renderField(DOMPurify.sanitize(card.card_name), 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                        ${renderField(DOMPurify.sanitize(card.card_num), 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                        <p class='card-info condition ${safeCardConditionClass}' data-field="condition">${DOMPurify.sanitize(card.condition) ? DOMPurify.sanitize(card.condition) : 'Unknown'}</p>
                        ${renderField(card.card_price ? DOMPurify.sanitize(card.card_price) + '€' : null, 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                        ${renderField(card.market_value ? DOMPurify.sanitize(card.market_value) + '€' : null, 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                        ${renderField(card.sell_price ? DOMPurify.sanitize(card.sell_price) + '€' : null, 'text', ['card-info', 'sell-price'], 'Sell Price', 'sell_price')}
                        ${renderField(card.card_price !== null && card.market_value !== null ? (card.market_value - card.card_price).toFixed(2) + '€' : ' ', 'text', ['card-info', 'profit'], 'profit', true)}
                        <button class="add-to-cart">Add to cart</button>
                        <span hidden class="card-id">${safeCardId}</span>
                        <button class=delete-card data-id="${safeCardId}">Delete</button>
                    `;
                        cardsContainer.appendChild(cardDiv);
                    });

                    cardsContainer.addEventListener('dblclick', (event) => {
                        if (event.target.closest('.card') && !(event.target.tagName === "DIV")) {
                            const cardDiv = event.target.closest('.card');
                            const cardId = cardDiv.querySelector('.card-id').textContent;
                            if (event.target.classList.contains('condition')) {
                                const value = event.target.textContent.trim();
                                const select = document.createElement('select');
                                const options = ['Mint', 'Near Mint', 'Excellent', 'Good', 'Light Played', 'Played', 'Poor'];
                                const dataset = event.target.dataset.field;
                                options.forEach(option => {
                                    const opt = document.createElement('option');
                                    opt.value = option;
                                    opt.textContent = option;
                                    if (option === value) {
                                        opt.selected = true;
                                    }
                                    select.appendChild(opt);
                                });
                                event.target.replaceWith(select);
                                select.classList.add(...event.target.classList, 'select-condition');
                                select.addEventListener('change', (event) => {
                                    const selectedValue = event.target.value;
                                    const p = document.createElement('p');
                                    const classValue = selectedValue.split(' ').join('_').toLowerCase();
                                    p.classList.add('card-info', 'condition', classValue);
                                    p.textContent = selectedValue || value;
                                    select.replaceWith(p);
                                    patchValue(cardId, p.textContent, dataset);
                                });
                            }
                            if (event.target.tagName === "P") {
                                let value = event.target.textContent.replace('€', '');
                                if (isNaN(value)) {
                                    value = value.toUpperCase();
                                }
                                const dataset = event.target.dataset.field;
                                const input = document.createElement('input');
                                input.type = 'text';
                                input.value = value;
                                input.classList.add(...event.target.classList);
                                event.target.replaceWith(input);
                                input.focus();
                                input.addEventListener('blur', async (blurEvent) => {
                                    let newValue = blurEvent.target.value.replace(',', '.');
                                    if (isNaN(newValue)) {
                                        newValue = newValue.toUpperCase();
                                    }
                                    const auctionTab = blurEvent.target.closest('.auction-tab');

                                    getInputValueAndPatch(newValue || value, input, dataset, cardId);
                                    if (blurEvent.target.classList.contains('card-price') || blurEvent.target.classList.contains('sell-price')) {
                                        await updateInventoryValueAndTotalProfit();
                                    }
                                });
                                input.addEventListener('keydown', (event) => {
                                    if (event.key === 'Enter') {
                                        input.blur();
                                    }
                                });
                            }
                        }
                    });


                    const inputFields = cardsContainer.querySelectorAll('input[type="text"]');
                    inputFields.forEach((input) => {
                        input.addEventListener('blur', async (event) => {
                            const cardId = event.target.closest('.card').querySelector('.card-id').textContent;
                            const value = event.target.value.replace(',', '.');
                            const dataset = event.target.dataset;
                            getInputValueAndPatch(value, input, dataset.field, cardId);
                            await updateInventoryValueAndTotalProfit();
                        })
                        input.addEventListener('keydown', (event) => {
                            if (event.key === 'Enter') {
                                input.blur();
                            }
                        });
                    });

                    const addToCartButtons = cardsContainer.querySelectorAll('.add-to-cart');
                    addToCartButtons.forEach((button) => {
                        button.addEventListener('click', async () => {
                            const cardDiv = button.closest('.card');
                            const cardId = cardDiv.getAttribute('data-id');
                            const auctionId = auctionDiv.getAttribute('data-id');
                            const card = new struct();
                            card.cardName = cardDiv.querySelector('.card-name').textContent;
                            card.cardNum = cardDiv.querySelector('.card-num').textContent;
                            card.condition = cardDiv.querySelector('.condition').textContent;
                            const marketValueText = cardDiv.querySelector('.market-value').textContent;
                            card.marketValue = marketValueText ? marketValueText.replace('€', '') : null;
                            await addToShoppingCart(card, auctionId, cardId);
                        });
                    });

                    const deleteCard = document.querySelectorAll('.delete-card');
                    deleteCard.forEach((button) => {
                        button.addEventListener('click', async () => {
                            const cardId = button.getAttribute('data-id');
                            const cardDiv = button.closest('.card');
                            const cardsContainer = button.closest('.cards-container');
                            const auctionId = cardsContainer.closest('.auction-tab').getAttribute('data-id');
                            if (button.textContent === 'Confirm') {
                                const auctionDiv = cardsContainer.closest('.auction-tab');
                                const deleted = await removeCard(cardId, cardDiv);
                                const cards = cardsContainer.querySelectorAll('.card');
                                if (!deleted) return;
                                if (auctionDiv.classList.contains('singles')) {
                                    await updateInventoryValueAndTotalProfit()
                                    if (cardsContainer.childElementCount < 3) {
                                        const p = document.createElement('p');
                                        p.textContent = 'Empty';
                                        cardsContainer.insertBefore(p, cardsContainer.querySelector('.button-container'));
                                    }
                                } else {
                                    await updateInventoryValueAndTotalProfit();
                                }
                                if (cardsContainer.childElementCount < 3) {
                                    if (!(auctionDiv.classList.contains('singles'))) {
                                        deleteAuction(auctionId, auctionDiv);
                                    }
                                }
                            } else {
                                // First click: ask for confirmation
                                button.textContent = 'Confirm';
                                const timerID = setTimeout(() => {
                                    button.textContent = 'Delete';
                                }, 3000);
                                // Remove confirmation if user clicks elsewhere
                                document.addEventListener('click', function handler(e) {
                                    if (e.target !== button) {
                                        button.textContent = 'Delete';
                                        document.removeEventListener('click', handler);
                                        clearTimeout(timerID);
                                    }
                                });
                            }
                        });
                    });
                }

                // Load sealed items BEFORE bulk items
                try {
                    const responseSealed = await fetch(sealedUrl);
                    const sealedData = await responseSealed.json();

                    sealedData.forEach(sealedItem => {
                        const sealedDiv = document.createElement('div');
                        sealedDiv.classList.add('sealed-item');
                        sealedDiv.setAttribute('sid', sealedItem.sid);

                        const margin = (Number(sealedItem.market_value) - Number(sealedItem.price)).toFixed(2);
                        const timeStamp = sealedItem.date.replace('Z', '');
                        const date = new Date(timeStamp);
                        let formatedDate = date.toLocaleDateString('sk-SK', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit'
                        });

                        sealedDiv.innerHTML = `
                            <p class="sealed-name">${DOMPurify.sanitize(sealedItem.name)}</p>
                            <p class="sealed-price">${DOMPurify.sanitize(sealedItem.price)}€</p>
                            <p class="sealed-market-value">${DOMPurify.sanitize(sealedItem.market_value)}€</p>
                            <p class="sealed-margin">${DOMPurify.sanitize(margin)}€</p>
                            <p class="sealed-date">${DOMPurify.sanitize(formatedDate)}</p>
                            <button class="add-to-cart-sealed" data-sid="${sealedItem.sid}">Add to cart</button>
                            <button class="delete-sealed-item" data-sid="${sealedItem.sid}">Delete</button>
                        `;

                        cardsContainer.insertBefore(sealedDiv, cardsContainer.querySelector('.button-container'));
                    });

                    // Add event listeners for "Add to cart" buttons
                    const addToCartButtons = cardsContainer.querySelectorAll('.add-to-cart-sealed');
                    addToCartButtons.forEach((button) => {
                        button.addEventListener('click', () => {
                            const sealedDiv = button.closest('.sealed-item');
                            const sid = sealedDiv.getAttribute('sid');
                            const auctionId = auctionDiv.getAttribute('data-id');

                            const sealedData = {
                                name: DOMPurify.sanitize(sealedDiv.querySelector('.sealed-name').textContent),
                                market_value: DOMPurify.sanitize(sealedDiv.querySelector('.sealed-market-value').textContent.replace('€', ''))
                            };

                            addSealedToCart(sealedData, sid, auctionId);
                        });
                    });

                    // Add event listeners for "Delete" buttons
                    const deleteSealedButtons = cardsContainer.querySelectorAll('.delete-sealed-item');
                    deleteSealedButtons.forEach((button) => {
                        button.addEventListener('click', async () => {
                            const sid = button.getAttribute('data-sid');
                            const sealedDiv = button.closest('.sealed-item');

                            if (button.textContent === 'Confirm') {
                                const response = await fetch(`/deleteSealed/${sid}`, { method: 'DELETE' });
                                const data = await response.json();

                                if (data.status === 'success') {
                                    sealedDiv.remove();
                                }
                            } else {
                                button.textContent = 'Confirm';
                                const timerID = setTimeout(() => {
                                    button.textContent = 'Delete';
                                }, 3000);

                                document.addEventListener('click', function handler(e) {
                                    if (e.target !== button) {
                                        button.textContent = 'Delete';
                                        document.removeEventListener('click', handler);
                                        clearTimeout(timerID);
                                    }
                                });
                            }
                        });
                    });

                } catch (error) {
                    renderAlert('Error loading sealed items: ' + error, 'error');
                }

                // Load bulk items
                try {
                    const responseBulk = await fetch(bulkUrl);
                    const bulkData = await responseBulk.json();
                    bulkData.forEach(bulkItem => {
                        const bulkDiv = document.createElement('div');
                        bulkDiv.classList.add('bulk-item');
                        bulkDiv.setAttribute('data-id', bulkItem.id);
                        bulkDiv.innerHTML = `
                            <p class="bulk-name">${DOMPurify.sanitize(bulkItem.item_type)}</p>
                            <p class="bulk-quantity">Quantity: ${DOMPurify.sanitize(bulkItem.quantity)}</p>
                            <p class="bulk-sell-price">Sell Price: ${bulkItem.total_price ? DOMPurify.sanitize(bulkItem.total_price) + '€' : 'N/A'}</p>
                            <button class="delete-bulk-item" data-id="${DOMPurify.sanitize(bulkItem.id)}">Delete</button>
                        `;
                        cardsContainer.insertBefore(bulkDiv, cardsContainer.querySelector('.button-container'));
                    }
                    );
                    const deleteBulkButtons = cardsContainer.querySelectorAll('.delete-bulk-item');
                    deleteBulkButtons.forEach((button) => {
                        button.addEventListener('click', async () => {
                            const bulkId = button.getAttribute('data-id');
                            const bulkDiv = button.closest('.bulk-item');
                            const cardsContainer = button.closest('.cards-container');
                            const auctionId = cardsContainer.closest('.auction-tab').getAttribute('data-id');
                            if (button.textContent === 'Confirm') {
                                const deleted = await removeBulkItem(bulkId, bulkDiv);
                                if (!deleted) return;
                            } else {
                                // First click: ask for confirmation
                                button.textContent = 'Confirm';
                                const timerID = setTimeout(() => {
                                    button.textContent = 'Delete';
                                }, 3000);
                                // Remove confirmation if user clicks elsewhere
                                document.addEventListener('click', function handler(e) {
                                    if (e.target !== button) {
                                        button.textContent = 'Delete';
                                        document.removeEventListener('click', handler);
                                        clearTimeout(timerID);
                                    }
                                });
                            }
                        });
                    });

                } catch (error) {
                    renderAlert('Error loading bulk items: ' + error, 'error');
                }
            }
        } else {
            cardsContainer.style.display = 'none';
            button.textContent = 'View';
        }
    } catch (error) {
        renderAlert('Error loading cards: ' + error, 'error');
    }

    // Only add button container if it doesn't exist
    if (!cardsContainer.querySelector('.button-container')) {
        const buttonDiv = document.createElement('div');
        buttonDiv.classList.add('button-container');
        buttonDiv.innerHTML = `
                <div><button class="add-cards-auction">Add cards</button></div>
                <div><button class="add-sealed-auction">Add sealed</button></div>
                <div><button class="add-bulk-auction">Add bulk</button></div>
                <div><button class="add-holo-auction">Add holo</button></div>
                <div><button class="add-ex-auction">Add ex</button></div>
                <div><button class="save-added-cards">Save</button></div>
                `;
        cardsContainer.appendChild(buttonDiv);
        cardsContainer.querySelector('.save-added-cards').hidden = true;

        const addCardButton = cardsContainer.querySelector('.add-cards-auction');
        addCardButton.addEventListener('click', () => {
            cardsContainer.querySelector('.save-added-cards').hidden = false;
            const newCard = document.createElement('div');
            newCard.classList.add('card', 'new-card');
            newCard.innerHTML = `
                ${renderField(null, 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                ${renderField(null, 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                <select class="card-info condition select-condition" data-field="condition">
                    <option value="Mint">Mint</option>
                    <option value="Near Mint" selected="selected">Near Mint</option>
                    <option value="Excellent">Excellent</option>
                    <option value="Good">Good</option>
                    <option value="Light Played">Light Played</option>
                    <option value="Played">Played</option>
                    <option value="Poor">Poor</option>
                </select>
                ${renderField(null, 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                ${renderField(null, 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                ${renderField(null, 'text', ['card-info', 'sell-price'], 'Sell Price', 'sell_price')}`;
            cardsContainer.insertBefore(newCard, cardsContainer.querySelector('.button-container'));
        });

        const addBulkButton = cardsContainer.querySelector('.add-bulk-auction');
        addBulkButton.addEventListener('click', () => {
            cardsContainer.querySelector('.save-added-cards').hidden = false;
            const bulkDiv = cardsContainer.querySelector('.add-bulk-item');
            if (!bulkDiv) {
                const newBulkDiv = document.createElement('div');
                newBulkDiv.classList.add('add-bulk-item');
                newBulkDiv.innerHTML = `
                    <p class="bulk-name">Bulk Item</p>
                    <p class="bulk-quantity">Quantity: <input type="number" class="bulk-quantity-input" min="1"></p>
                    <p class="bulk-sell-price">Sell Price: <input type="text" class="bulk-sell-price-input" ></p>
    
                `;
                cardsContainer.insertBefore(newBulkDiv, cardsContainer.querySelector('.button-container'));
            }
        });

        const addSealedButton = cardsContainer.querySelector('.add-sealed-auction');
        addSealedButton.addEventListener('click', () => {
            cardsContainer.querySelector('.save-added-cards').hidden = false;

            // Create input form for new sealed item
            const newSealedDiv = document.createElement('div');
            newSealedDiv.classList.add('add-sealed-item');

            const currentDate = new Date().toISOString().split('T')[0];

            newSealedDiv.innerHTML = `
                <input type="text" class="sealed-name-input" placeholder="Sealed item name">
                <input type="number" class="sealed-price-input" placeholder="Price" step="0.01" min="0">
                <input type="number" class="sealed-market-value-input" placeholder="Market value" step="0.01" min="0">
                <input type="date" class="sealed-date-input" value="${currentDate}" max="${currentDate}">
                <button class="remove-sealed-input">×</button>
            `;

            cardsContainer.insertBefore(newSealedDiv, cardsContainer.querySelector('.button-container'));

            // Add remove button functionality
            const removeBtn = newSealedDiv.querySelector('.remove-sealed-input');
            removeBtn.addEventListener('click', () => {
                newSealedDiv.remove();

                // Hide save button if no new items
                const hasNewItems = cardsContainer.querySelector('.new-card') ||
                    cardsContainer.querySelector('.add-sealed-item') ||
                    cardsContainer.querySelector('.add-bulk-item') ||
                    cardsContainer.querySelector('.add-holo-item') ||
                    cardsContainer.querySelector('.add-ex-item');
                if (!hasNewItems) {
                    cardsContainer.querySelector('.save-added-cards').hidden = true;
                }
            });
        });

        const addHoloButton = cardsContainer.querySelector('.add-holo-auction');
        addHoloButton.addEventListener('click', () => {
            cardsContainer.querySelector('.save-added-cards').hidden = false;
            const holoDiv = cardsContainer.querySelector('.add-holo-item');
            if (!holoDiv) {
                const newHoloDiv = document.createElement('div');
                newHoloDiv.classList.add('add-holo-item');
                newHoloDiv.innerHTML = `
                    <p class="holo-name">Holo Item</p>
                    <p class="holo-quantity">Quantity: <input type="number" class="holo-quantity-input" min="1"></p>
                    <p class="holo-sell-price">Sell Price: <input type="text" class="holo-sell-price-input" ></p>
                `;
                cardsContainer.insertBefore(newHoloDiv, cardsContainer.querySelector('.button-container'));
            }
        });

        const addExButton = cardsContainer.querySelector('.add-ex-auction');
        addExButton.addEventListener('click', () => {
            cardsContainer.querySelector('.save-added-cards').hidden = false;
            const exDiv = cardsContainer.querySelector('.add-ex-item');
            if (!exDiv) {
                const newExDiv = document.createElement('div');
                newExDiv.classList.add('add-ex-item');
                newExDiv.innerHTML = `
                    <p class="ex-name">Ex Item</p>
                    <p class="ex-quantity">Quantity: <input type="number" class="ex-quantity-input" min="1"></p>
                    <p class="ex-sell-price">Sell Price: <input type="text" class="ex-sell-price-input" ></p>
                `;
                cardsContainer.insertBefore(newExDiv, cardsContainer.querySelector('.button-container'));
            }
        });

        const saveAddedCardButton = cardsContainer.querySelector('.save-added-cards');
        saveAddedCardButton.addEventListener('click', async () => {
            const itemsToAdd = {};
            saveAddedCardButton.hidden = true;
            const auctionId = auctionDiv.getAttribute('data-id');
            let cardsArray = [];
            const newCards = cardsContainer.querySelectorAll('.new-card');
            //try {
            newCards.forEach(async (card) => {
                let cardObj = new struct();
                cardObj.cardName = DOMPurify.sanitize(card.querySelector('input.card-name').value.trim().toUpperCase()) || null;
                cardObj.cardNum = DOMPurify.sanitize(card.querySelector('input.card-num').value.trim().toUpperCase()) || null;
                cardObj.condition = DOMPurify.sanitize(card.querySelector('select.condition').value) || null;
                cardObj.buyPrice = DOMPurify.sanitize(card.querySelector('input.card-price').value.replace(',', '.').trim()) || null;
                cardObj.marketValue = DOMPurify.sanitize(card.querySelector('input.market-value').value.replace(',', '.').trim()) || null;
                cardObj.sellPrice = DOMPurify.sanitize(card.querySelector('input.sell-price').value.replace(',', '.').trim()) || null;
                cardObj.soldDate = null;

                if (cardObj.buyPrice === null) cardObj.buyPrice = cardObj.marketValue * 0.85;
                if (cardObj.sellPrice === null) cardObj.sellPrice = cardObj.marketValue;
                if (cardObj.cardName !== null && cardObj.marketValue !== null) {
                    cardsArray.push(cardObj);
                } else {
                    card.remove();
                }
            });

            itemsToAdd['cards'] = cardsArray;

            const auctionSingles = auctionDiv.classList.contains('singles') ? true : false;
            for (let i = 0; i < cardsArray.length; i++) {
                let j = 0;
                for (const [key, value] of Object.entries(cardsArray[i])) {
                    if (key === 'soldDate') continue;
                    const cardElement = newCards[i].children;
                    replaceWithPElement(cardElement[j].dataset.field, value, cardElement[j]);
                    j++;
                }
            }

            const bulkDiv = cardsContainer.querySelector('.add-bulk-item');
            if (bulkDiv) {
                const bulkItems = { 'item_type': 'bulk', 'quantity': null, 'total_price': null };
                bulkItems.quantity = DOMPurify.sanitize(bulkDiv.querySelector('.bulk-quantity-input').value.trim()) || null;
                bulkItems.total_price = DOMPurify.sanitize(bulkDiv.querySelector('.bulk-sell-price-input').value.replace(',', '.').trim()) || null;
                bulkItems.unit_price = bulkItems.total_price / bulkItems.quantity || null;
                itemsToAdd['bulk'] = bulkItems;
            }

            const holoDiv = cardsContainer.querySelector('.add-holo-item');
            if (holoDiv) {
                const holoItems = { 'item_type': 'holo', 'quantity': null, 'total_price': null };
                holoItems.quantity = DOMPurify.sanitize(holoDiv.querySelector('.holo-quantity-input').value.trim()) || null;
                holoItems.total_price = DOMPurify.sanitize(holoDiv.querySelector('.holo-sell-price-input').value.replace(',', '.').trim()) || null;
                holoItems.unit_price = holoItems.total_price / holoItems.quantity || null;
                itemsToAdd['holo'] = holoItems;
            }

            const exDiv = cardsContainer.querySelector('.add-ex-item');
            if (exDiv) {
                const exItems = { 'item_type': 'ex', 'quantity': null, 'total_price': null };
                exItems.quantity = DOMPurify.sanitize(exDiv.querySelector('.ex-quantity-input').value.trim()) || null;
                exItems.total_price = DOMPurify.sanitize(exDiv.querySelector('.ex-sell-price-input').value.replace(',', '.').trim()) || null;
                exItems.unit_price = exItems.total_price / exItems.quantity || null;
                itemsToAdd['ex'] = exItems;
            }

            // Handle sealed items
            const sealedDivs = cardsContainer.querySelectorAll('.add-sealed-item');
            if (sealedDivs.length > 0) {
                const sealedItems = [];
                sealedDivs.forEach(sealedDiv => {
                    const name = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-name-input').value.trim()) || null;
                    const price = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-price-input').value.trim()) || null;
                    const marketValue = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-market-value-input').value.trim()) || null;
                    const date = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-date-input').value) || null;

                    if (name !== null && marketValue !== null) {
                        sealedItems.push({
                            name: name,
                            price: price,
                            market_value: marketValue,
                            date: date
                        });
                    }
                });

                if (sealedItems.length > 0) {
                    itemsToAdd['sealed'] = sealedItems;
                }
            }

            const jsonbody = JSON.stringify(itemsToAdd);
            const response = await fetch(`/addToExistingAuction/${auctionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: jsonbody
            });
            const data = await response.json();
            if (!(data.status === 'success')) {
                renderAlert('Error saving new cards: ' + JSON.stringify(data), 'error');
                return;
            }

            await updateInventoryValueAndTotalProfit();

            newCards.forEach(card => card.classList.remove('new-card'));
            //} catch (error) {
            //    renderAlert('Error saving new cards: ' + error, 'error');
            //    return;
            // }
            //this could be done better by dynamically adding the cards instead of reloading the whole auction
            window.location.reload();
        });
    }
}

async function initializeSealed() {
    const sealedContainer = document.querySelector('.sealed-container');
    const sealedTab = sealedContainer.querySelector('.sealed-tab');
    const viewButton = sealedContainer.querySelector('.view-sealed');
    viewButton.addEventListener('click', () => {
        loadSealed(viewButton);
    });

}

async function loadSealed(viewButton) {
    const sealedTab = document.querySelector('.sealed-tab');
    const contentDiv = document.querySelector('.sealed-tab-content')
    if (sealedTab.style.display === 'none' || sealedTab.childElementCount === 0) {
        sealedTab.style.display = 'flex';
        viewButton.innerHTML = 'Hide';
        console.log(sealedTab.childElementCount);

        // Only fetch if we don't have items already
        if (contentDiv.childElementCount === 0) {
            try {
                const response = await fetch('/loadSealed');
                const data = await response.json();
                if (data.status != 'success') {
                    renderAlert('Failed to load sealed products', 'error');
                    return;
                }

                data.data.forEach((sealedData) => {
                    const sealedDiv = document.createElement('div');
                    sealedDiv.classList.add('sealed-item');
                    sealedDiv.setAttribute('sid', sealedData.sid);
                    const margin = (Number(DOMPurify.sanitize(sealedData.market_value)) - Number(DOMPurify.sanitize(sealedData.price))).toFixed(2);
                    const timeStamp = DOMPurify.sanitize(sealedData.date).replace('Z', '');
                    const date = new Date(timeStamp);
                    let formatedDate = date.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
                    sealedDiv.innerHTML = `
                        <p class='sealed-name'>${DOMPurify.sanitize(sealedData.name)}</p>
                        <p class='unit-price'>${DOMPurify.sanitize(sealedData.price)}</p>
                        <p class='VAT-sealed'>${(DOMPurify.sanitize(sealedData.price) / 1.23).toFixed(2)}</p>
                        <p class='market-value-sealed'>${DOMPurify.sanitize(sealedData.market_value)}</p>
                        <p class='margin'>${margin}</p>
                        <p class='add-date'>${formatedDate}</p>
                        <button class='add-to-cart'>Add to cart</button>
                        <button class='delete-sealed'>Delete</button>
                        `

                    const addToCart = sealedDiv.querySelector('.add-to-cart');
                    addToCart.addEventListener('click', () => {
                        addSealedToCart(sealedData, sealedData.sid)
                    });

                    const removeSealed = sealedDiv.querySelector('.delete-sealed');
                    removeSealed.addEventListener('click', async () => {

                        if (removeSealed.textContent === 'Confirm') {
                            const response = await fetch(`/deleteSealed/${sealedData.sid}`, { method: 'DELETE' })
                            const data = await response.json();

                            if (data.status === 'success') {
                                sealedDiv.remove();
                            }
                        } else {
                            removeSealed.textContent = 'Confirm';
                            const timerID = setTimeout(() => {
                                removeSealed.textContent = 'Delete';
                            }, 3000);
                            // Remove confirmation if user clicks elsewhere
                            document.addEventListener('click', function handler(e) {
                                if (e.target !== removeSealed) {
                                    removeSealed.textContent = 'Delete';
                                    document.removeEventListener('click', handler);
                                    clearTimeout(timerID);
                                }
                            });
                        }
                    });
                    contentDiv.append(sealedDiv);
                })


                const buttonsContainer = document.querySelector('.buttons-container')

                const addButton = buttonsContainer.querySelector('.add-sealed');
                const date = new Date().toJSON().split('T')[0]
                addButton.addEventListener('click', () => {
                    const div = document.createElement('div');
                    div.classList.add('add-sealed');
                    div.innerHTML = `
                            <input type='text' placeholder='name'></input>
                            <input type='number' placeholder='price'></input>
                            <input type='number' placeholder='market value'></input>
                            <p></p>
                            <input type='date' value=${date} max=${date} ></input>
                        `
                    contentDiv.append(div);

                    const saveButton = buttonsContainer.querySelector('.save-sealed-btn');
                    saveButton.style.display = 'block';

                });

                const saveButton = buttonsContainer.querySelector('.save-sealed-btn');
                saveButton.addEventListener('click', async () => {
                    const inputDivs = contentDiv.querySelectorAll('.add-sealed');
                    let inputValues = []
                    inputDivs.forEach(div => {
                        const inputs = div.querySelectorAll('input');
                        const row = {};
                        row.name = inputs[0].value || null;
                        row.price = inputs[1].value || null;
                        row.market_value = inputs[2].value || null;
                        row.dateAdded = inputs[3].value;
                        if (row.name !== null && row.market_value !== null) {
                            inputValues.push(row);
                        }
                    })
                    saveButton.style.display = 'none';
                    if (inputValues.length > 0) {
                        const response = await fetch('/addSealed', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(inputValues)
                        });
                        const data = await response.json();
                        if (data.status === 'success') {
                            window.location.reload()
                        } else {
                            renderAlert(data.message, 'error');
                            inputDivs.forEach(div => {
                                div.remove();
                            });
                        }
                    }
                })

            }
            catch (e) {
                console.log('Error:', e);
            }
        }
    } else {
        sealedTab.style.display = 'none'
        viewButton.innerHTML = 'View';
    }
}

async function loadUnlinkedIds() {
    try {
        const response = await fetch('/unlinkedBarterIds');
        const data = await response.json();
        if (data.status === 'success') {
            return data.data;
        } else {
            throw ('Error');
        }
    } catch (err) {
        renderAlert('There was an error fetching non-barter ids' + err, 'error');
    }
}

async function renderBarterSelect(select) {
    const data = await loadUnlinkedIds();

    data.forEach((row) => {
        const option = document.createElement('option');
        option.value = sanitizeNumericId(row.id);
        option.textContent = sanitizePlainText(row.invoice_number);
        select.appendChild(option);
    });
    return select
}

async function loadAuctions() {
    const auctionContainer = document.querySelector('.auction-container');
    try {
        const response = await fetch('/loadAuctions');
        const data = await response.json();
        data.forEach(auction => {
            const safeAuctionId = sanitizeNumericId(auction.id);
            const safeSaleId = sanitizeNumericId(auction.sale_id);
            const auctionDiv = document.createElement('div');
            auctionDiv.classList.add('auction-tab');
            auctionDiv.id = safeAuctionId;
            if (auction.auction_name === 'Singles') {
                auctionDiv.classList.add('singles');
            }
            auctionDiv.setAttribute('data-id', safeAuctionId);
            let auctionName = auction.auction_name || "Auction " + (auction.id - 1); // Fallback for name
            let auctionPrice = auction.auction_price || null; // Fallback for buy price
            const buyDate = new Date(auction.date_created);
            let formatedDate = buyDate.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
            if (formatedDate === 'Invalid Date') {
                formatedDate = new Date(String(auction.date_created).split('T')[0]).toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });;
            }

            // Parse payment methods
            const payments = parsePaymentMethods(auction.payment_method);
            const paymentDisplay = formatPaymentDisplay(payments);
            const invoiceNumber = auction.invoice_number;

            auctionDiv.innerHTML = `
                <p class="auction-name">${DOMPurify.sanitize(auctionName)}</p>
                ${renderField(auctionPrice != null ? DOMPurify.sanitize(auctionPrice) + '€' : null, 'text', ['auction-price'], 'Auction Buy Price', 'auction_price')}
                <p class="buy-date">${DOMPurify.sanitize(formatedDate || dateFromUTC)}</p>
                <div class="payment-method-container">
                    <div class="payment-method">${paymentDisplay}</div>
                    <button class="edit-payments-btn">Edit</button>
                </div>
                <button class="view-auction" data-id="${safeAuctionId}">View</button>
                <button class="delete-auction" data-id="${safeAuctionId}">Delete</button>
                <div class="auction-link-cell">
                    ${auction.sale_id == null
                    ? `<select class='barter-id-select'><option value="null">Select Invoice Number to link</option></select>`
                    : `<a class="sale-link" href="/sold#${safeSaleId}">Invoice Number: ${DOMPurify.sanitize(invoiceNumber)}</a>`
                }
                </div>
                <div class="cards-container">
                    <!-- Cards will be loaded here -->
                </div>
            `;
            auctionContainer.appendChild(auctionDiv);

            // Store payments data on the div for la
            auctionDiv.paymentsData = payments;

        });

        const barterSelects = document.querySelectorAll('.barter-id-select');
        barterSelects.forEach((select) => {
            select.addEventListener('focus', () => {
                renderBarterSelect(select);
            });
            select.addEventListener('change', async (event) => {
                const auctionDiv = event.target.closest('.auction-tab');
                const auctionId = auctionDiv.getAttribute('data-id');
                const selected = event.target.value;
                if (selected === 'null') return;
                try {
                    const res = await fetch(`/linkAuctionToSale/${auctionId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ 'sale_id': selected })
                    });
                    const data = await res.json()
                    if (data.status === 'success') {
                        console.log('success')
                    }
                } catch (err) {
                    renderAlert('There was an error' + err, 'error')
                }

            });
        });

        // Handle payment editing - define as named function to allow re-attachment
        const handleEditPayment = (event) => {
            const auctionDiv = event.target.closest('.auction-tab');
            const auctionId = auctionDiv.getAttribute('data-id');
            const paymentContainer = auctionDiv.querySelector('.payment-method-container');
            const payments = auctionDiv.paymentsData || [];

            // Clear container and create payment editor
            paymentContainer.innerHTML = '<div class="payment-rows-container"></div>';
            const rowsContainer = paymentContainer.querySelector('.payment-rows-container');

            // Add existing payments
            if (payments.length > 0) {
                payments.forEach(payment => {
                    rowsContainer.innerHTML += paymentTypeRow(DOMPurify.sanitize(payment.type), DOMPurify.sanitize(payment.amount));
                });
            } else {
                // Add one empty row if no payments
                const auctionPrice = DOMPurify.sanitize(auctionDiv.querySelector('.auction-price').textContent.replace('€', ''));
                rowsContainer.innerHTML += paymentTypeRow('Bankový prevod', auctionPrice);
            }

            // Add control buttons (create elements instead of innerHTML to preserve rowsContainer reference)
            const buttonsDiv = document.createElement('div');
            buttonsDiv.classList.add('payment-buttons-container');
            buttonsDiv.innerHTML = `
                <button class="add-payment-row-btn">+</button>
                <button class="save-payments-btn">Save</button>
                <button class="cancel-payments-btn">Cancel</button>
            `;
            paymentContainer.appendChild(buttonsDiv);

            // Attach remove button listeners
            const attachRemoveListeners = () => {
                const removeButtons = rowsContainer.querySelectorAll('.remove-payment-btn');
                removeButtons.forEach(btn => {
                    btn.onclick = () => {
                        if (rowsContainer.children.length > 1) {
                            btn.closest('.payment-row').remove();
                        } else {
                            renderAlert('At least one payment row is required', 'error');
                        }
                    };
                });
            };
            attachRemoveListeners();

            // Add payment row button
            paymentContainer.querySelector('.add-payment-row-btn').addEventListener('click', () => {
                rowsContainer.innerHTML += paymentTypeRow();
                attachRemoveListeners();
            });

            // Save button
            paymentContainer.querySelector('.save-payments-btn').addEventListener('click', async () => {
                const paymentRows = rowsContainer.querySelectorAll('.payment-row');
                const paymentsArray = [];
                let hasEmptyType = false;

                paymentRows.forEach(row => {
                    const type = row.querySelector('.payment-type-select').value;
                    const amount = parseFloat(row.querySelector('.payment-amount-input').value) || 0;

                    if (!type || type.trim() === '') {
                        hasEmptyType = true;
                    } else {
                        paymentsArray.push({ type, amount });
                    }
                });

                if (hasEmptyType && paymentsArray.length === 0) {
                    renderAlert('Please select at least one payment type', 'error');
                    return;
                }

                // Validate payments
                const validation = validatePayments(paymentsArray);
                if (!validation.valid) {
                    renderAlert(validation.error, 'error');
                    return;
                }

                const success = await updatePaymentMethod(auctionId, paymentsArray);
                if (success) {
                    // Update display
                    auctionDiv.paymentsData = paymentsArray;
                    const paymentDisplay = formatPaymentDisplay(paymentsArray);
                    paymentContainer.innerHTML = `
                        <div class="payment-method">${DOMPurify.sanitize(paymentDisplay)}</div>
                        <button class="edit-payments-btn">Edit</button>
                    `;
                    // Re-attach listener to new edit button
                    paymentContainer.querySelector('.edit-payments-btn').addEventListener('click', handleEditPayment);
                } else {
                    renderAlert('Failed to update payment methods. Please try again.', 'error');
                }
            });

            // Cancel button
            paymentContainer.querySelector('.cancel-payments-btn').addEventListener('click', () => {
                const paymentDisplay = formatPaymentDisplay(auctionDiv.paymentsData || []);
                paymentContainer.innerHTML = `
                    <div class="payment-method">${DOMPurify.sanitize(paymentDisplay)}</div>
                    <button class="edit-payments-btn">Edit</button>
                `;
                // Re-attach listener to new edit button
                paymentContainer.querySelector('.edit-payments-btn').addEventListener('click', handleEditPayment);
            });
        };

        const editPaymentButtons = document.querySelectorAll('.edit-payments-btn');
        editPaymentButtons.forEach((button) => {
            button.addEventListener('click', handleEditPayment);
        });

        const auctionPriceInputs = document.querySelectorAll('input.auction-price');
        auctionPriceInputs.forEach(input => {
            input.addEventListener('blur', (event) => {
                const value = event.target.value.replace(',', '.');
                const auctionDiv = event.target.closest('.auction-tab');
                const auctionId = auctionDiv.getAttribute('data-id');
                if (!Boolean(value)) {
                    return;
                }
                updateAuction(auctionId, value, 'auction_price');
                const p = document.createElement('p');
                p.classList.add('auction-price');
                p.textContent = appendEuroSign(value, 'auction_price');
                event.target.replaceWith(p);


            })
            input.addEventListener('keydown', (event) => {
                if (event.key == 'Enter') {
                    input.blur();
                }
            })
        })

        const attachAuctionNameListener = (name) => {
            if (name.textContent === 'Singles') {
                return;
            }
            name.addEventListener('dblclick', (event) => {
                const value = event.target.textContent.replace('€', '');
                const input = document.createElement('input');
                input.type = 'text';
                input.value = value;
                input.classList.add(...event.target.classList);
                event.target.replaceWith(input);
                input.focus();
                input.addEventListener('blur', (blurEvent) => {
                    const value = blurEvent.target.value;
                    const auctionDiv = blurEvent.target.closest('.auction-tab');
                    const auctionId = auctionDiv.getAttribute('data-id');
                    if (!Boolean(value)) {
                        return;
                    }
                    updateAuction(auctionId, value, 'auction_name');
                    const p = document.createElement('p');
                    p.classList.add('auction-name');
                    p.textContent = value;
                    blurEvent.target.replaceWith(p);
                    attachAuctionNameListener(p);
                })
                input.addEventListener('keydown', (keyEvent) => {
                    if (keyEvent.key == 'Enter') {
                        input.blur();
                    }
                });
            });
        };

        const auctionNames = document.querySelectorAll('.auction-name');
        auctionNames.forEach(name => attachAuctionNameListener(name));

        const attachAuctionPriceListener = (price) => {
            price.addEventListener('dblclick', (event) => {
                const value = event.target.textContent.replace('€', '');
                const input = document.createElement('input');
                input.type = 'text';
                input.value = value;
                input.classList.add(...event.target.classList);
                event.target.replaceWith(input);
                input.focus();
                input.addEventListener('blur', async (blurEvent) => {
                    let value = blurEvent.target.value.replace(',', '.');
                    if (isNaN(value)) {
                        value = value.toUpperCase();
                    }
                    const auctionDiv = blurEvent.target.closest('.auction-tab');
                    const auctionId = auctionDiv.getAttribute('data-id');
                    if (!Boolean(value)) {
                        return;
                    }
                    await updateAuction(auctionId, value, 'auction_price');
                    const p = document.createElement('p');
                    p.classList.add('auction-price');
                    p.textContent = appendEuroSign(value, 'auction_price');
                    blurEvent.target.replaceWith(p);
                    changeCardPricesBasedOnAuctionPrice(auctionDiv);
                    attachAuctionPriceListener(p);
                })
                input.addEventListener('keydown', (keyEvent) => {
                    if (keyEvent.key == 'Enter') {
                        input.blur();
                    }
                })
            });
        };

        const auctionPrices = document.querySelectorAll('.auction-price');
        auctionPrices.forEach(price => attachAuctionPriceListener(price));

        //Attach event listener for changing date
        const auctionDateListener = (date) => {
            date.addEventListener('dblclick', (event) => {
                const currValue = event.target.textContent;
                const input = document.createElement('INPUT');
                input.type = 'date';
                const maxDate = new Date().toISOString().split("T")[0];
                input.max = `${maxDate}`;
                const [day, month, year] = currValue.split(". ").map(s => s.trim());
                const dateValue = `${year}-${month}-${day}`;
                input.value = dateValue;
                input.classList.add(...event.target.classList);
                event.target.replaceWith(input);
                input.focus();

                input.addEventListener('blur', async (blurEvent) => {
                    let value = blurEvent.target.value;
                    const auctionDiv = blurEvent.target.closest('.auction-tab');
                    const auctionId = auctionDiv.getAttribute('data-id');
                    if (!Boolean(value)) {
                        return;
                    }
                    await updateAuction(auctionId, value, 'date_created');
                    const p = document.createElement('p');

                    value = new Date(value);
                    let formatedDate = value.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
                    p.textContent = formatedDate;
                    p.classList.add('buy-date');
                    blurEvent.target.replaceWith(p);
                    auctionDateListener(p);
                });
                input.addEventListener('keydown', (keyEvent) => {
                    if (keyEvent.key === 'Enter') {
                        input.blur();
                    }
                })
            });
        }

        const dateElements = document.querySelectorAll('.buy-date');
        dateElements.forEach(date => auctionDateListener(date));
        // Attach event listeners after auctions are loaded
        const viewButtons = document.querySelectorAll('.view-auction');
        viewButtons.forEach(button => {
            button.addEventListener('click', () => loadAuctionContent(button));
        });

        const auctionsTabs = document.querySelectorAll('.auction-tab');
        auctionsTabs.forEach(tab => {
            tab.addEventListener('click', async (event) => {
                // Only trigger if the click is on the tab itself, not its children
                if (event.target === tab) {
                    const viewButton = tab.querySelector('.view-auction');
                    if (viewButton) {
                        loadAuctionContent(viewButton);
                    }
                }
            });
        });


        //TODO - investigate if this does something, look like not
        const auctionTab = document.querySelectorAll('.auction-tab');
        auctionTab.forEach((tab) => {
            const paymentMethodSelects = tab.querySelectorAll('.payment-method-select');
            if (paymentMethodSelects) {
                paymentMethodSelects.forEach(select => {
                    attachPaymentMethodSelectListener(select);
                });

            }
        });


        const deleteButton = document.querySelectorAll('.delete-auction');
        deleteButton.forEach(button => {
            button.addEventListener('click', () => {
                const auctionId = button.getAttribute('data-id');
                if (auctionId != 1) {
                    if (button.textContent === 'Confirm') {
                        const auctionDiv = button.closest('.auction-tab');
                        deleteAuction(auctionId, auctionDiv);
                        updateInventoryValueAndTotalProfit()
                    } else {
                        button.textContent = 'Confirm';
                        const timerID = setTimeout(() => {
                            button.textContent = 'Delete';
                        }, 3000);
                        // Remove confirmation if user clicks elsewhere
                        document.addEventListener('click', function handler(e) {
                            if (e.target !== button) {
                                button.textContent = 'Delete';
                                document.removeEventListener('click', handler);
                                clearTimeout(timerID);
                            }
                        });
                    }

                }
            });
        });
    } catch (error) {
        renderAlert('Error loading auctions: ' + error, 'error');
    }
}

if (document.title === "Trade Tracker") {
    searchBar();
    loadAuctions();
    initializeSealed();
    importCSV();
    soldReportBtn();
    initializeCart();
    initializeBulkHolo();
    loadCartContentFromSession();
    scrollOnLoad();
    document.addEventListener('DOMContentLoaded', async () => {
        await updateInventoryValueAndTotalProfit();
    }, false);
    startPolling();
}
