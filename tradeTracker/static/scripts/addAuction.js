import {updateInventoryValueAndTotalProfit, renderAlert} from "./main.js";

const ALLOWED_PAYMENT_TYPES = new Set([
    'Hotovosť',
    'Karta',
    'Barter',
    'Bankový prevod',
    'Online platba',
    'Dobierka',
    'Online platobný systém'
]);

function validatePayments(payments) {
    if (!payments || payments.length === 0) {
        return { valid: true }; // Payments are optional
    }
    
    if (payments.length > 10) {
        return { valid: false, error: 'Too many payment methods (max 10)' };
    }
    
    for (const payment of payments) {
        if (!ALLOWED_PAYMENT_TYPES.has(payment.type)) {
            return { valid: false, error: 'Invalid payment type selected' };
        }
        
        const amount = parseFloat(payment.amount);
        if (isNaN(amount) || amount < 0) {
            return { valid: false, error: 'Invalid payment amount' };
        }
        
        if (amount > 1000000) {
            return { valid: false, error: 'Payment amount too large' };
        }
    }
    
    return { valid: true };
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

export class struct{
    constructor(){
        this.cardName = null;
        this.cardNum = null;
        this.condition = null;
        this.buyPrice = null;
        this.marketValue = null;
        this.sellPrice = null;
        this.soldDate = null;
    }
}

const cardsArr = [];
let totalSellValue = 0;
let auctionValueCalculated = 0;
const saveButton = document.querySelector('.save-btn')
//add typechecks
saveButton.addEventListener('click', () =>{
    const auctionName = document.querySelector('.auction-name').value;
    const auctionBuy = document.querySelector('.auction-buy-price').value;
    const date = new Date().toISOString();
    
    // Collect all payment rows
    const paymentRows = document.querySelectorAll('.payment-row');
    const payments = [];
    paymentRows.forEach(row => {
        const type = row.querySelector('.payment-type-select').value;
        const amount = parseFloat(row.querySelector('.payment-amount-input').value) || 0;
        if (type) {
            payments.push({type, amount});
        }
    });
    
    let auction = {
        name: auctionName.trim() || null,
        buy: auctionBuy ? parseFloat(auctionBuy.replace(',','.')) : null,
        date: date.trim() || null,
        payments: payments.length > 0 ? payments : null
    };
    
    // Validate payments
    if (auction.payments) {
        const validation = validatePayments(auction.payments);
        if (!validation.valid) {
            renderAlert('Payment validation error: ' + validation.error, 'error');
            return;
        }
    }
    
    if(cardsArr.length === 0){
        cardsArr.push(auction);
    }

    const cards = document.querySelectorAll('.card');
    cards.forEach(ell =>{
        let card = new struct();
        const input = (selector) => ell.querySelector(selector)?.value.trim().toUpperCase() || null;
        const inputNumber = (selector) => {
            const val = ell.querySelector(selector)?.value.trim();
                if(!val){
                    return null;
                }
            return parseFloat(val.replace(',', '.'));
        };
        card.cardName = input('input[name=cardName]');
        card.cardNum = input('input[name=cardNum]');
        card.condition = input('select[name=condition]');
        card.buyPrice = inputNumber('input[name=buyPrice]');
        card.marketValue = inputNumber('input[name=marketValue]');
        card.sellPrice = inputNumber('input[name=sellPrice]');
        if(card.sellPrice === null){
            card.sellPrice = card.marketValue;
        }
        if(card.buyPrice === null && card.marketValue !== null){
            card.buyPrice = parseFloat((card.marketValue * 0.80).toFixed(2));
        }
        auctionValueCalculated += card.buyPrice || 0;
        if(card.cardName !== null && card.marketValue !== null){
            cardsArr.push(card);
        }
    });


    if(!cardsArr[0].buy){
        cardsArr[0].buy = parseFloat(auctionValueCalculated.toFixed(2));
    }

    if (cardsArr.length !== 1){
        const jsonbody = JSON.stringify(cardsArr);
        fetch('/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: jsonbody
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.message || 'Server error');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                window.location.href = '/';
            } else {
                renderAlert('Error: ' + (data.message || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            renderAlert('Failed to save auction: ' + error.message, 'error');
        });
    }
})

const addCardButton = document.querySelector('.add-card');
addCardButton.addEventListener('click', () =>{
    const cards = document.querySelectorAll('.card');
    const card = cards[0];
    const container = document.querySelector(".cards-container")
    const newCard = createNewCard(card.cloneNode(true));

    container.append(newCard);
})

// Payment row management
const addPaymentRowBtn = document.querySelector('.add-payment-row-btn');
const paymentRowsContainer = document.querySelector('.payment-rows-container');

function createPaymentRow() {
    const row = document.createElement('div');
    row.classList.add('payment-row');
    row.innerHTML = `
        <select class="payment-type-select">
            <option value=''>Select payment method</option>
            <option value="Hotovosť">Hotovosť</option>
            <option value="Karta">Karta</option>
            <option value="Bankový prevod">Bankový prevod</option>
            <option value="Online platba">Online platba</option>
            <option value="Dobierka">Dobierka</option>
            <option value="Online platobný systém">Online platobný systém</option>
        </select>
        <input type="number" class="payment-amount-input" step="0.01" min="0" placeholder="Amount" autocomplete="off">
        <button type="button" class="remove-payment-btn">×</button>
    `;
    return row;
}

function attachRemoveListener(row) {
    const removeBtn = row.querySelector('.remove-payment-btn');
    removeBtn.addEventListener('click', () => {
        if (paymentRowsContainer.children.length > 1) {
            row.remove();
        } else {
            renderAlert('At least one payment row is required', 'error');
        }
    });
}

addPaymentRowBtn.addEventListener('click', () => {
    const newRow = createPaymentRow();
    paymentRowsContainer.appendChild(newRow);
    attachRemoveListener(newRow);
});

// Attach listener to initial row
attachRemoveListener(document.querySelector('.payment-row'));

document.addEventListener('DOMContentLoaded', async () => {
    await updateInventoryValueAndTotalProfit();
}, false);
