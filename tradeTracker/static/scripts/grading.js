import { renderAlert, renderServerErrors, scrollOnLoad } from './utils/renderUtil.js';
import { sanitizeNumericId, csrfFetch } from './utils/sanitizers.js';

const GRADING_STATUSES = ['preparing', 'sent_for_grading', 'received_by_grader'];
const ACTIVE_STATUSES = ['preparing', 'sent_for_grading', 'received_by_grader'];
const TERMINAL_STATUSES = ['graded', 'returned', 'cancelled'];

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
    if (value === 'returned') return 'Returned ungraded';
    return String(value)
        .split('_')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
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
    ].forEach((label) => appendTextCell(header, label));
    cardsContainer.appendChild(header);

    cards.forEach((card) => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card';
        cardElement.dataset.id = sanitizeNumericId(card.card_id);

        const gradeParts = [card.grade_numeric, card.grade_label].filter(
            (value) => value !== null && value !== undefined && value !== '',
        );
        appendTextCell(cardElement, card.card_name || 'Unknown', 'card-info card-name');
        appendTextCell(cardElement, card.card_num || '', 'card-info card-num');
        appendTextCell(cardElement, card.condition || 'Unknown', 'card-info condition');
        appendTextCell(
            cardElement,
            formatCurrency(card.submitted_value),
            'card-info submitted-value',
        );
        appendTextCell(
            cardElement,
            formatCurrency(card.total_grading_cost),
            'card-info grading-cost',
        );
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

function removeMutationButtons(submissionElement) {
    submissionElement.querySelector('.change-status')?.remove();
    submissionElement.querySelector('.complete')?.remove();
    submissionElement.querySelector('.mark-returned')?.remove();
    submissionElement.querySelector('.cancel-submission')?.remove();
}

function openStatusModal(button, submission, terminalStatus = null) {
    if (TERMINAL_STATUSES.includes(submission.status)) {
        renderAlert('Finalized grading submissions cannot be changed', 'error');
        return;
    }
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
    title.textContent =
        terminalStatus === 'returned'
            ? 'Mark submission returned ungraded'
            : 'Update grading submission';

    const statusLabel = document.createElement('label');
    statusLabel.htmlFor = 'grading-status-select';
    statusLabel.textContent = 'Status';

    const statusSelect = document.createElement('select');
    statusSelect.id = 'grading-status-select';
    statusSelect.name = 'status';
    const availableStatuses = terminalStatus ? [terminalStatus] : GRADING_STATUSES;
    availableStatuses.forEach((status) => {
        const option = document.createElement('option');
        option.value = status;
        option.textContent = formatStatus(status);
        statusSelect.appendChild(option);
    });
    statusSelect.value = terminalStatus || submission.status;
    statusLabel.hidden = Boolean(terminalStatus);
    statusSelect.hidden = Boolean(terminalStatus);

    const notesLabel = document.createElement('label');
    notesLabel.htmlFor = 'grading-notes';
    notesLabel.textContent = 'Note';

    const notes = document.createElement('textarea');
    notes.id = 'grading-notes';
    notes.name = 'notes';
    notes.rows = 5;
    notes.placeholder = 'Add a note about this submission';
    notes.value = submission.notes || '';

    const returnedDateLabel = document.createElement('label');
    returnedDateLabel.htmlFor = 'grading-returned-at';
    returnedDateLabel.textContent = 'Returned date';
    const returnedDate = document.createElement('input');
    returnedDate.id = 'grading-returned-at';
    returnedDate.name = 'returned_at';
    returnedDate.type = 'date';
    returnedDate.min = String(submission.submitted_at || '').slice(0, 10);
    const today = new Date();
    today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    returnedDate.value = today.toISOString().slice(0, 10);
    returnedDateLabel.hidden = true;
    returnedDate.hidden = true;

    const syncTerminalFields = () => {
        const returning = statusSelect.value === 'returned';
        returnedDateLabel.hidden = !returning;
        returnedDate.hidden = !returning;
        returnedDate.required = returning;
        notes.required = returning;
        notes.placeholder = returning
            ? 'Explain why the shipment was returned without grading'
            : 'Add a note about this submission';
    };
    statusSelect.addEventListener('change', syncTerminalFields);
    syncTerminalFields();

    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'modal-buttons';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.textContent = 'Cancel';

    const saveButton = document.createElement('button');
    saveButton.type = 'submit';
    saveButton.textContent = 'Save';

    buttonContainer.append(cancelButton, saveButton);
    content.append(
        closeButton,
        title,
        statusLabel,
        statusSelect,
        returnedDateLabel,
        returnedDate,
        notesLabel,
        notes,
        buttonContainer,
    );
    modal.appendChild(content);
    document.body.appendChild(modal);

    const close = () => {
        document.removeEventListener('keydown', handleKeydown);
        modal.remove();
        const submissionElement = button.closest('.auction-tab');
        const focusTarget = button.isConnected
            ? button
            : submissionElement?.querySelector('.view-auction');
        focusTarget?.focus();
    };
    const handleKeydown = (event) => {
        if (event.key === 'Escape') close();
    };

    closeButton.addEventListener('click', close);
    cancelButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) close();
    });
    document.addEventListener('keydown', handleKeydown);

    content.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!content.reportValidity()) return;
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
                    returned_at: statusSelect.value === 'returned' ? returnedDate.value : null,
                }),
            });
            const result = await response.json();
            if (!response.ok) {
                renderServerErrors(
                    result,
                    content,
                    {
                        notes: '#grading-notes',
                        returned_at: '#grading-returned-at',
                    },
                    'Unable to update grading submission',
                );
                saveButton.disabled = false;
                saveButton.textContent = 'Save';
                return;
            }

            submission.status = statusSelect.value;
            submission.notes = updatedNotes || null;
            const submissionElement = button.closest('.auction-tab');
            submissionElement.querySelector('.grading-status').textContent = formatStatus(
                submission.status,
            );
            if (submission.status === 'returned') {
                submission.returned_at = returnedDate.value;
                submissionElement.querySelector('.returned-date').textContent = formatDate(
                    submission.returned_at,
                );
            }
            if (TERMINAL_STATUSES.includes(submission.status)) {
                removeMutationButtons(submissionElement);
            }
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

    if (terminalStatus === 'returned') returnedDate.focus();
    else statusSelect.focus();
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
    buttonContainer.innerHTML = `
        <button class='view-auction' data-id=${submissionId}>View</button>
        ${ACTIVE_STATUSES.includes(submission.status) ? `<button class='change-status' data-id=${submissionId}>Change Status</button>` : ''}
        `;
    if (ACTIVE_STATUSES.includes(submission.status)) {
        const completeButton = document.createElement('button');
        completeButton.classList.add('complete');
        completeButton.type = 'button';
        completeButton.setAttribute('data-id', submissionId);
        completeButton.textContent = 'Complete';
        completeButton.addEventListener('click', () => {
            if (!ACTIVE_STATUSES.includes(submission.status)) return;
            window.location.href = `/grading/submissions/${submissionId}/complete`;
        });
        buttonContainer.append(completeButton);

        const returnedButton = document.createElement('button');
        returnedButton.className = 'mark-returned';
        returnedButton.type = 'button';
        returnedButton.textContent = 'Mark returned ungraded';
        buttonContainer.append(returnedButton);

        const cancelSubmissionButton = document.createElement('button');
        cancelSubmissionButton.className = 'cancel-submission';
        cancelSubmissionButton.type = 'button';
        cancelSubmissionButton.textContent = 'Cancel submission';
        buttonContainer.append(cancelSubmissionButton);
    }
    submissionElement.appendChild(buttonContainer);

    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'cards-container';
    cardsContainer.hidden = true;
    submissionElement.appendChild(cardsContainer);

    const viewButton = buttonContainer.querySelector('.view-auction');
    const changeStatusButton = buttonContainer.querySelector('.change-status');
    const returnedButton = buttonContainer.querySelector('.mark-returned');
    const cancelSubmissionButton = buttonContainer.querySelector('.cancel-submission');
    viewButton.addEventListener('click', () => loadSubmissionCards(viewButton));
    changeStatusButton?.addEventListener('click', () =>
        openStatusModal(changeStatusButton, submission),
    );
    returnedButton?.addEventListener('click', () =>
        openStatusModal(returnedButton, submission, 'returned'),
    );
    cancelSubmissionButton?.addEventListener('click', async () => {
        if (!window.confirm('Cancel this submission and release its cards back to raw inventory?'))
            return;
        cancelSubmissionButton.disabled = true;
        try {
            const response = await csrfFetch(`/grading/submissions/${submissionId}/cancel`, {
                method: 'POST',
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok)
                throw new Error(result.message || `request failed with status ${response.status}`);
            submission.status = 'cancelled';
            submissionElement.querySelector('.grading-status').textContent = formatStatus(
                submission.status,
            );
            removeMutationButtons(submissionElement);
            renderAlert('Grading submission cancelled', 'message');
        } catch (error) {
            renderAlert(`Error cancelling grading submission: ${error}`, 'error');
            cancelSubmissionButton.disabled = false;
        }
    });
    submissionElement.addEventListener('click', (event) => {
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

        submissions.forEach((submission) => renderSubmission(container, submission));
    } catch (error) {
        container.replaceChildren();
        renderAlert(`Error loading grading submissions: ${error}`, 'error');
    }
}

scrollOnLoad();
loadSubmissions();
