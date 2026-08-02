import { renderAlert, scrollOnLoad } from "./utils/renderUtil.js";
import { sanitizeNumericId, csrfFetch } from "./utils/sanitizers.js";

const GRADING_STATUSES = [
    'preparing',
    'sent_for_grading',
    'received_by_grader',
    'graded',
    'returned',
    'cancelled',
];

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
        appendTextCell(cardElement, gradeParts.join(' - ') || '', 'card-info grade');
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

function openStatusModal(button, submission) {
    const modal = document.createElement('div');
    modal.className = 'reciever-div grading-status-overlay';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'grading-status-title');

    const content = document.createElement('form');
    content.className = 'modal-content grading-status-modal';

    const closeButton = document.createElement('button');
    closeButton.className = 'close-modal';
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close');
    closeButton.textContent = '\u00d7';

    const title = document.createElement('h2');
    title.id = 'grading-status-title';
    title.textContent = 'Update grading submission';

    const statusLabel = document.createElement('label');
    statusLabel.htmlFor = 'grading-status-select';
    statusLabel.textContent = 'Status';

    const statusSelect = document.createElement('select');
    statusSelect.id = 'grading-status-select';
    statusSelect.name = 'status';
    GRADING_STATUSES.forEach(status => {
        const option = document.createElement('option');
        option.value = status;
        option.textContent = formatStatus(status);
        statusSelect.appendChild(option);
    });
    statusSelect.value = submission.status;

    const notesLabel = document.createElement('label');
    notesLabel.htmlFor = 'grading-notes';
    notesLabel.textContent = 'Note';

    const notes = document.createElement('textarea');
    notes.id = 'grading-notes';
    notes.name = 'notes';
    notes.rows = 5;
    notes.placeholder = 'Add a note about this submission';
    notes.value = submission.notes || '';

    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'modal-buttons';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.textContent = 'Cancel';

    const saveButton = document.createElement('button');
    saveButton.type = 'submit';
    saveButton.textContent = 'Save';

    buttonContainer.append(cancelButton, saveButton);
    content.append(closeButton, title, statusLabel, statusSelect, notesLabel, notes, buttonContainer);
    modal.appendChild(content);
    document.body.appendChild(modal);

    const close = () => {
        document.removeEventListener('keydown', handleKeydown);
        modal.remove();
        button.focus();
    };
    const handleKeydown = event => {
        if (event.key === 'Escape') close();
    };

    closeButton.addEventListener('click', close);
    cancelButton.addEventListener('click', close);
    modal.addEventListener('click', event => {
        if (event.target === modal) close();
    });
    document.addEventListener('keydown', handleKeydown);

    content.addEventListener('submit', async event => {
        event.preventDefault();
        saveButton.disabled = true;
        saveButton.textContent = 'Saving';

        const submissionId = sanitizeNumericId(submission.id);
        const updatedNotes = notes.value.trim();

        try {
            const response = await csrfFetch(`/grading/submissions/${submissionId}/updateStatus`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    status: statusSelect.value,
                    notes: updatedNotes || null,
                }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || `request failed with status ${response.status}`);

            submission.status = statusSelect.value;
            submission.notes = updatedNotes || null;
            const submissionElement = button.closest('.auction-tab');
            submissionElement.querySelector('.grading-status').textContent = formatStatus(submission.status);
            if (submission.notes) {
                submissionElement.title = submission.notes;
            } else {
                submissionElement.removeAttribute('title');
            }
            close();
            renderAlert('Grading submission updated', 'message');
        } catch (error) {
            renderAlert(`Error updating grading submission: ${error}`, 'error');
            saveButton.disabled = false;
            saveButton.textContent = 'Save';
        }
    });

    statusSelect.focus();
}

function renderSubmission(container, submission) {
    const completable = ['preparing', 'sent_for_grading', 'received_by_grader'];
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
    buttonContainer.innerHTML = `
        <button class='view-auction' data-id=${submissionId}>View</button>
        <button class='change-status' data-id=${submissionId}>Change Status</button>
        `;
    if (completable.includes(submission.status)) {
        const completeButton = document.createElement('button');
        completeButton.classList.add('complete');
        completeButton.setAttribute('data-id', submissionId);
        completeButton.innerHTML = `<a href='grading/submissions/${submissionId}/complete'>Complete</a>`;
        buttonContainer.append(completeButton);
    }
    submissionElement.appendChild(buttonContainer);

    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'cards-container';
    cardsContainer.hidden = true;
    submissionElement.appendChild(cardsContainer);

    const viewButton = buttonContainer.querySelector('.view-auction');
    const changeStatusButton = buttonContainer.querySelector('.change-status');
    viewButton.addEventListener('click', () => loadSubmissionCards(viewButton));
    changeStatusButton.addEventListener('click', () => openStatusModal(changeStatusButton, submission));
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
