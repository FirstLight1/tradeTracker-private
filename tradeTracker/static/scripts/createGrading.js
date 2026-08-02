import { queue } from "./utils/classes.js";
import { renderAlert, scrollOnLoad } from "./utils/renderUtil.js";
import { csrfFetch, escapeHtml, sanitizeClassToken, sanitizeNumericId } from "./utils/sanitizers.js";
import { searchCard } from "./utils/searchApi.js";

const addedIds = new Set();
let currentResultsQueue = null;

function searchBar() {
    const searchInput = document.querySelector('.grading-card-search .search-field');
    const searchBtn = document.querySelector('.grading-card-search .search-btn');
    const searchContainer = document.querySelector('.grading-card-search .search-results');

    searchInput.addEventListener('keydown', event => {
        if (!currentResultsQueue) return;
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            currentResultsQueue.moveNext();
            currentResultsQueue.getCurrent().focus();
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            currentResultsQueue.movePrev();
            currentResultsQueue.getCurrent().focus();
        }
    });

    const search = async () => {
        const query = searchInput.value.trim();
        if (!query) {
            searchContainer.replaceChildren();
            return;
        }
        const results = (await searchCard(query, [...addedIds]) || [])
            .filter(result => !Object.prototype.hasOwnProperty.call(result, 'sid'))
            .slice(0, 7);
        currentResultsQueue = new queue(results.length + 1);
        currentResultsQueue.enqueue(searchInput);
        displayResults(results, currentResultsQueue, searchInput, searchContainer);
    };

    searchInput.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            search();
        }
    });
    searchBtn.addEventListener('click', search);
}

function displayResults(results, resultsQueue, searchInput, searchContainer) {
    searchContainer.replaceChildren();
    if (results.length === 0) {
        const emptyResult = document.createElement('div');
        emptyResult.className = 'search-result-item';
        emptyResult.textContent = 'No cards found';
        searchContainer.appendChild(emptyResult);
        return;
    }

    results.forEach(result => {
        const row = document.createElement('div');
        row.className = 'search-result-item';
        row.tabIndex = 0;
        row.innerHTML = `
            <p class="result result-name">${escapeHtml(result.card_name || 'N/A')}</p>
            <p class="result result-num">${escapeHtml(result.card_num || '')}</p>
            <p class="result result-condition ${sanitizeClassToken(result.condition || '')}">${escapeHtml(result.condition || '')}</p>
            <p class="result result-quantity">1 / ${escapeHtml(String(result.available_count || 1))}</p>
            <p class="result result-market-value">${escapeHtml(String(result.market_value ?? ''))}€</p>
        `;
        resultsQueue.enqueue(row);

        const add = async () => {
            await addCard(result);
            searchInput.value = '';
            searchInput.focus();
            searchContainer.replaceChildren();
        };

        row.addEventListener('click', add);
        row.addEventListener('keydown', async event => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                resultsQueue.moveNext();
                resultsQueue.getCurrent().focus();
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                resultsQueue.movePrev();
                resultsQueue.getCurrent().focus();
            } else if (event.key === 'Enter') {
                event.preventDefault();
                await add();
            }
        });
        searchContainer.appendChild(row);
    });
}

async function addCard(result) {
    const response = await csrfFetch('/getCardIds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            card_name: result.card_name,
            card_num: result.card_num,
            condition: result.condition,
            exclude_ids: [...addedIds],
        }),
    });
    const data = await response.json();
    const cardId = data.status === 'success' ? data.card_ids?.[0] : null;
    if (!cardId) {
        renderAlert('No more available copies of this card', 'error');
        return;
    }

    addedIds.add(cardId);
    renderCard(result, cardId);
}

function renderCard(result, cardId) {
    const itemsContainer = document.querySelector('.creditnote-item-content');
    if (!itemsContainer.querySelector('.grading-card-header')) {
        const header = document.createElement('div');
        header.className = 'grading-card-header';
        header.innerHTML = `
            <span>Card</span>
            <span>Condition</span>
            <span>Submitted value</span>
            <span>Grading fee</span>
            <span>Prep fee</span>
            <span>Upcharge</span>
            <span></span>
        `;
        itemsContainer.appendChild(header);
    }

    const row = document.createElement('div');
    row.className = 'card creditnote-item-row grading-card-row';
    row.dataset.id = sanitizeNumericId(cardId);
    row.innerHTML = `
        <div class="item-info">
            <p class="item-name">${escapeHtml(result.card_name || '')}</p>
            <p class="item-number">${escapeHtml(result.card_num || '')}</p>
        </div>
        <p class="item-condition ${sanitizeClassToken(result.condition || '')}">${escapeHtml(result.condition || '')}</p>
        <input class="submitted-value-input" aria-label="Submitted value" type="number" min="0" step="0.01" value="${escapeHtml(String(result.market_value ?? 0))}">
        <input class="grading-fee-input" aria-label="Grading fee" type="number" min="0" step="0.01" value="0">
        <input class="prep-fee-input" aria-label="Prep fee" type="number" min="0" step="0.01" value="0">
        <input class="upcharge-input" aria-label="Upcharge" type="number" min="0" step="0.01" value="0">
        <button class="item-remove-btn" type="button">X</button>
    `;
    row.querySelector('.item-remove-btn').addEventListener('click', () => {
        addedIds.delete(cardId);
        row.remove();
        if (!itemsContainer.querySelector('.grading-card-row')) {
            itemsContainer.querySelector('.grading-card-header')?.remove();
        }
        updateTotal();
    });
    row.querySelectorAll('input').forEach(input => input.addEventListener('input', updateTotal));
    itemsContainer.appendChild(row);
    updateTotal();
}

function updateTotal() {
    const sharedCosts = [
        '#outbound-shipping-cost', '#return-shipping-cost', '#insurance-cost', '#customs-duty-cost', '#other-shared-cost',
    ].reduce((total, selector) => total + (Number(document.querySelector(selector).value) || 0), 0);
    const cardCosts = [...document.querySelectorAll('.grading-card-row')].reduce((total, row) => total
        + (Number(row.querySelector('.grading-fee-input').value) || 0)
        + (Number(row.querySelector('.prep-fee-input').value) || 0)
        + (Number(row.querySelector('.upcharge-input').value) || 0), 0);
    document.querySelector('.total-amount').textContent = (sharedCosts + cardCosts).toFixed(2);
}

function submissionPayload() {
    const value = selector => document.querySelector(selector).value;
    return {
        submission: {
            grader: value('#grader'),
            service_level: value('#service-level') || null,
            status: value('#status'),
            submitted_at: value('#submitted-at'),
            returned_at: value('#returned-at') || null,
            notes: value('#notes') || null,
            outbound_shipping_cost: Number(value('#outbound-shipping-cost')) || 0,
            return_shipping_cost: Number(value('#return-shipping-cost')) || 0,
            insurance_cost: Number(value('#insurance-cost')) || 0,
            customs_duty_cost: Number(value('#customs-duty-cost')) || 0,
            other_shared_cost: Number(value('#other-shared-cost')) || 0,
        },
        cards: [...document.querySelectorAll('.grading-card-row')].map(row => ({
            card_id: Number(row.dataset.id),
            grader: null,
            submitted_value: Number(row.querySelector('.submitted-value-input').value) || 0,
            grading_fee: Number(row.querySelector('.grading-fee-input').value) || 0,
            prep_fee: Number(row.querySelector('.prep-fee-input').value) || 0,
            upcharge: Number(row.querySelector('.upcharge-input').value) || 0,
        })),
    };
}

function setupForm() {
    const form = document.querySelector('.grading-submission-form');
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const payload = submissionPayload();
        if (payload.cards.length === 0) {
            renderAlert('Add at least one card', 'error');
            return;
        }
        const response = await csrfFetch('/grading/submissions/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            renderAlert(`Error: ${data.message || 'Unable to create submission'}`, 'error');
            return;
        }
        window.location.href = '/grading';
    });
    document.querySelectorAll('.creditnote-receiver input').forEach(input => input.addEventListener('input', updateTotal));
}

searchBar();
setupForm();
scrollOnLoad();
