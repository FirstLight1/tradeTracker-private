import { csrfFetch, escapeHtml, sanitizeNumericId, sanitizeClassToken } from "./sanitizers.js";
import { renderAlert } from "./renderUtil.js";

export class DebitNoteItem {
    constructor({ type, cardName, cardNum, condition, marketValue, sid, cardIds, quantity, addedIds }) {
        this.type = type;
        this.cardName = cardName;
        this.cardNum = cardNum;
        this.condition = condition;
        this.marketValue = marketValue;
        this.sid = sid;
        this.cardIds = cardIds;
        this.quantity = quantity;
        this.addedIds = addedIds;
        this.elements = [];
    }

    get ids() {
        return this.type === 'card' ? [...this.cardIds] : [this.sid];
    }

    render() {
        this.elements = [];
        if (this.type === 'card') {
            this.cardIds.forEach(id => {
                const row = document.createElement('div');
                row.classList.add('card', 'creditnote-item-row', 'debitnote-item-row');
                row.setAttribute('data-id', sanitizeNumericId(id));
                const condClass = sanitizeClassToken(this.condition || '');
                row.innerHTML = `
                    <div class="item-info">
                        <p class="item-name">${escapeHtml(this.cardName || '')}</p>
                        <p class="item-number">${escapeHtml(this.cardNum || '')}</p>
                    </div>
                    <p class="item-condition ${condClass}">${escapeHtml(this.condition || '')}</p>
                    <p class="market-value">${escapeHtml(String(this.marketValue ?? ''))}<span class="currency">€</span></p>
                    <button class="item-remove-btn" type="button">X</button>
                `;
                row.querySelector('.item-remove-btn').addEventListener('click', () => {
                    row.remove();
                    this.addedIds.delete(id);
                    this.elements = this.elements.filter(el => el !== row);
                    document.querySelector('.creditnote-total .total-amount').textContent = (Number(document.querySelector('.creditnote-total .total-amount').textContent) - Number(this.marketValue)).toFixed(2);
                });
                this.elements.push(row);
            });
        } else {
            const row = document.createElement('div');
            row.classList.add('sealed-item', 'creditnote-item-row', 'debitnote-item-row');
            row.setAttribute('data-id', sanitizeNumericId(this.sid));
            row.innerHTML = `
                <p class="item-quantity">${sanitizeNumericId(this.quantity)}</p>
                <p class="item-name">${escapeHtml(this.cardName || '')}</p>
                <p class="market-value">${escapeHtml(String(this.marketValue ?? ''))}<span class="currency">€</span></p>
                <button class="item-remove-btn" type="button">X</button>
            `;
            row.querySelector('.item-remove-btn').addEventListener('click', () => {
                row.remove();
                this.addedIds.delete(this.sid);
                this.elements = this.elements.filter(el => el !== row);
                document.querySelector('.creditnote-total .total-amount').textContent = (Number(document.querySelector('.creditnote-total .total-amount').textContent) - Number(this.marketValue * this.quantity)).toFixed(2);
            });
            this.elements.push(row);
        }
        return this.elements;
    }

    static async fromSearchResult(result, pendingQty, addedIds) {
        const isSealed = Object.prototype.hasOwnProperty.call(result, 'sid');
        if (isSealed) {
            if (addedIds.has(result.sid)) {
                renderAlert('This item is already added', 'error');
                return null;
            }
            addedIds.add(result.sid);
            return new DebitNoteItem({
                type: 'sealed',
                sid: result.sid,
                cardName: result.name,
                marketValue: result.market_value,
                quantity: pendingQty,
                addedIds,
            });
        }

        const ids = await DebitNoteItem._fetchCardIds(result, [...addedIds]);
        if (ids.length === 0) {
            renderAlert('No more available copies of this card', 'error');
            return null;
        }
        if (ids.length < pendingQty) {
            renderAlert(`Only ${ids.length} available (requested ${pendingQty})`, 'error');
        }
        const taken = ids.slice(0, pendingQty);
        taken.forEach(id => addedIds.add(id));
        return new DebitNoteItem({
            type: 'card',
            cardName: result.card_name,
            cardNum: result.card_num,
            condition: result.condition,
            marketValue: result.market_value,
            cardIds: taken,
            addedIds,
        });
    }

    static async _fetchCardIds(result, excludeIds) {
        const resp = await csrfFetch('/getCardIds', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_name: result.card_name,
                card_num: result.card_num,
                condition: result.condition,
                exclude_ids: excludeIds,
            }),
        });
        const data = await resp.json();
        return data.status === 'success' ? (data.card_ids || []) : [];
    }
}
