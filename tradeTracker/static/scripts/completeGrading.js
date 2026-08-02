import { renderAlert, scrollOnLoad } from "./utils/renderUtil.js";
import { csrfFetch, sanitizeNumericId } from "./utils/sanitizers.js";

const main = document.querySelector('main[data-submission-id]');
const submissionId = sanitizeNumericId(main.dataset.submissionId);
const form = document.querySelector('.grading-completion-form');
const cardList = document.querySelector('.completion-card-list');
const submitButton = form.querySelector('.confirm-btn');

function nullableText(input) {
    const value = input.value.trim();
    return value || null;
}

function nullableNumber(input) {
    return input.value === '' ? null : Number(input.value);
}

function createInput(className, label, type = 'text') {
    const input = document.createElement('input');
    input.className = className;
    input.type = type;
    input.setAttribute('aria-label', label);
    if (type === 'number') input.step = '0.01';
    return input;
}

function setInitialValue(input, value) {
    input.value = value === null || value === undefined ? '' : String(value);
}

function renderHeader() {
    const header = document.createElement('div');
    header.className = 'completion-card-header';
    ['Card', 'Condition', 'Grade number', 'Grade label', 'Qualifier', 'Certificate', 'Market value'].forEach(label => {
        const cell = document.createElement('span');
        cell.textContent = label;
        header.appendChild(cell);
    });
    cardList.appendChild(header);
}

function renderCard(card) {
    const row = document.createElement('div');
    row.className = 'completion-card-row';
    row.dataset.cardId = sanitizeNumericId(card.card_id);

    const cardInfo = document.createElement('div');
    cardInfo.className = 'completion-card-info';
    const cardName = document.createElement('p');
    cardName.className = 'completion-card-name';
    cardName.textContent = card.card_name || 'Unknown card';
    const cardNumber = document.createElement('p');
    cardNumber.className = 'completion-card-number';
    cardNumber.textContent = card.card_num || '';
    cardInfo.append(cardName, cardNumber);

    const condition = document.createElement('p');
    condition.className = 'completion-condition';
    condition.textContent = card.condition || 'Unknown';

    const gradeNumeric = createInput('grade-numeric-input', `${card.card_name || 'Card'} grade number`, 'number');
    gradeNumeric.min = '0';
    const gradeLabel = createInput('grade-label-input', `${card.card_name || 'Card'} grade label`);
    const qualifier = createInput('qualifier-input', `${card.card_name || 'Card'} qualifier`);
    const certNumber = createInput('cert-number-input', `${card.card_name || 'Card'} certificate number`);
    const marketValue = createInput('market-value-input', `${card.card_name || 'Card'} post-grade market value`, 'number');
    marketValue.min = '0';

    setInitialValue(gradeNumeric, card.grade_numeric);
    setInitialValue(gradeLabel, card.grade_label);
    setInitialValue(qualifier, card.qualifier);
    setInitialValue(certNumber, card.cert_number);
    setInitialValue(marketValue, card.post_grade_market_value ?? card.market_value);

    row.append(cardInfo, condition, gradeNumeric, gradeLabel, qualifier, certNumber, marketValue);
    cardList.appendChild(row);
}

async function loadCards() {
    try {
        const response = await csrfFetch(`/grading/submissions/${submissionId}`);
        if (!response.ok) throw new Error(`request failed with status ${response.status}`);
        const cards = await response.json();
        if (!Array.isArray(cards)) throw new Error('invalid cards response');

        cardList.replaceChildren();
        if (cards.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'completion-empty';
            empty.textContent = 'No cards found in this submission.';
            cardList.appendChild(empty);
            return;
        }

        renderHeader();
        cards.forEach(renderCard);
        submitButton.disabled = false;
    } catch (error) {
        cardList.replaceChildren();
        renderAlert(`Error loading grading submission: ${error}`, 'error');
    }
}

function completionPayload() {
    return [...cardList.querySelectorAll('.completion-card-row')].map(row => ({
        card_id: Number(row.dataset.cardId),
        grade_numeric: nullableNumber(row.querySelector('.grade-numeric-input')),
        grade_label: nullableText(row.querySelector('.grade-label-input')),
        qualifier: nullableText(row.querySelector('.qualifier-input')),
        cert_number: nullableText(row.querySelector('.cert-number-input')),
        post_grade_market_value: nullableNumber(row.querySelector('.market-value-input')),
    }));
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    const payload = completionPayload();
    if (payload.length === 0) return;

    submitButton.disabled = true;
    submitButton.textContent = 'Completing...';
    try {
        const response = await csrfFetch(`/grading/submissions/${submissionId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.message || `request failed with status ${response.status}`);
        window.location.href = '/grading';
    } catch (error) {
        renderAlert(`Error completing grading submission: ${error}`, 'error');
        submitButton.disabled = false;
        submitButton.textContent = 'Complete submission';
    }
});

scrollOnLoad();
loadCards();
