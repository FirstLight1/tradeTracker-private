import { renderField, renderAlert, renderServerErrors, clearFieldErrors, scrollOnLoad, replaceWithPElement, getInventoryValue, updateInventoryValueAndTotalProfit, appendEuroSign, downloadFile, createNewItem } from "./utils/renderUtil.js";
import { CardStruct, queue, CartLine } from "./utils/classes.js";
import { escapeHtml, sanitizePlainText, sanitizeAttrValue, sanitizeNumericId, sanitizeClassToken, csrfFetch } from "./utils/sanitizers.js";
import { searchCard } from "./utils/searchApi.js";
import "./headerActions.js";


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

function languageSelect(className = 'language-select', dataField = '', defaultValue = 'en') {
    const dataAttribute = dataField ? ` data-field="${dataField}"` : '';
    const selectedValue = String(defaultValue || 'en').toLowerCase();
    return `
    <select class="${className}"${dataAttribute}>
        <option value="en" ${selectedValue === 'en' ? 'selected' : ''}>English</option>
        <option value="jp" ${selectedValue === 'jp' ? 'selected' : ''}>Japanese</option>
        <option value="de" ${selectedValue === 'de' ? 'selected' : ''}>German</option>
        <option value="fr" ${selectedValue === 'fr' ? 'selected' : ''}>French</option>
        <option value="it" ${selectedValue === 'it' ? 'selected' : ''}>Italian</option>
        <option value="es" ${selectedValue === 'es' ? 'selected' : ''}>Spanish</option>
        <option value="kr" ${selectedValue === 'kr' ? 'selected' : ''}>Korean</option>
        <option value="cn" ${selectedValue === 'cn' ? 'selected' : ''}>Chinese</option>
        <option value="pt" ${selectedValue === 'pt' ? 'selected' : ''}>Portuguese</option>
    </select>`;
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
        const response = await csrfFetch(`/updatePaymentMethod/${auctionId}`, {
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

function getInputValueAndPatch(value, element, dataset, cardId) {
    if (!Boolean(value)) {
        return null;
    }
    replaceWithPElement(dataset, value, element);
    patchValue(cardId, value, dataset);
}

async function patchValue(id, value, dataset) {
    if (value === " ") {
        value = null;
    }
    if (!value === null || !value === undefined) {
        value = String(value);
        value = value.replace('€', '');

    }
    try {
        const response = await csrfFetch(`/update/${id}`, {
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
        renderAlert('Error updating value: ' + e + 'Error code: Mx01', 'error');
    }
}

async function patchSealedLanguage(sid, language) {
    try {
        const response = await csrfFetch(`/updateSealed/${sid}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: 'language', value: language })
        });
        const data = await response.json();
        if (response.ok && data.status === 'success') return true;
        renderAlert('Failed to update sealed language', 'error');
    } catch (error) {
        renderAlert('Error updating sealed language: ' + error, 'error');
    }
    return false;
}

function enableSealedLanguageEditing(sealedDiv) {
    sealedDiv.addEventListener('dblclick', (event) => {
        if (!event.target.classList.contains('sealed-language')) return;
        event.preventDefault();
        event.stopPropagation();

        const languageElement = event.target;
        const previousValue = languageElement.textContent.trim() || 'en';
        const container = document.createElement('div');
        container.innerHTML = languageSelect('sealed-language-select', '', previousValue);
        const select = container.firstElementChild;
        languageElement.replaceWith(select);
        select.focus();

        let saving = false;
        let finished = false;
        const finishEditing = (value) => {
            if (finished) return;
            finished = true;
            const replacement = document.createElement('p');
            replacement.classList.add('sealed-language');
            replacement.textContent = value;
            select.replaceWith(replacement);
        };

        select.addEventListener('click', (selectEvent) => selectEvent.stopPropagation());
        select.addEventListener('change', async () => {
            saving = true;
            select.disabled = true;
            const selectedValue = select.value;
            const saved = await patchSealedLanguage(sealedDiv.getAttribute('sid'), selectedValue);
            finishEditing(saved ? selectedValue : previousValue);
        }, { once: true });
        select.addEventListener('blur', () => {
            if (!saving) finishEditing(previousValue);
        });
        select.addEventListener('keydown', (keyEvent) => {
            if (keyEvent.key === 'Escape') finishEditing(previousValue);
        });
    });
}

function deleteAuction(id, div) {
    csrfFetch(`/deleteAuction/${id}`, {
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

async function removeCard(id, div) {
    try {
        const response = await csrfFetch(`/deleteCard/${id}`, {
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
        renderAlert('Error deleting card: ' + error + 'Error code: Mx02', 'error');
        return false;
    }
}

async function removeBulkItem(bulkId, bulkDiv) {
    try {
        const response = await csrfFetch(`/deleteBulkItem/${bulkId}`, {
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
        renderAlert('Error deleting bulk item: ' + error + 'Mx03', 'error');
        return false;
    }
}

async function updateAuction(auctionId, value, field) {
    try {
        const response = await csrfFetch(`/updateAuction/${auctionId}`, {
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
        renderAlert('Error updating auction: ' + error + 'Mx04', 'error');
        return
    }
}

function isEmpty(obj) {
    return Object.keys(obj).length === 0;
}

function createSealedItemRow() {
    const itemDiv = document.createElement('div');
    itemDiv.classList.add('sealed-item-row');
    itemDiv.innerHTML = `
    <input type="text" class="sealed-name-input" placeholder="item name">
    <input type="text" class="sealed-number-input" placeholder="item number">
    <select class="sealed-condition-select">
        <option value="MINT">Mint</option>
        <option value="NEAR MINT" selected="selected">Near Mint</option>
        <option value="EXCELLENT">Excellent</option>
        <option value="GOOD">Good</option>
        <option value="LIGHT PLAYED">Light Played</option>
        <option value="PLAYED">Played</option>
        <option value="POOR">Poor</option>
    </select>
    ${languageSelect('sealed-language-select')}
    <input type="text" class="sealed-price-input" placeholder="price">
    <input type="text" class="sealed-market-value-input" placeholder="market value">
    `;
    return itemDiv;
}

function createSealedModal(sid, auctionId, initialValue, sourceName, sourceLanguage) {
    const modal = document.createElement('div');
    modal.classList.add('reciever-div');
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('modal-content', 'sealed-modal');
    const buttonDiv = document.createElement('div');
    buttonDiv.classList.add('modal-buttons');

    const closeButton = document.createElement('span');
    closeButton.classList.add('close-modal');
    closeButton.innerHTML = '&times;';
    contentDiv.appendChild(closeButton);

    const sourceContext = document.createElement('p');
    sourceContext.classList.add('sealed-source-context');
    sourceContext.textContent = `Opening ${sourceName} (${sourceLanguage || 'en'})`;
    contentDiv.appendChild(sourceContext);

    const rowsContainer = document.createElement('div');
    rowsContainer.classList.add('sealed-rows-container');
    contentDiv.appendChild(rowsContainer);

    const firstRow = createSealedItemRow();
    rowsContainer.append(firstRow);
    createNewItem(firstRow, {
        triggerSelector: '.sealed-market-value-input',
        onTrigger: (el) => window.handleSealedInput(el, rowsContainer)
    });

    const addLineButton = document.createElement('button');
    addLineButton.classList.add('sealed-add-line-btn');
    addLineButton.type = 'button';
    addLineButton.textContent = 'Add new line';
    addLineButton.addEventListener('click', () => {
        const newRow = createSealedItemRow();
        rowsContainer.appendChild(newRow);
        createNewItem(newRow, {
            triggerSelector: '.sealed-market-value-input',
            onTrigger: (el) => window.handleSealedInput(el, rowsContainer)
        });
    });

    const confirmButton = document.createElement('button');
    confirmButton.classList.add('sealed-confirm-btn');
    confirmButton.type = 'button';
    confirmButton.textContent = 'Confirm';
    confirmButton.addEventListener('click', async () => {
        const cards = [];
        const sealed = [];
        rowsContainer.querySelectorAll('.sealed-item-row').forEach(div => {
            const item = new CardStruct();
            item.cardName = DOMPurify.sanitize(div.querySelector('.sealed-name-input').value);
            item.cardNum = DOMPurify.sanitize(div.querySelector('.sealed-number-input').value);
            item.condition = DOMPurify.sanitize(div.querySelector('.sealed-condition-select').value);
            item.language = DOMPurify.sanitize(div.querySelector('.sealed-language-select').value);
            item.buyPrice = Number(DOMPurify.sanitize(div.querySelector('.sealed-price-input').value.replace('€', '')));
            item.marketValue = Number(DOMPurify.sanitize(div.querySelector('.sealed-market-value-input').value.replace('€', '')));
            item.soldDate = null;
            if (item.marketValue == '') return;
            if (item.cardNum !== '') {
                cards.push(item);
            } else {
                sealed.push(item);
            }
        });
        const response = await csrfFetch(`/openSealed/${auctionId ?? 0}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ openedItem: { id: sid, initialValue: initialValue }, sealed: sealed, cards: cards })
        });
        const result = await response.json();
        if (result.status === 'success') {
            modal.remove();
            window.location.reload();
        } else {
            renderAlert(result.message, 'error');
        }
    });

    buttonDiv.append(addLineButton, confirmButton);
    contentDiv.appendChild(buttonDiv);
    modal.appendChild(contentDiv);
    document.body.appendChild(modal);

    const close = () => modal.remove();
    closeButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) close();
    });
}

function gradingModal(cardId) {
    const existingModal = document.querySelector('.grading-modal-overlay');
    if (existingModal) {
        existingModal.querySelector('#grading-grader')?.focus();
        return;
    }

    const restoreFocusTo = document.activeElement;
    const modal = document.createElement('div');
    modal.classList.add('reciever-div', 'grading-modal-overlay');
    modal.dataset.cardId = cardId;
    modal.innerHTML = `
        <form class="modal-content grading-status-modal direct-grading-form" role="dialog" aria-modal="true" aria-labelledby="grading-modal-title" novalidate>
            <button class="close-modal" type="button" aria-label="Close grading modal">&times;</button>
            <p id="grading-modal-title">Grade card</p>
            <div>
                <label for="grading-grader">Grader</label>
                <input id="grading-grader" name="grader" type="text" autocomplete="organization" required>
            </div>
            <div>
                <label for="grading-grade-numeric">Numeric grade</label>
                <input id="grading-grade-numeric" name="grade_numeric" type="number" min="0" max="10" step="0.01" aria-describedby="grading-result-help">
            </div>
            <div>
                <label for="grading-grade-label">Grade label</label>
                <input id="grading-grade-label" name="grade_label" type="text" aria-describedby="grading-result-help">
                <p id="grading-result-help" class="field-help">Enter a numeric grade or a grade label.</p>
            </div>
            <div>
                <label for="grading-qualifier">Qualifier</label>
                <input id="grading-qualifier" name="qualifier" type="text">
            </div>
            <div>
                <label for="grading-cert-number">Certificate number</label>
                <input id="grading-cert-number" name="cert_number" type="text">
            </div>
            <div>
                <label for="grading-market-value">Post-grade market value</label>
                <input id="grading-market-value" name="post_grade_market_value" type="number" min="0" step="0.01">
            </div>
            <div class="modal-buttons">
                <button class="grading-confirm-btn" type="submit">Confirm</button>
            </div>
        </form>
    `;

    document.body.appendChild(modal);

    const closeButton = modal.querySelector('.close-modal');
    const close = () => {
        document.removeEventListener('keydown', handleKeydown);
        modal.remove();
        if (restoreFocusTo?.isConnected) restoreFocusTo.focus();
    };
    const handleKeydown = (event) => {
        if (event.key === 'Escape') close();
    };

    closeButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) close();
    });
    const gradingForm = modal.querySelector('.direct-grading-form');
    const gradeNumeric = modal.querySelector('#grading-grade-numeric');
    const gradeLabel = modal.querySelector('#grading-grade-label');
    gradingForm.addEventListener('submit', async event => {
        event.preventDefault();
        clearFieldErrors(gradingForm);
        const grader = modal.querySelector('#grading-grader');
        const marketValue = modal.querySelector('#grading-market-value');
        const errors = {};
        if (!grader.value.trim()) errors.grader = 'Grader is required.';
        if (!gradeNumeric.value && !gradeLabel.value.trim()) {
            errors.grade_numeric = 'Enter a numeric grade or a grade label.';
        } else if (gradeNumeric.value && !gradeNumeric.validity.valid) {
            errors.grade_numeric = 'Numeric grade must be between 0 and 10.';
        }
        if (marketValue.value && !marketValue.validity.valid) {
            errors.post_grade_market_value = 'Market value must be zero or greater.';
        }
        if (Object.keys(errors).length) {
            renderServerErrors({ errors }, gradingForm, {
                grader: '#grading-grader', grade_numeric: '#grading-grade-numeric',
                post_grade_market_value: '#grading-market-value',
            });
            return;
        }
        const nullableText = (selector) => {
            const value = modal.querySelector(selector).value.trim();
            return value || null;
        };
        const nullableNumber = (selector) => {
            const value = modal.querySelector(selector).value;
            return value === '' ? null : Number(value);
        };
        const confirmButton = modal.querySelector('.grading-confirm-btn');
        confirmButton.disabled = true;
        confirmButton.textContent = 'Saving...';

        try {
            const response = await csrfFetch('/gradeCard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    card_id: Number(modal.dataset.cardId),
                    grader: nullableText('#grading-grader'),
                    grade_numeric: nullableNumber('#grading-grade-numeric'),
                    grade_label: nullableText('#grading-grade-label'),
                    qualifier: nullableText('#grading-qualifier'),
                    cert_number: nullableText('#grading-cert-number'),
                    post_grade_market_value: nullableNumber('#grading-market-value'),
                }),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                renderServerErrors(result, gradingForm, {
                    grader: '#grading-grader', grade_numeric: '#grading-grade-numeric',
                    grade_label: '#grading-grade-label', qualifier: '#grading-qualifier',
                    cert_number: '#grading-cert-number', post_grade_market_value: '#grading-market-value',
                }, 'Unable to save card grading');
                confirmButton.disabled = false;
                confirmButton.textContent = 'Confirm';
                return;
            }
            close();
            window.location.reload();
        } catch (error) {
            renderAlert(`Error saving card grading: ${error}`, 'error');
            confirmButton.disabled = false;
            confirmButton.textContent = 'Confirm';
        }
    });
    document.addEventListener('keydown', handleKeydown);
    modal.querySelector('#grading-grader').focus();
}

function cardConditionDisplay(card) {
    if (card.grading_state === 'at_grader') {
        const statusLabels = {
            preparing: 'Preparing for grading',
            sent_for_grading: 'Sent for grading',
            received_by_grader: 'At grader',
        };
        const status = statusLabels[card.grading_submission_status] || 'At grader';
        return [status, card.grader].filter(Boolean).join(' - ');
    }
    if (card.grading_state === 'graded') {
        const fullGrade = [card.grader, card.grade_numeric, card.grade_label, card.qualifier]
            .filter(value => value !== null && value !== undefined && value !== '')
            .join(' ');
        return fullGrade || 'Graded';
    }
    return card.condition || 'Unknown';
}

window.handleSealedInput = function(input, container) {
    window.handleCardInput(input, {
        itemSelector: '.sealed-item-row',
        container,
        triggerSelector: '.sealed-market-value-input'
    });
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
            sum += Number(item.marketValue) * (Number(item.quantity) || 1);
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
    const response = await csrfFetch(`/recalculateCardPrices/${auctionId}/${auctionPrice}`, { method: 'POST' });
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
        const gradeDisplay = line.grading
            ? [line.grading.grader, line.grading.grade_numeric, line.grading.grade_label, line.grading.qualifier]
                .filter(value => value !== null && value !== undefined && value !== '').join(' ') || 'Graded'
            : line.condition;
        const minusDisabled = line.cardIds.length <= 1 ? 'disabled' : '';
        const plusDisabled = !line.canIncrement ? 'disabled' : '';
        cardDiv.innerHTML = `
            <p class="cart-card-name">${DOMPurify.sanitize(line.cardName)}</p>
            <p class="cart-card-num">${DOMPurify.sanitize(line.cardNum)}</p>
            <p class="cart-condition${line.grading ? ' graded' : ''}">${DOMPurify.sanitize(gradeDisplay)}</p>
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
                language: item.getAttribute('data-language') || 'en',
                marketValue: item.querySelector('.sealed-price').textContent.replace('€', '').replace(',', '.').trim(),
                quantity: item.querySelector('.sealed-qty-display')?.textContent || '1',
                available: item.getAttribute('data-available') || ''
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
            cartData.sealed.forEach(item => {
                // Backward compat: older sessions stored `price` (with €) instead of `marketValue`
                const marketValue = item.marketValue != null
                    ? item.marketValue
                    : (item.price ? item.price.replace('€', '').replace(',', '.').trim() : '');
                addSealedToCart(
                    { name: item.name, language: item.language || 'en', market_value: marketValue },
                    item.sid,
                    item.auctionId || null,
                    Number(item.quantity) || 1,
                    item.available ? Number(item.available) : null
                );
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
                <input type='text' class='bulk-sell-price' value='${DOMPurify.sanitize(cartData.bulk.price)}'>
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
                <input type='text' class='holo-sell-price' value='${DOMPurify.sanitize(cartData.holo.price)}'>
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
                <input type='text' class='ex-sell-price' value='${DOMPurify.sanitize(cartData.ex.price)}'>
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
        renderAlert('Error loading cart data from sessionStorage: ' + e + 'Error code: Mx03', 'error');
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
        clientZip: document.querySelector('.client-zip')?.value || '',
        paybackDate: document.querySelector('.date-input')?.value || '',
        price: document.querySelector('.price-input')?.value || '',
        shippingPrice: document.querySelector('.shipping-price')?.value || '',
        deliveryMethod: document.querySelector('.delivery-method-select')?.value || '',
        parcelCategory: document.querySelector('.parcel-category-select')?.value || '',
        insuranceValue: document.querySelector('.insurance-value-input')?.value || '',
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
        const clientZip = recieverDiv.querySelector('.client-zip');
        const paybackDate = recieverDiv.querySelector('.date-input');
        const priceInput = recieverDiv.querySelector('.price-input');
        const shippingPrice = recieverDiv.querySelector('.shipping-price');

        if (clientName) clientName.value = DOMPurify.sanitize(modalData.clientName);
        if (clientAddress) clientAddress.value = DOMPurify.sanitize(modalData.clientAddress);
        if (clientCity) clientCity.value = DOMPurify.sanitize(modalData.clientCity);
        if (clientCountry) clientCountry.value = DOMPurify.sanitize(modalData.clientCountry);
        if (clientZip) clientZip.value = DOMPurify.sanitize(modalData.clientZip);
        if (paybackDate && modalData.paybackDate) paybackDate.value = DOMPurify.sanitize(modalData.paybackDate);
        if (priceInput) priceInput.value = DOMPurify.sanitize(modalData.price);
        if (shippingPrice) shippingPrice.value = DOMPurify.sanitize(modalData.shippingPrice);

        // Restore delivery method and conditional parcel/insurance fields
        const deliveryMethodSelect = recieverDiv.querySelector('.delivery-method-select');
        if (deliveryMethodSelect && modalData.deliveryMethod) {
            deliveryMethodSelect.value = DOMPurify.sanitize(modalData.deliveryMethod);
            if (modalData.deliveryMethod === 'SK-post') {
                const deliveryMethodInfo = recieverDiv.querySelector('.delivery-method-info');
                if (deliveryMethodInfo) {
                    deliveryMethodInfo.innerHTML = `
                    <select class="parcel-category-select">
                        <option value=''>Parcel category</option>
                        <option value='r'>Registered letter</option>
                        <option value='olz'>Letter</option>
                        <option value='pl'>Insured letter</option>
                        <option value='b'>Packet</option>
                    </select>
                    <input type='number' placeholder="Insurance value" class="insurance-value-input">
                    `;
                    const parcelCategorySelect = deliveryMethodInfo.querySelector('.parcel-category-select');
                    const insuranceValueInput = deliveryMethodInfo.querySelector('.insurance-value-input');
                    if (parcelCategorySelect && modalData.parcelCategory) {
                        parcelCategorySelect.value = DOMPurify.sanitize(modalData.parcelCategory);
                    }
                    if (insuranceValueInput && modalData.insuranceValue) {
                        insuranceValueInput.value = DOMPurify.sanitize(modalData.insuranceValue);
                    }
                    const newInputs = deliveryMethodInfo.querySelectorAll('input, select');
                    newInputs.forEach(input => {
                        input.addEventListener('input', saveModalDataToSession);
                        input.addEventListener('change', saveModalDataToSession);
                    });
                }
            }
        }

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
        renderAlert('Error loading modal data from sessionStorage: ' + e + 'Error code: Mx05', 'error');
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

async function collectModalData(recieverDiv, cartVal, cartContent, kind) {
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
    const clientZip = DOMPurify.sanitize(recieverDiv.querySelector('.client-zip')?.value) || '';
    const paybackDate = DOMPurify.sanitize(recieverDiv.querySelector('.date-input')?.value) || '';
    const shippingWay = 'Doprava / Poštovné – samostatná služba';
    const shippingPrice = DOMPurify.sanitize(recieverDiv.querySelector('.shipping-price')?.value.replace(',', '.')) || '';
    const deliveryMethod = DOMPurify.sanitize(recieverDiv.querySelector('.delivery-method-select')?.value) || '';
    const parcelCategory = DOMPurify.sanitize(recieverDiv.querySelector('.parcel-category-select')?.value) || '';
    const insuranceValue = DOMPurify.sanitize(recieverDiv.querySelector('.insurance-value-input')?.value) || '';

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
        renderAlert('Please select at least one payment method, Error code: Mx06', 'error');
        return;
    }
    cartContent.paymentMethods = paymentMethods;
    // ZIP is only collected/required when the recipient country is Slovakia
    const isSlovakia = ['slovakia', 'sk', 'slovensko'].includes(clientCountry.trim().toLowerCase());
    if (isSlovakia) {
        if (!clientZip.trim()) {
            renderAlert('ZIP / postal code is required for Slovakia, Error code: Mx07', 'error');
            return;
        }
    }
    // Update or create recieverInfo (always update payment methods)
    const recieverInfo = {
        nameAndSurname: clientName,
        address: clientAddress,
        city: clientCity,
        state: clientCountry,
        paybackDate: paybackDate,
        total: null,
    };
    if (isSlovakia) {
        recieverInfo.zip = clientZip;
    }
    cartContent.recieverInfo = recieverInfo;

    if (shippingPrice !== "") {
        const shipping = {
            shippingWay: shippingWay,
            shippingPrice: shippingPrice.replace(',', '.'),
        };
        cartContent.shipping = shipping;
    }

    if (deliveryMethod) {
        const delivery = {
            deliveryMethod: deliveryMethod,
            parcelCategory: parcelCategory,
            insuranceValue: insuranceValue
        };
        cartContent.delivery = delivery;
    }

    // Apply price adjustment if cart value was manually changed
    if (cartValueInput != cartVal) {
        const bulkSub = cartContent.bulkItem ? Number(cartContent.bulkItem.sell_price) : 0;
        const holoSub = cartContent.holoItem ? Number(cartContent.holoItem.sell_price) : 0;
        const exSub = cartContent.exItem ? Number(cartContent.exItem.sell_price) : 0;
        const fixedSubtotal = bulkSub + holoSub + exSub;
        const cardsSub = cartContent.cards ? cartContent.cards.reduce((sum, c) => sum + Number(c.marketValue), 0) : 0;
        const sealedSub = cartContent.sealed ? cartContent.sealed.reduce(
            (sum, item) => sum + Number(String(item.marketValue).replace('€', '')) * (Number(item.quantity) || 1),
            0
        ) : 0;

        const adjustableSubtotal = cardsSub + sealedSub;
        const targetAdjustable = cartValueInput - fixedSubtotal;

        if (adjustableSubtotal > 0) {
            const scale = targetAdjustable / adjustableSubtotal;
            const allItems = [
                ...(cartContent.cards || []).map(item => ({ item, quantity: 1 })),
                ...(cartContent.sealed || []).map(item => ({ item, quantity: Number(item.quantity) || 1 }))
            ];

            let distributed = 0;
            for (let i = 0; i < allItems.length; i++) {
                const { item, quantity } = allItems[i];
                if (i === allItems.length - 1) {
                    item.marketValue = ((targetAdjustable - distributed) / quantity).toFixed(2);
                } else {
                    const scaled = parseFloat((Number(item.marketValue) * scale).toFixed(2));
                    item.marketValue = scaled.toFixed(2);
                    distributed += scaled * quantity;
                }
            }
        }
    }
    cartContent.recieverInfo.total = Number(cartValue(cartContent));
    if (Object.keys(cartContent).length !== 0) {
        const response = await csrfFetch(`/createSale/${kind}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(cartContent),
            });

        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            const err = await response.json();
            renderAlert('Error: ' + (err.message || 'Unknown error'), 'error');
            return false;
        }
        try {
            downloadFile(response)
            return true;
        } catch (e) {
            renderAlert('Error: ' + e, 'error');
        }
    }
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

                const sealedData = {
                    sid: sid,
                    auctionId: auctionId,
                    sealedName: item.querySelector('.sealed-name')?.textContent || '',
                    language: item.getAttribute('data-language') || 'en',
                    marketValue: item.querySelector('.sealed-price')?.textContent.replace('€', '').replace(',', '.').trim() || '',
                    quantity: Number(item.querySelector('.sealed-qty-display')?.textContent) || 1
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
                    <div class='zip-div'>
                        <p>ZIP <span class='zip-optional-label'>(Slovakia only)</span></p>
                        <input type='text' class='client-zip'>
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
                    <p class='shipping-way'>Doprava / Poštovné – samostatná služba</p>
                    <input type=text placeholder="Price of shipping" class="shipping-price">
                    </div>
                    <div>
                        <select class="delivery-method-select">
                            <option value="">Delivery method</option>
                            <option value="SK-post">Slovak post</option>
                        </select>
                        <div class="delivery-method-info">
                    </div>
                    <div class='invoice-buttons'>
                        <button class=sales-invoice>Add sale</button>
                        <button class="generate-invoice">Generate Invoice</button>
                    </div>
                </div>
                `;
            body.append(recieverDiv);

            // Load saved data from sessionStorage if exists
            loadModalDataFromSession(recieverDiv);

            const deliveryMethodSelect = recieverDiv.querySelector('.delivery-method-select');
            deliveryMethodSelect.addEventListener('change', () => {
                const selected = deliveryMethodSelect.value;
                const deliveryMethodInfo = recieverDiv.querySelector('.delivery-method-info');
                if (selected === 'SK-post') {
                    deliveryMethodInfo.innerHTML = `
                    <select class="parcel-category-select">
                        <option value=''>Parcel category</option>
                        <option value='r'>Registered letter</option>
                        <option value='olz'>Letter</option>
                        <option value='pl'>Insured letter</option>
                        <option value='b'>Packet</option>
                    </select>
                    <input type='number' placeholder="Insurance value" class="insurance-value-input">
                    `;
                    const newInputs = deliveryMethodInfo.querySelectorAll('input, select');
                    newInputs.forEach(input => {
                        input.addEventListener('input', saveModalDataToSession);
                        input.addEventListener('change', saveModalDataToSession);
                    });
                } else {
                    deliveryMethodInfo.innerHTML = '';
                }
                saveModalDataToSession();
            });

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
        generateInvoiceBtn.addEventListener('click', () => {
            const success = collectModalData(recieverDiv, cartVal, cartContent, 'invoice');
            if (success) {
                cards = [];
                for (const key in cartContent) {
                    delete cartContent[key];
                }
                deleteCartContent(contentDiv, bulkCartContent, holoCartContent, exCartContent, sealedContent, recieverDiv)
                loadBulkHoloValues();

                // Clear sessionStorage on successful invoice generation
                clearModalDataFromSession();
                removeCartContentFromSession();
            }
        });

        const salesInvoiceBtn = document.querySelector('.sales-invoice');
        salesInvoiceBtn.addEventListener('click', () => {
            const success = collectModalData(recieverDiv, cartVal, cartContent, 'sales_invoice');
            if (success) {
                cards = [];
                for (const key in cartContent) {
                    delete cartContent[key];
                }
                deleteCartContent(contentDiv, bulkCartContent, holoCartContent, exCartContent, sealedContent, recieverDiv)
                loadBulkHoloValues();

                // Clear sessionStorage on successful invoice generation
                clearModalDataFromSession();
                removeCartContentFromSession();
            }
        });
    });
}

async function addToShoppingCart(card, auctionId, cardId = null) {
    // Entry B: From auction tab (cardId provided)
    if (cardId !== null) {
        if (existingIDs.has(cardId)) {
            renderAlert('This card is already in cart, Error code: Mx07', 'error');
            return;
        }

        // Check if a matching CartLine already exists
        const existing = cartLines.find(l => l.matches(card.cardName, card.cardNum, card.condition, card.grading));
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
                [cardId], card.grading
            );
            cartLines.push(line);
            existingIDs.add(cardId);
            renderCartLine(line);
        }
        return;
    }

    // Entry A: From search results (no cardId)
    const existing = cartLines.find(l => l.matches(card.cardName, card.cardNum, card.condition, card.grading));
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
            renderAlert('No more available copies of this card, Error code: Mx09', 'error');
        }
        return;
    }

    // No existing line — fetch full pool from server
    try {
        const response = await csrfFetch('/getCardIds', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_name: card.cardName,
                card_num: card.cardNum,
                condition: card.condition,
                is_graded: card.grading !== null,
                ...card.grading,
                exclude_ids: [...existingIDs]
            })
        });
        if (!response.ok) {
            renderAlert('Failed to fetch card IDs, Mx10', 'error');
            return;
        }
        const data = await response.json();
        if (data.status !== 'success' || !data.card_ids || data.card_ids.length === 0) {
            renderAlert('Card no longer available, Error code: Mx11', 'error');
            return;
        }
        const line = new CartLine(
            card.cardName, card.cardNum, card.condition,
            card.auctionName || '', card.marketValue || '',
            data.card_ids, card.grading
        );
        cartLines.push(line);
        existingIDs.add(line.cardIds[0]);
        renderCartLine(line);
    } catch (e) {
        renderAlert('Error adding card to cart: ' + e + 'Mx12', 'error');
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

function addSealedToCart(sealed, sid, auctionId = null, quantity = 1, available = null) {
    if (!existingIDs.has(sid)) {
        existingIDs.add(sid);
        const sealedDiv = document.querySelector('.sealed-content');
        const itemDiv = document.createElement('div');
        itemDiv.setAttribute('sid', sid);
        itemDiv.classList.add('sealed-item-cart');
        const language = sealed.language || 'en';
        itemDiv.setAttribute('data-language', language);
        if (auctionId != null) {
            itemDiv.setAttribute('auction_id', auctionId)
        }

        const max = Number(available) > 0 ? Number(available) : (Number(quantity) || 1);
        let qty = Math.min(Math.max(Number(quantity) || 1, 1), max);
        itemDiv.setAttribute('data-available', max);

        const renderSealed = () => {
            const minusDisabled = qty <= 1 ? 'disabled' : '';
            const plusDisabled = qty >= max ? 'disabled' : '';
            itemDiv.innerHTML = `
            <p class='sealed-name'>${DOMPurify.sanitize(sealed.name)}</p>
            <p class='sealed-language'>${DOMPurify.sanitize(language)}</p>
            <p class='sealed-price'>${DOMPurify.sanitize(sealed.market_value)}€</p>
            <div class="qty-controls">
                <button class="sealed-qty-minus" ${minusDisabled}>-</button>
                <span class="sealed-qty-display">${qty}</span>
                <button class="sealed-qty-plus" ${plusDisabled}>+</button>
            </div>
            <button class='remove-from-cart'>Remove</button>
            `;

            itemDiv.querySelector('.sealed-qty-minus').addEventListener('click', () => {
                if (qty > 1) { qty--; renderSealed(); saveCartContentToSession(); }
            });
            itemDiv.querySelector('.sealed-qty-plus').addEventListener('click', () => {
                if (qty < max) { qty++; renderSealed(); saveCartContentToSession(); }
            });
            itemDiv.querySelector('.remove-from-cart').addEventListener('click', () => {
                existingIDs.delete(sid);
                itemDiv.remove();
                saveCartContentToSession();
            });
        };

        renderSealed();
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
            renderAlert(`You can not add more than ${maxBulk} bulk items to the cart, Error code: Mx13`, 'error');
            return;
        }

        if (!bulkItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('bulk-cart-item-bulk');
                div.innerHTML = `
                    <p>Bulk</p>
                    <p class='bulk-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='bulk-sell-price'>
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
            renderAlert(`You can not add more than ${maxHolo} holo items to the cart, Error code: Mx14`, 'error');
            return;
        }

        if (!holoItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('holo-cart-item-holo');
                div.innerHTML = `
                    <p>Holo</p>
                    <p class='holo-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='holo-sell-price'>
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
            renderAlert(`You can not add more than ${maxEx} ex items to the cart, Error code: Mx15`, 'error');
            return;
        }

        if (!exItems) {
            if (value && !isNaN(value)) {
                const div = document.createElement('div');
                div.classList.add('ex-cart-item-ex');
                div.innerHTML = `
                    <p>Ex</p>
                    <p class='ex-quantity'>q: ${DOMPurify.sanitize(value)}</p>
                    <input type='text' class='ex-sell-price'>
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
            const response = await csrfFetch('/getLatest');
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
                    if (sealedIds.length === 0 || sealedIds.every(id => id == null)) {
                        spawnMissingIdModal(item);
                        return;
                    }
                    const qty = Number(item.quantity) || item.count || 1;
                    const available = item.available != null ? Number(item.available) : null;
                    addSealedToCart({ name: item.name, language: item.language || 'en', market_value: item.market_value }, sealedIds[0], null, qty, available);
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
            results = await searchCard(searchInput.value, [...existingIDs]);
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
        results = await searchCard(searchInput.value.trim(), [...existingIDs]);
        const resultsQueue = new queue(results.length + 1);
        resultsQueue.enqueue(searchInput)
        displaySearchResults(results, resultsQueue);
        searchInput.focus();
        addResultScrollingWithArrows(searchInput, resultsQueue);
    });
}

function displaySearchResults(results, resultsQueue, searchInput) {

    const searchContainer = document.querySelector('.search-results');
    searchContainer.innerHTML = ''; // Clear previous results

    if (!results) {
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
            div.classList.add('sealed-search-result');
            const sealed = {
                name: result.name,
                language: result.language || 'en',
                market_value: result.market_value
            };

            div.innerHTML = `
                <p class="result result-sealed-name">${DOMPurify.sanitize(result.name || 'N/A')}</p>
                <p class="result result-language">${DOMPurify.sanitize(result.language || 'en')}</p>
                <p class="result result-market-value">${DOMPurify.sanitize(result.market_value ? result.market_value + '€' : 'N/A')}</p>
                <span class="result-type-badge sealed-badge">Sealed${result.available_count ? ' ·' + result.available_count : ''}</span>
                <p class="result result-auction-name">${DOMPurify.sanitize(result.auction_name || (result.auction_id ? result.auction_id - 1 : 'Unassigned'))}</p>
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
                const available = result.available_count != null ? Number(result.available_count) : null;
                addSealedToCart(sealed, result.sid, result.auction_id, 1, available);
                searchContainer.innerHTML = '';
            });

        } else {
            // Handle card display
            div.classList.add('card-search-result');
            let card = new CardStruct();
            card.cardName = result.card_name;
            card.cardNum = result.card_num;
            card.condition = result.condition;
            card.language = result.language || 'en';
            card.marketValue = result.market_value;
            card.grading = result.is_graded ? {
                grader: result.grader,
                grade_numeric: result.grade_numeric != null ? String(result.grade_numeric) : null,
                grade_label: result.grade_label,
                qualifier: result.qualifier,
                cert_number: result.cert_number,
            } : null;
            const safeConditionClass = sanitizeClassToken(result.condition || 'Unknown');
            const gradeDisplay = card.grading
                ? [result.grader, result.grade_numeric, result.grade_label, result.qualifier]
                    .filter(value => value !== null && value !== undefined && value !== '').join(' ') || 'Graded'
                : result.condition || 'Unknown';

            const availableCount = result.available_count ? result.available_count : 1;
            let pendingQty = 1;

            // Display in desired order, with proper formatting
            div.innerHTML = `
                <p class="result result-card-name">${DOMPurify.sanitize(result.card_name || 'N/A')}</p>
                <p class="result result-card-num">${DOMPurify.sanitize(result.card_num || 'N/A')}</p>
                <p class="result result-condition ${safeConditionClass}${card.grading ? ' graded' : ''}">
                    ${DOMPurify.sanitize(gradeDisplay)}
                </p>
                <p class="result result-language">${DOMPurify.sanitize(result.language || 'N/A')}</p>
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
        const response = await csrfFetch('/bulkCounterValue');
        const data = await response.json();
        if (data.status == 'success') {
            bulkVal.textContent = data.bulk_counter;
            holoVal.textContent = data.holo_counter;
            exVal.textContent = data.ex_counter;
        } else {
            renderAlert('There was a problem loading bulk, holo and ex values, Error code: Mx16', 'error');
        }
    } catch (e) {
        renderAlert('Error loading bulk/holo/ex values: ' + e + 'Error code: Mx17', 'error');
    }
}

function initializeBulkHolo() {
    loadBulkHoloValues();
}

let box = null;

function spawnItemsContextMenu(cardId, e, itemLine) {
    box?.remove();

    const isSealed = cardId.includes('s');
    const gradingState = isSealed ? null : (itemLine.dataset.gradingState || 'raw');
    const canAddToCart = isSealed || gradingState !== 'at_grader';
    const canDelete = isSealed || gradingState === 'raw';
    const canGrade = !isSealed && gradingState === 'raw';
    const canViewGrading = !isSealed && gradingState === 'at_grader';
    box = document.createElement('div');
    box.classList.add("context-menu");
    //TODO: move styles to css
    box.style.left = (e.pageX + 10) + "px";
    box.style.top = (e.pageY - 25) + "px";
    box.innerHTML = `<div class="">
                            <div class="">
                                ${isSealed ? `<div class="">
                                    <button class="open-sealed-item">Open</button>
                                </div>` : ''}
                                ${canAddToCart ? `<div class="">
                                    <button class="add-to-cart">Add to cart</button>
                                </div>` : ''}
                                ${canDelete ? `<div class="">
                                    <button class="delete-card" data-id="${cardId}">Delete</button>
                                </div>` : ''}
                                ${canGrade ? `<div class="">
                                    <button class="grade-card" data-id="${cardId}">Grade</button>
                                </div>` : ''}
                                ${canViewGrading ? `<div class="">
                                    <button class="view-grading">View grading</button>
                                </div>` : ''}
                            </div>
                        </div>
                        <span hidden class="card-id">${cardId}</span>
                            `;
    document.body.appendChild(box);

    if (isSealed) {
        const openButton = box.querySelector('.open-sealed-item');
        openButton.addEventListener('click', () => {
            const auctionDiv = itemLine.closest('.auction-tab');
            const auctionId = auctionDiv?.getAttribute('data-id');
            const initialValue = itemLine.querySelector('.sealed-market-value, .market-value-sealed').textContent.replace('€', '');
            const sourceName = itemLine.querySelector('.sealed-name').textContent;
            const sourceLanguage = itemLine.querySelector('.sealed-language')?.textContent || 'en';
            createSealedModal(cardId, auctionId, initialValue, sourceName, sourceLanguage);
            box?.remove();
            box = null;
        });
    }

    const gradeButton = box.querySelector('.grade-card');
    if (gradeButton) {
        gradeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            const gradeCardId = gradeButton.getAttribute('data-id');
            gradingModal(gradeCardId);
            box?.remove();
            box = null;
        });
    }

    const viewGradingButton = box.querySelector('.view-grading');
    if (viewGradingButton) {
        viewGradingButton.addEventListener('click', () => {
            window.location.href = '/grading';
        });
    }

    const button = box.querySelector('.add-to-cart');
    //sealed add
    if (button && isSealed) {
        button.addEventListener('click', () => {
            const auctionDiv = itemLine.closest('.auction-tab');
            const auctionId = auctionDiv?.getAttribute('data-id');

            const sealedData = {
                name: DOMPurify.sanitize(itemLine.querySelector('.sealed-name').textContent),
                language: DOMPurify.sanitize(itemLine.querySelector('.sealed-language')?.textContent || 'en'),
                market_value: DOMPurify.sanitize(itemLine.querySelector('.sealed-market-value, .market-value-sealed').textContent.replace('€', ''))
            };

            const available = Number(itemLine.getAttribute('data-quantity')) || null;
            addSealedToCart(sealedData, cardId, auctionId, 1, available);
        });
    } else if (button) {
        //cards add
        button.addEventListener('click', async () => {
            const auctionDiv = itemLine.closest('.auction-tab');
            const auctionId = auctionDiv.getAttribute('data-id');

            const card = new CardStruct();
            card.cardName = itemLine.querySelector('.card-name').textContent;
            card.cardNum = itemLine.querySelector('.card-num').textContent;
            card.condition = itemLine.dataset.condition || itemLine.querySelector('.condition').textContent;
            card.language = itemLine.querySelector('.language')?.textContent || 'en';
            card.grading = itemLine.dataset.isGraded === 'true' ? {
                grader: itemLine.dataset.grader || null,
                grade_numeric: itemLine.dataset.gradeNumeric || null,
                grade_label: itemLine.dataset.gradeLabel || null,
                qualifier: itemLine.dataset.qualifier || null,
                cert_number: itemLine.dataset.certNumber || null,
            } : null;
            const marketValueText = itemLine.querySelector('.market-value').textContent;
            card.marketValue = marketValueText ? marketValueText.replace('€', '') : null;
            await addToShoppingCart(card, auctionId, cardId);
        });
    }

    const deleteButton = box.querySelector('.delete-card');
    if (deleteButton) deleteButton.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (deleteButton.textContent !== 'Confirm') {
            deleteButton.textContent = 'Confirm';
            const timerID = setTimeout(() => {
                deleteButton.textContent = 'Delete';
            }, 3000);
            return;
        }

        const cardsContainer = itemLine.closest('.cards-container');
        const auctionDiv = itemLine.closest('.auction-tab');
        const auctionId = auctionDiv?.getAttribute('data-id');

        if (isSealed) {
            try {
                const response = await csrfFetch(`/deleteSealed/${cardId}`, { method: 'DELETE' });
                const data = await response.json();
                if (data.status !== 'success') {
                    renderAlert('Error deleting sealed item: ' + JSON.stringify(data), 'error');
                    return;
                }
            } catch (error) {
                renderAlert('Error deleting sealed item: ' + error + ' Error code: Mx19', 'error');
                return;
            }
            itemLine.remove();
            await updateInventoryValueAndTotalProfit();
        } else {
            const deleted = await removeCard(cardId, itemLine);
            if (!deleted) return;
            await updateInventoryValueAndTotalProfit();
            if (cardsContainer && cardsContainer.childElementCount < 3) {
                if (auctionDiv && auctionDiv.classList.contains('singles')) {
                    const p = document.createElement('p');
                    p.textContent = 'Empty';
                    cardsContainer.insertBefore(p, cardsContainer.querySelector('.button-container'));
                } else if (auctionDiv) {
                    deleteAuction(auctionId, auctionDiv);
                }
            }
        }

        box?.remove();
        box = null;
    });
};

document.addEventListener('click', (e) => {
    box?.remove();
    box = null;
});


async function loadAuctionContent(button) {
    const auctionId = Number(button.getAttribute('data-id'));
    //TODO - make this into a single endpoint
    const cardsUrl = '/loadCards/' + auctionId;
    const bulkUrl = '/loadBulk/' + auctionId;
    const sealedUrl = '/loadSealed/' + auctionId;
    const auctionDiv = button.closest('.auction-tab');
    const cardsContainer = auctionDiv.querySelector('.cards-container');
    try {
        if (cardsContainer.childElementCount === 0 || cardsContainer.hidden) {
            cardsContainer.hidden = false;
            button.textContent = 'Hide';

            // Only fetch if we don't have content already
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
                        <p>Lang</p>
                        <p>Buy price</p>
                        <p>Market value</p>
                        <p>Margin</p>
                        <p></p>
                        <p></p>
                        <p></p>
                    </div>
                `;
                    cards.forEach(card => {
                        const safeCardId = sanitizeNumericId(card.id);
                        const conditionDisplay = cardConditionDisplay(card);
                        const safeCardConditionClass = sanitizeClassToken(card.condition || 'Unknown');
                        const gradingClass = card.grading_state === 'graded'
                            ? ' graded'
                            : card.grading_state === 'at_grader' ? ' at-grader' : '';
                        const cardDiv = document.createElement('div');
                        cardDiv.classList.add('card');
                        cardDiv.setAttribute('data-id', safeCardId);
                        cardDiv.dataset.condition = card.condition || '';
                        cardDiv.dataset.gradingState = card.grading_state || 'raw';
                        cardDiv.dataset.gradingSubmissionId = card.grading_submission_id ?? '';
                        cardDiv.dataset.gradingSubmissionStatus = card.grading_submission_status ?? '';
                        cardDiv.dataset.isGraded = card.grading_state === 'graded' ? 'true' : 'false';
                        cardDiv.dataset.grader = card.grader ?? '';
                        cardDiv.dataset.gradeNumeric = card.grade_numeric ?? '';
                        cardDiv.dataset.gradeLabel = card.grade_label ?? '';
                        cardDiv.dataset.qualifier = card.qualifier ?? '';
                        cardDiv.dataset.certNumber = card.cert_number ?? '';
                        cardDiv.innerHTML = `
                        ${renderField(DOMPurify.sanitize(card.card_name), 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                        ${renderField(DOMPurify.sanitize(card.card_num), 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                        <p class='card-info condition ${safeCardConditionClass}${gradingClass}' data-field="condition">${DOMPurify.sanitize(conditionDisplay)}</p>
                        ${renderField(DOMPurify.sanitize(card.language), 'text', ['card-info', 'language'], 'Lang', 'language')}
                        ${renderField(card.card_price ? DOMPurify.sanitize(card.card_price) + '€' : null, 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                        ${renderField(card.market_value ? DOMPurify.sanitize(card.market_value) + '€' : null, 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                        ${renderField(card.card_price !== null && card.market_value !== null ? (card.market_value - card.card_price).toFixed(2) + '€' : ' ', 'text', ['card-info', 'profit'], 'profit', true)}
                        <p></p>
                        `;
                        cardsContainer.appendChild(cardDiv);
                    });

                    let timer;
                    cardsContainer.addEventListener('click', (e) => {
                        clearTimeout(timer);

                        timer = setTimeout(() => {
                            const itemLine = e.target.closest('.card') || e.target.closest('.sealed-item');
                            const safeCardId = sanitizeNumericId(itemLine?.getAttribute("data-id")) || itemLine.getAttribute("sid");
                            spawnItemsContextMenu(safeCardId, e, itemLine);
                        }, 200);
                    });

                    cardsContainer.addEventListener('dblclick', (event) => {
                        clearTimeout(timer);
                        if (event.target.closest('.card') && !(event.target.tagName === "DIV")) {
                            const cardDiv = event.target.closest('.card');
                            const cardId = cardDiv.getAttribute('data-id');
                            const editableFields = new Set(['card_name', 'card_num', 'card_price', 'market_value']);
                            if (event.target.classList.contains('condition')) {
                                if (event.target.classList.contains('graded')) return;
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
                                    cardDiv.dataset.condition = p.textContent;
                                    patchValue(cardId, p.textContent, dataset);
                                });
                            } else if (event.target.classList.contains('language')) {
                                const value = event.target.textContent.trim();
                                const dataset = event.target.dataset.field;
                                const container = document.createElement('div');
                                container.innerHTML = languageSelect('card-info language select-language', dataset, value);
                                const select = container.firstElementChild;
                                event.target.replaceWith(select);
                                select.focus();
                                select.addEventListener('change', () => {
                                    const selectedValue = select.value;
                                    const p = document.createElement('p');
                                    p.classList.add('card-info', 'language');
                                    p.dataset.field = dataset;
                                    p.textContent = selectedValue;
                                    select.replaceWith(p);
                                    patchValue(cardId, selectedValue, dataset);
                                });
                            } else if (event.target.tagName === "P" && editableFields.has(event.target.dataset.field)) {
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
                            const cardId = event.target.closest('.card').getAttribute('data-id');
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
                            const card = new CardStruct();
                            card.cardName = cardDiv.querySelector('.card-name').textContent;
                            card.cardNum = cardDiv.querySelector('.card-num').textContent;
                            card.condition = cardDiv.dataset.condition;
                            card.language = cardDiv.querySelector('.language')?.textContent || 'en';
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
                    const responseSealed = await csrfFetch(sealedUrl);
                    const sealedData = await responseSealed.json();

                    sealedData.forEach(sealedItem => {
                        const sealedDiv = document.createElement('div');
                        sealedDiv.classList.add('sealed-item');
                        sealedDiv.setAttribute('sid', sealedItem.sid);
                        if (sealedItem.quantity != null) {
                            sealedDiv.setAttribute('data-quantity', sealedItem.quantity);
                        }

                        const margin = (Number(sealedItem.market_value) - Number(sealedItem.price)).toFixed(2);

                        sealedDiv.innerHTML = `
                            <p class='sealed-quantity'>${DOMPurify.sanitize(sealedItem.quantity)}</p>
                            <p class="sealed-name">${DOMPurify.sanitize(sealedItem.name)}</p>
                            <p class="sealed-language">${DOMPurify.sanitize(sealedItem.language || 'en')}</p>
                            <p class="sealed-price">${DOMPurify.sanitize(sealedItem.price)}€</p>
                            <p class="VAT-sealed">${(Number(DOMPurify.sanitize(sealedItem.price)) / 1.23).toFixed(2)}</p>
                            <p class="sealed-market-value">${DOMPurify.sanitize(sealedItem.market_value)}€</p>
                            <p class="sealed-margin">${DOMPurify.sanitize(margin)}€</p>
                            <p></p>
                            `;
                        enableSealedLanguageEditing(sealedDiv);

                        cardsContainer.insertBefore(sealedDiv, cardsContainer.querySelector('.button-container'));
                        sealedDiv.addEventListener('click', (event) => {
                            if (event.target.closest('.sealed-language, .sealed-language-select')) {
                                event.stopPropagation();
                                return;
                            }
                            event.stopPropagation();
                            spawnItemsContextMenu(sealedItem.sid, event, sealedDiv);
                        });
                    });

                    // Sealed "Open" lives in the items context menu (spawnItemsContextMenu)

                    // Add event listeners for "Add to cart" buttons
                    const addToCartButtons = cardsContainer.querySelectorAll('.add-to-cart-sealed');
                    addToCartButtons.forEach((button) => {
                        button.addEventListener('click', () => {
                            const sealedDiv = button.closest('.sealed-item');
                            const sid = sealedDiv.getAttribute('sid');
                            const auctionId = auctionDiv.getAttribute('data-id');

                            const sealedData = {
                                name: DOMPurify.sanitize(sealedDiv.querySelector('.sealed-name').textContent),
                                language: DOMPurify.sanitize(sealedDiv.querySelector('.sealed-language')?.textContent || 'en'),
                                market_value: DOMPurify.sanitize(sealedDiv.querySelector('.sealed-market-value').textContent.replace('€', ''))
                            };

                            const available = Number(sealedDiv.getAttribute('data-quantity')) || null;
                            addSealedToCart(sealedData, sid, auctionId, 1, available);
                        });
                    });

                    // Add event listeners for "Delete" buttons
                    const deleteSealedButtons = cardsContainer.querySelectorAll('.delete-sealed-item');
                    deleteSealedButtons.forEach((button) => {
                        button.addEventListener('click', async () => {
                            const sid = button.getAttribute('data-sid');
                            const sealedDiv = button.closest('.sealed-item');

                            if (button.textContent === 'Confirm') {
                                const response = await csrfFetch(`/deleteSealed/${sid}`, { method: 'DELETE' });
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
                    const responseBulk = await csrfFetch(bulkUrl);
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
            cardsContainer.hidden = true;
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
                ${languageSelect('card-info language select-language', 'language')}
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
                ${languageSelect('sealed-language-select')}
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
            try {
                newCards.forEach(async (card) => {
                    let cardObj = new CardStruct();
                    cardObj.cardName = DOMPurify.sanitize(card.querySelector('input.card-name').value.trim().toUpperCase()) || null;
                    cardObj.cardNum = DOMPurify.sanitize(card.querySelector('input.card-num').value.trim().toUpperCase()) || null;
                    cardObj.condition = DOMPurify.sanitize(card.querySelector('select.condition').value) || null;
                    cardObj.language = DOMPurify.sanitize(card.querySelector('select.language').value);
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
                        if (key === 'soldDate' || key === 'grading') continue;
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
                        const language = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-language-select').value);
                        const date = DOMPurify.sanitize(sealedDiv.querySelector('.sealed-date-input').value) || null;

                        if (name !== null && marketValue !== null) {
                            sealedItems.push({
                                name: name,
                                price: price,
                                market_value: marketValue,
                                language: language,
                                date: date
                            });
                        }
                    });

                    if (sealedItems.length > 0) {
                        itemsToAdd['sealed'] = sealedItems;
                    }
                }

                const jsonbody = JSON.stringify(itemsToAdd);
                const response = await csrfFetch(`/addToExistingAuction/${auctionId}`, {
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
            } catch (error) {
                renderAlert('Error saving new cards: ' + error, 'error');
                return;
            }
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
    if (sealedTab.hidden || sealedTab.childElementCount === 0) {
        sealedTab.hidden = false;
        viewButton.innerHTML = 'Hide';

        // Only fetch if we don't have items already
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
                    sealedDiv.setAttribute('sid', sealedData.sid);
                    if (sealedData.quantity != null) {
                        sealedDiv.setAttribute('data-quantity', sealedData.quantity);
                    }
                    const margin = (Number(DOMPurify.sanitize(sealedData.market_value)) - Number(DOMPurify.sanitize(sealedData.price))).toFixed(2);
                    const timeStamp = DOMPurify.sanitize(sealedData.date).replace('Z', '');
                    const date = new Date(timeStamp);
                    let formatedDate = date.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
                    sealedDiv.innerHTML = `
                        <p class='sealed-quantity'>${DOMPurify.sanitize(sealedData.quantity)}</p>
                        <p class='sealed-name'>${DOMPurify.sanitize(sealedData.name)}</p>
                        <p class='sealed-language'>${DOMPurify.sanitize(sealedData.language || 'en')}</p>
                        <p class='unit-price'>${DOMPurify.sanitize(sealedData.price)}</p>
                        <p class='VAT-sealed sealed-market-VAT-value'>${(DOMPurify.sanitize(sealedData.price) / 1.23).toFixed(2)}</p>
                        <p class='market-value-sealed'>${DOMPurify.sanitize(sealedData.market_value)}</p>
                        <p class='margin'>${margin}</p>
                        <p class='add-date'>${formatedDate}</p>
                        <p></p>
                        <p></p>
                        `
                    enableSealedLanguageEditing(sealedDiv);

                    sealedDiv.addEventListener('click', (event) => {
                        if (event.target.closest('.sealed-language, .sealed-language-select')) {
                            event.stopPropagation();
                            return;
                        }
                        event.stopPropagation();
                        spawnItemsContextMenu(sealedData.sid, event, sealedDiv);
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
                            ${languageSelect('sealed-language-select')}
                            <input type='date' value=${date} max=${date} ></input>
                        `
                    contentDiv.append(div);

                    const saveButton = buttonsContainer.querySelector('.save-sealed-btn');
                    saveButton.hidden = false;

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
                        row.dateAdded = inputs[3].value || null;
                        row.language = div.querySelector('.sealed-language-select').value;
                        if (row.name !== null && row.market_value !== null) {
                            inputValues.push(row);
                        }
                    })
                    saveButton.hidden = true;
                    if (inputValues.length > 0) {
                        const response = await csrfFetch('/addSealed', {
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
        sealedTab.hidden = true;
        viewButton.innerHTML = 'View';
    }
}

async function loadUnlinkedIds() {
    try {
        const response = await csrfFetch('/unlinkedBarterIds');
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

function openMergeAuctionModal(auctionId, auctionName) {
    const modal = document.createElement('div');
    modal.classList.add('reciever-div');
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('modal-content', 'merge-auction-modal');

    const close = () => modal.remove();
    contentDiv.innerHTML = `
        <span class="close-modal">&times;</span>
        <div>
            <p>Source auction:</p>
            <p>${auctionName}</p>
        </div>
        <div>
            <p>Target auction:</p>
            <select class="merge-auction-target-select"></select>
        </div>
        <div>
            <button class="merge-auction-confirm-btn">Confirm</button>
        </div>
    `;

    const targetSelect = contentDiv.querySelector('.merge-auction-target-select');
    targetSelect.addEventListener('focus', async (event) => {
        const response = await csrfFetch(`/loadAuctions`);
        const data = await response.json();
        data.forEach(auction => {
            if (auction.id == auctionId) return;
            const safeAuctionId = sanitizeNumericId(auction.id);
            const option = document.createElement('option');
            option.value = safeAuctionId;
            option.textContent = `${auction.auction_name || 'Auction ' + (auction.id - 1)}`;
            targetSelect.appendChild(option);
        });
    })
    let targetId = null;
    targetSelect.addEventListener('change', (event) => {
        targetId = event.target.value;
    });


    const confirmBtn = contentDiv.querySelector('.merge-auction-confirm-btn');
    confirmBtn.addEventListener('click', async (event) => {
        if (!targetId) {
            renderAlert('Please select target auction', 'error');
            close();
            return;
        }
        const response = await csrfFetch(`/mergeAuctions/${auctionId}/${targetId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
        });
        const data = await response.json();
        if (data.status === 'success') {
            window.location.reload();
            close();
        } else {
            renderAlert(data.message, 'error');
            close();
        };
    });

    modal.appendChild(contentDiv);
    document.body.appendChild(modal);

    const closeButton = document.querySelector('.close-modal');
    closeButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) close();
    });
}

async function loadAuctions() {
    const auctionContainer = document.querySelector('.auction-container');
    try {
        const response = await csrfFetch('/loadAuctions');
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
                <div>
                    <button class="view-auction" data-id="${safeAuctionId}">View</button>
                </div>
                <div class="auction-options">
                    <div class="auction-options-list">
                        <div class="auction-option">
                            <button class="delete-auction" data-id="${safeAuctionId}">Delete</button>
                        </div>
                        <div class="auction-option">
                            <button class="merge-button">Merge</button>
                        </div>
                        <div class="auction-option auction-link-cell">
                            ${auction.sale_id == null
                    ? `<select class='barter-id-select'><option value="null">Select Invoice Number to link</option></select>`
                    : `<a class="sale-link" href="/sold#${safeSaleId}">Invoice Number: ${DOMPurify.sanitize(invoiceNumber)}</a>`
                }
                        </div>
                    </div>
                </div>
                <div class="cards-container">
                    <!-- Cards will be loaded here -->
                </div>
            `;
            auctionContainer.appendChild(auctionDiv);

            // Store payments data on the div for la
            auctionDiv.paymentsData = payments;

        });

        const mergeAuctions = document.querySelectorAll('.merge-button');
        mergeAuctions.forEach((button) => {
            button.addEventListener('click', async (event) => {
                const auctionDiv = event.target.closest('.auction-tab');
                const auctionId = auctionDiv.getAttribute('data-id');
                const auctionName = auctionDiv.querySelector('.auction-name').textContent;
                openMergeAuctionModal(auctionId, auctionName);
            });
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
                    const res = await csrfFetch(`/linkAuctionToSale/${auctionId}`, {
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

searchBar();
loadAuctions();
initializeSealed();
initializeCart();
initializeBulkHolo();
loadCartContentFromSession();
scrollOnLoad();
startPolling();
