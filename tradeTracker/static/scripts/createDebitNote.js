import { renderField, renderAlert, scrollOnLoad, downloadFile } from "./utils/renderUtil.js";
import { sanitizeNumericId, sanitizeClassToken, escapeHtml, csrfFetch } from "./utils/sanitizers.js";
import { queue } from "./utils/classes.js";
import { searchCard } from "./utils/searchApi.js";
import { DebitNoteItem } from "./utils/debitNoteItem.js";

function conditionClass(condition) {
    if (!condition) return '';
    const norm = condition.toLowerCase().replace(/[\s_-]+/g, '');
    const map = {
        mint: 'mint',
        mt: 'mint',
        nearmint: 'near_mint',
        nm: 'near_mint',
        excellent: 'excellent',
        ex: 'excellent',
        good: 'good',
        gd: 'good',
        lightplayed: 'light_played',
        lp: 'light_played',
        played: 'played',
        pl: 'played',
        poor: 'poor',
        po: 'poor',
    };
    return map[norm] || '';
}

function renderAddressBlock(container, data) {
    container.innerHTML = `
        <div class="creditnote-address-block">
            <p class="address-name">${data.name || data.summary || ''}</p>
            <p class="address-line">${data.address || ''}</p>
            <p class="address-line"><span class="address-zip">${data.zip_code || ''}</span> <span class="address-city">${data.city || ''}</span></p>
            <p class="address-line">${data.state || data.country || ''}</p>
            ${data.phone ? `<p class="address-line address-contact">${data.phone}</p>` : ''}
            ${data.email ? `<p class="address-line address-contact">${data.email}</p>` : ''}
            ${data.ico ? `<p class="address-line address-id"><span>IČO:</span> ${data.ico}</p>` : ''}
            ${data.dic ? `<p class="address-line address-id"><span>DIČ:</span> ${data.dic}</p>` : ''}
            ${data.ic_dph ? `<p class="address-line address-id"><span>IČ DPH:</span> ${data.ic_dph}</p>` : ''}
        </div>
    `;
}

const addedIds = new Set();
let currentResultsQueue = null;

function searchBar() {
    const searchInput = document.querySelector('.debit-note-search .search-field');
    const searchBtn = document.querySelector('.debit-note-search .search-btn');
    if (!searchInput || !searchBtn) return;

    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown' && currentResultsQueue) {
            event.preventDefault();
            currentResultsQueue.moveNext();
            currentResultsQueue.getCurrent().focus();
        }
        if (event.key === 'ArrowUp' && currentResultsQueue) {
            event.preventDefault();
            currentResultsQueue.movePrev();
            currentResultsQueue.getCurrent().focus();
        }
    });

    searchInput.addEventListener('keydown', async (event) => {
        if (event.key === 'Enter') {
            if (searchInput.value === '') {
                document.querySelector('.debit-note-search .search-results').innerHTML = '';
                return;
            }
            const results = await searchCard(searchInput.value, [...addedIds]) || [];
            currentResultsQueue = new queue(results.length + 1);
            currentResultsQueue.enqueue(searchInput);
            displayDebitNoteResults(results, currentResultsQueue, searchInput);
        }
    });

    searchBtn.addEventListener('click', async () => {
        if (searchInput.value === '') {
            document.querySelector('.debit-note-search .search-results').innerHTML = '';
        }
        const results = await searchCard(searchInput.value.trim(), [...addedIds]) || [];
        currentResultsQueue = new queue(results.length + 1);
        currentResultsQueue.enqueue(searchInput);
        displayDebitNoteResults(results, currentResultsQueue, searchInput);
        searchInput.focus();
    });
}

function displayDebitNoteResults(results, resultsQueue, searchInput) {
    const searchContainer = document.querySelector('.debit-note-search .search-results');
    searchContainer.innerHTML = '';

    if (!results || results.length === 0) {
        const div = document.createElement('div');
        div.classList.add('search-result-item');
        div.innerHTML = '<p>No results found</p>';
        searchContainer.appendChild(div);
        return;
    }

    results.forEach(result => {
        const isSealed = Object.prototype.hasOwnProperty.call(result, 'sid');
        const name = isSealed ? result.name : result.card_name;
        const num = isSealed ? '' : (result.card_num || '');
        const condition = isSealed ? '' : (result.condition || '');
        const availableCount = result.available_count ? Number(result.available_count) : 1;
        const marketValue = result.market_value != null ? result.market_value : '';
        const safeConditionClass = sanitizeClassToken(condition || '');

        let pendingQty = 1;
        const div = document.createElement('div');
        div.classList.add('search-result-item');
        div.tabIndex = 0;
        div.innerHTML = `
            <p class="result result-name">${escapeHtml(name || 'N/A')}</p>
            <p class="result result-num">${escapeHtml(num)}</p>
            <p class="result result-condition ${safeConditionClass}">${escapeHtml(condition)}</p>
            <p class="result result-quantity">${pendingQty} / ${availableCount}</p>
            <p class="result result-market-value">${escapeHtml(String(marketValue))}€</p>
        `;
        resultsQueue.enqueue(div);

        const updateQty = () => {
            div.querySelector('.result-quantity').textContent = `${pendingQty} / ${availableCount}`;
        };

        div.addEventListener('keydown', async (event) => {
            event.preventDefault();
            if (event.key === 'ArrowDown') {
                resultsQueue.moveNext();
                resultsQueue.getCurrent().focus();
            } else if (event.key === 'ArrowUp') {
                resultsQueue.movePrev();
                resultsQueue.getCurrent().focus();
            } else if (event.key === 'ArrowRight') {
                pendingQty = Math.min(pendingQty + 1, availableCount);
                updateQty();
            } else if (event.key === 'ArrowLeft') {
                pendingQty = Math.max(pendingQty - 1, 1);
                updateQty();
            } else if (event.key === 'Enter') {
                await addItemToDebitNote(result, pendingQty);
                searchInput.value = '';
                searchInput.focus();
                searchContainer.innerHTML = '';
            }
        });

        div.addEventListener('click', async () => {
            await addItemToDebitNote(result, pendingQty);
            searchInput.value = '';
            searchInput.focus();
            searchContainer.innerHTML = '';
        });

        searchContainer.appendChild(div);
    });
}

async function addItemToDebitNote(result, pendingQty) {
    const itemsContainer = document.querySelector('.creditnote-item-content');
    const item = await DebitNoteItem.fromSearchResult(result, pendingQty, addedIds);
    if (!item) return;
    const totalPrice = document.querySelector('.total-amount');
    item.render().forEach(el => {
        itemsContainer.appendChild(el)
    });
    if (item.type === 'card') {
        item.cardIds.forEach(_ => {
            totalPrice.textContent = (Number(totalPrice.textContent) + Number(item.marketValue)).toFixed(2)
        })
    } else {
        totalPrice.textContent = (Number(totalPrice.textContent) + Number(item.marketValue * item.quantity)).toFixed(2)
    }

}

async function loadContent() {
    const params = new Proxy(new URLSearchParams(window.location.search), {
        get: (searchParams, prop) => searchParams.get(prop),
    });

    const saleId = sanitizeNumericId(params.saleId);

    const providerDiv = document.querySelector('.creditnote-box-content');
    const recieverDiv = document.querySelector('.creditnote-reciver-content');

    //TODO: find better name for this endpoint 
    const response = await csrfFetch(`/partyInfo/${saleId}`);
    const data = await response.json();
    const saleInfo = data.sale;
    const originalInvoiceNum = saleInfo.invoice_number;
    const providerInfo = data.providerInfo;
    const recieverInfo = data.recieverInfo;

    renderAddressBlock(providerDiv, {
        ...providerInfo,
        name: providerInfo.summary,
        state: providerInfo.country,
    });

    renderAddressBlock(recieverDiv, {
        ...recieverInfo,
        name: recieverInfo.nameAndSurname,
        country: recieverInfo.state,
    });

    searchBar();
}

loadContent();
