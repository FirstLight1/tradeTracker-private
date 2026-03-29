import {renderAlert} from './renderUtil.js';

export class CardStruct {
    constructor() {
        this.cardName = null;
        this.cardNum = null;
        this.condition = null;
        this.buyPrice = null;
        this.marketValue = null;
        this.sellPrice = null;
        this.soldDate = null;
    }
}

export class queue {
    constructor(size) {
        this.items = [];
        this.size = size;
        this.curr = 0;
        this.next = 1;
        this.prev = size - 1;
    }
    moveNext() {
        this.prev = this.curr;
        this.curr = this.next;
        this.next = (this.next + 1) % this.size;
    }
    movePrev() {
        this.next = this.curr;
        this.curr = this.prev;
        this.prev = (this.prev - 1 + this.size) % this.size;
    }

    enqueue(item) {
        if (this.items.length < this.size) {
            this.items.push(item);
        } else {
            this.items[this.curr] = item;
        }
    }
    getCurrent() {
        return this.items[this.curr];
    }
    getItem() {
        return this.items[this.curr];
    }
    printQueue() {
        console.log(this.items);
    }
}

export class CartLine {
    constructor(cardName, cardNum, condition, auctionName, marketValue, allIds) {
        this.cardName = cardName;
        this.cardNum = cardNum;
        this.condition = condition;
        this.auctionName = auctionName;
        this.marketValue = marketValue;
        this.cardIds = [allIds[0]];
        this.reservableIds = allIds.slice(1);
        this.element = null;
    }

    get quantity() { return this.cardIds.length; }
    get canIncrement() { return this.reservableIds.length > 0; }
    get canDecrement() { return this.cardIds.length > 0; }

    increment() {
        if (!this.canIncrement) { return null; }
        const id = this.reservableIds.shift();
        this.cardIds.push(id);
        return id;
    }

    decrement() {
        if (!this.canDecrement) { return null; }
        const id = this.cardIds.pop();
        this.reservableIds.unshift(id);
        return id;
    }

    removeAll() {
        return [...this.cardIds];
    }

    matches(cardName, cardNum, condition) {
        return this.cardName === cardName
            && this.cardNum === cardNum
            && this.condition === condition;
    }

    maxQuantity() {
        const quantity = this.cardIds.push(...this.reservableIds);
        this.reservableIds.length = 0;
        return quantity;
    }

    // For sessionStorage
    toJSON() {
        return {
            cardName: this.cardName,
            cardNum: this.cardNum,
            condition: this.condition,
            auctionName: this.auctionName,
            marketValue: this.marketValue,
            cardIds: this.cardIds,
            reservableIds: this.reservableIds
        };
    }

    // Restore from sessionStorage
    static fromJSON(data) {
        const line = new CartLine(
            data.cardName, data.cardNum, data.condition,
            data.auctionName, data.marketValue,
            [...data.cardIds, ...(data.reservableIds || [])]
        );
        // Override the constructor's default split
        line.cardIds = data.cardIds;
        line.reservableIds = data.reservableIds || [];
        return line;
    }

    // Expand for /invoice payload
    toInvoiceItems() {
        return this.cardIds.map(id => ({
            cardId: id,
            cardName: this.cardName,
            cardNum: this.cardNum,
            condition: this.condition,
            marketValue: this.marketValue
        }));
    }

    // Lazy backfill: fetch more IDs from server when reservableIds is empty
    async backfillPool(excludeIds) {
        if (this.reservableIds.length > 0) return;
        try {
            const response = await fetch('/getCardIds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    card_name: this.cardName,
                    card_num: this.cardNum,
                    condition: this.condition,
                    exclude_ids: [...excludeIds]
                })
            });
            if (!response.ok) {
                renderAlert('Failed to fetch card IDs: ' + response.status, 'error');
                return;
            }
            const data = await response.json();
            if (data.status === 'success' && data.card_ids) {
                this.reservableIds = data.card_ids.filter(id => !this.cardIds.includes(id));
            }
        } catch (e) {
            renderAlert('Error fetching card IDs: ' + e, 'error');
        }
    }
}