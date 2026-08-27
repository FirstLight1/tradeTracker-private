import { sanitizeAttrValue, sanitizeClassToken, sanitizePlainText, csrfFetch } from "./sanitizers.js";

let alertTimer = null;

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

    if (!alertDiv) return;

    if (alertTimer) clearTimeout(alertTimer);
    alertDiv.classList.remove('alert-error', 'alert-message');
    const isError = type === 'error';
    alertDiv.classList.add(isError ? 'alert-error' : 'alert-message');
    alertDiv.setAttribute('role', isError ? 'alert' : 'status');
    alertDiv.setAttribute('aria-live', isError ? 'assertive' : 'polite');
    alertDiv.setAttribute('aria-atomic', 'true');
    alertDiv.textContent = String(text);

    alertTimer = setTimeout(() => {
        alertDiv.textContent = '';
        alertDiv.classList.remove('alert-error', 'alert-message');
        alertDiv.removeAttribute('role');
        alertDiv.removeAttribute('aria-live');
        alertDiv.removeAttribute('aria-atomic');
        alertTimer = null;
    }, isError ? 10000 : 6000);
}

export function errorMessage(error, fallback = 'Something went wrong') {
    if (typeof error === 'string' && error.trim()) return error;
    if (error && typeof error.message === 'string' && error.message.trim()) return error.message;
    return fallback;
}

export function clearFieldErrors(root = document) {
    root.querySelectorAll('.field-error[data-generated-error="true"]').forEach(error => error.remove());
    root.querySelectorAll('[aria-invalid="true"]').forEach(field => {
        field.removeAttribute('aria-invalid');
        const describedBy = (field.getAttribute('aria-describedby') || '')
            .split(/\s+/)
            .filter(id => id && !id.startsWith('server-error-'));
        if (describedBy.length) field.setAttribute('aria-describedby', describedBy.join(' '));
        else field.removeAttribute('aria-describedby');
    });
}

function flattenErrors(errors) {
    if (Array.isArray(errors)) {
        return errors.flatMap(error => {
            if (typeof error === 'string') return [{ field: '', message: error }];
            if (!error || typeof error !== 'object') return [];
            return [{ field: error.field || error.path || '', message: errorMessage(error, 'Invalid value') }];
        });
    }
    if (!errors || typeof errors !== 'object') return [];
    return Object.entries(errors).flatMap(([field, value]) => {
        const values = Array.isArray(value) ? value : [value];
        return values.map(item => ({ field, message: errorMessage(item, 'Invalid value') }));
    });
}

export function renderServerErrors(data, root = document, fieldMap = {}, fallback = 'Unable to save') {
    clearFieldErrors(root);
    const errors = flattenErrors(data?.errors);
    const general = [];
    errors.forEach(({ field, message }, index) => {
        const parts = String(field).split(/[.\[\]]/).filter(Boolean);
        const mapped = fieldMap[field] ?? fieldMap[parts[parts.length - 1]];
        const itemIndex = parts.find(part => /^\d+$/.test(part));
        const input = typeof mapped === 'function'
            ? mapped({ field, parts, itemIndex })
            : (typeof mapped === 'string'
                ? (itemIndex === undefined
                    ? root.querySelector(mapped)
                    : root.querySelectorAll(mapped)[Number(itemIndex)])
                : mapped);
        if (!input) {
            general.push(message);
            return;
        }
        const error = document.createElement('p');
        error.className = 'field-error';
        error.dataset.generatedError = 'true';
        error.id = `server-error-${Date.now()}-${index}`;
        error.textContent = message;
        input.setAttribute('aria-invalid', 'true');
        const describedBy = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
        describedBy.add(error.id);
        input.setAttribute('aria-describedby', [...describedBy].join(' '));
        input.insertAdjacentElement('afterend', error);
    });
    if (errors.length === 0) general.push(errorMessage(data, fallback));
    else if (data?.message) general.unshift(data.message);
    if (general.length) renderAlert([...new Set(general)].join('\n'), 'error');
    const firstInvalid = root.querySelector('[aria-invalid="true"]');
    firstInvalid?.focus();
    return errors.length > 0;
}

export function scrollOnLoad() {
    window.addEventListener('load', () => {
        const hash = window.location.hash;
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
        const response = await csrfFetch('/inventoryValue', {
            method: 'GET',
        });
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

export function createNewItem(node, { triggerSelector = '.marketValue', onTrigger = (el) => window.handleCardInput(el) } = {}) {
    node.querySelectorAll('input').forEach(el => {
        el.value = '';
    });
    node.querySelectorAll('select').forEach(sel => {
        const defaultOption = sel.querySelector('option[selected]');
        sel.value = defaultOption?.value ?? sel.options[0]?.value ?? '';
    });
    const trigger = node.querySelector(triggerSelector);
    if (trigger) {
        trigger.addEventListener('input', () => onTrigger(trigger));
    }
    return node;
}

export function createNewCard(newCard) {
    return createNewItem(newCard);
}

window.handleCardInput = function (input, { itemSelector = '.card', container = document.querySelector('.cards-container'), triggerSelector = '.marketValue' } = {}) {
    const items = container.querySelectorAll(itemSelector);
    const current = input.closest(itemSelector);
    const last = items[items.length - 1];

    if (current === last && input.value.trim() !== '') {
        const newNode = createNewItem(last.cloneNode(true), {
            triggerSelector,
            onTrigger: (el) => window.handleCardInput(el, { itemSelector, container, triggerSelector })
        });
        container.appendChild(newNode);
    }
}

export async function downloadFile(response, fallbackName = 'invoice.pdf'){
    const disposition = response.headers.get('Content-Disposition');
    const filename = disposition?.match(/filename\*?=["']?(?:UTF-\d+'')?([^"';\n]+)/i)?.[1]
    ?? fallbackName;

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    const a = Object.assign(document.createElement('a'), { href: url, download: filename });
    a.click();

    // Revoke after a tick so the browser has time to start the download
    setTimeout(() => URL.revokeObjectURL(url), 0);
}
