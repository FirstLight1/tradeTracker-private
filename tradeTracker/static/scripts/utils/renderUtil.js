import { sanitizeAttrValue, sanitizeClassToken, sanitizePlainText } from "./sanitizers.js";

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

export async function getInventoryValue() {
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

export function appendEuroSign(value, dataset) {
    if (dataset === 'card_num' || dataset === 'card_name') {
        return value;
    }
    if (isNaN(value)) {
        return value;
    } else {
        return value + '€';
    }
}

export function createNewCard(newCard){
     newCard.querySelectorAll('input').forEach(el =>{
            el.value = '';
        });

        newCard.querySelectorAll('select').forEach(sel => {
        sel.selectedIndex = 1;
        });

        const newCardName = newCard.querySelector('.marketValue');
        newCardName.oninput = function () {
        handleCardInput(this);
        }
        return newCard;
}


window.handleCardInput = function (input){
    const container = document.querySelector(".cards-container")
    const cards = document.querySelectorAll(".card")
    const currentCard = input.closest('.card');
    const lastCard = cards[cards.length - 1];

    if(currentCard == lastCard && input.value.trim() !== ''){
        const newCard = createNewCard(lastCard.cloneNode(true));
        container.appendChild(newCard)
    }
}