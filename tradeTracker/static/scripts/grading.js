import { renderAlert, scrollOnLoad } from "./utils/renderUtil.js";
import { sanitizeNumericId, csrfFetch } from "./utils/sanitizers.js";

function formatCurrency(value) {
    if (value === null || value === undefined || value === '') return '0.00€';
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)}€` : '0.00€';
}

function formatDate(value) {
    if (!value) return 'Not set';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? String(value)
        : date.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

function formatStatus(value) {
    if (!value) return 'Unknown';
    return String(value)
        .split('_')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function appendTextCell(container, value, className = '') {
    const cell = document.createElement('p');
    if (className) cell.className = className;
    cell.textContent = value;
    container.appendChild(cell);
}

function renderCards(cardsContainer, cards) {
    cardsContainer.replaceChildren();

    if (cards.length === 0) {
        appendTextCell(cardsContainer, 'No cards in this submission', 'empty-grading-submission');
        return;
    }

    const header = document.createElement('div');
    header.className = 'cards-header';
    [
        'Card name',
        'Card number',
        'Condition',
        'Submitted value',
        'Grading cost',
        'Grade',
        'Qualifier',
        'Certificate',
        'Market value',
    ].forEach(label => appendTextCell(header, label));
    cardsContainer.appendChild(header);

    cards.forEach(card => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card';
        cardElement.dataset.id = sanitizeNumericId(card.card_id);

        const gradeParts = [card.grade_numeric, card.grade_label].filter(value => value !== null && value !== undefined && value !== '');
        appendTextCell(cardElement, card.card_name || 'Unknown', 'card-info card-name');
        appendTextCell(cardElement, card.card_num || '', 'card-info card-num');
        appendTextCell(cardElement, card.condition || 'Unknown', 'card-info condition');
        appendTextCell(cardElement, formatCurrency(card.submitted_value), 'card-info submitted-value');
        appendTextCell(cardElement, formatCurrency(card.total_grading_cost), 'card-info grading-cost');
        appendTextCell(cardElement, gradeParts.join(' - ') || 'Pending', 'card-info grade');
        appendTextCell(cardElement, card.qualifier || '', 'card-info qualifier');
        appendTextCell(cardElement, card.cert_number || '', 'card-info cert-number');
        appendTextCell(
            cardElement,
            formatCurrency(card.post_grade_market_value ?? card.market_value),
            'card-info market-value',
        );
        cardsContainer.appendChild(cardElement);
    });
}

async function loadSubmissionCards(button) {
    if (button.dataset.loading === 'true') return;

    const submission = button.closest('.auction-tab');
    const cardsContainer = submission.querySelector('.cards-container');

    if (!cardsContainer.hidden) {
        cardsContainer.hidden = true;
        button.textContent = 'View';
        return;
    }

    cardsContainer.hidden = false;
    button.textContent = 'Hide';
    if (cardsContainer.dataset.loaded === 'true') return;

    button.dataset.loading = 'true';
    button.disabled = true;
    button.textContent = 'Loading';

    try {
        const submissionId = sanitizeNumericId(submission.dataset.id);
        const response = await csrfFetch(`/grading/submissions/${submissionId}`);
        if (!response.ok) throw new Error(`request failed with status ${response.status}`);

        const cards = await response.json();
        if (!Array.isArray(cards)) throw new Error('invalid cards response');

        renderCards(cardsContainer, cards);
        cardsContainer.dataset.loaded = 'true';
        button.textContent = 'Hide';
    } catch (error) {
        cardsContainer.hidden = true;
        button.textContent = 'View';
        renderAlert(`Error loading grading submission: ${error}`, 'error');
    } finally {
        button.dataset.loading = 'false';
        button.disabled = false;
    }
}

function renderSubmission(container, submission) {
    const submissionId = sanitizeNumericId(submission.id);
    const submissionElement = document.createElement('div');
    submissionElement.className = 'grading-tab auction-tab';
    submissionElement.id = submissionId;
    submissionElement.dataset.id = submissionId;

    const sharedCosts = [
        submission.outbound_shipping_cost,
        submission.return_shipping_cost,
        submission.insurance_cost,
        submission.customs_duty_cost,
        submission.other_shared_cost,
    ].reduce((total, value) => total + (Number(value) || 0), 0);

    appendTextCell(submissionElement, submission.grader || 'Unknown grader', 'auction-name');
    appendTextCell(submissionElement, submission.service_level || 'Standard', 'service-level');
    appendTextCell(submissionElement, formatStatus(submission.status), 'grading-status');
    appendTextCell(submissionElement, formatDate(submission.submitted_at), 'submitted-date');
    appendTextCell(submissionElement, formatDate(submission.returned_at), 'returned-date');
    appendTextCell(submissionElement, formatCurrency(sharedCosts), 'shared-cost');

    const buttonContainer = document.createElement('div');
    const viewButton = document.createElement('button');
    viewButton.className = 'view-auction';
    viewButton.dataset.id = submissionId;
    viewButton.textContent = 'View';
    buttonContainer.appendChild(viewButton);
    submissionElement.appendChild(buttonContainer);

    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'cards-container';
    cardsContainer.hidden = true;
    submissionElement.appendChild(cardsContainer);

    viewButton.addEventListener('click', () => loadSubmissionCards(viewButton));
    submissionElement.addEventListener('click', event => {
        if (event.target === submissionElement) loadSubmissionCards(viewButton);
    });

    if (submission.notes) submissionElement.title = submission.notes;
    container.appendChild(submissionElement);
}

async function loadSubmissions() {
    const container = document.querySelector('.grading-submissions-container');
    appendTextCell(container, 'Loading grading submissions...', 'grading-loading');

    try {
        const response = await csrfFetch('/grading/submissions');
        if (!response.ok) throw new Error(`request failed with status ${response.status}`);

        const submissions = await response.json();
        if (!Array.isArray(submissions)) throw new Error('invalid submissions response');

        container.replaceChildren();
        if (submissions.length === 0) {
            appendTextCell(container, 'No grading submissions found', 'empty-grading-submissions');
            return;
        }

        submissions.forEach(submission => renderSubmission(container, submission));
    } catch (error) {
        container.replaceChildren();
        renderAlert(`Error loading grading submissions: ${error}`, 'error');
    }
}

scrollOnLoad();
loadSubmissions();
