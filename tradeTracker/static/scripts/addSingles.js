import { CardStruct } from './utils/classes.js';
import { renderAlert, createNewCard } from './utils/renderUtil.js';
import { csrfFetch } from './utils/sanitizers.js';

const cardsArr = [];
const saveButton = document.querySelector('.save-btn');
const initialMarketValueInput = document.querySelector('.card .marketValue');

if (initialMarketValueInput) {
    initialMarketValueInput.addEventListener('input', function () {
        window.handleCardInput(this);
    });
}

saveButton.addEventListener('click', () => {
    cardsArr.length = 0;

    const cards = document.querySelectorAll('.card');
    cards.forEach((ell) => {
        const card = new CardStruct();
        const input = (selector) =>
            DOMPurify.sanitize(ell.querySelector(selector)?.value.trim().toUpperCase()) || null;
        const inputNumber = (selector) => {
            const val = DOMPurify.sanitize(ell.querySelector(selector)?.value.trim());
            if (!val) {
                return null;
            }
            return parseFloat(val.replace(',', '.'));
        };
        card.name = input('input[name=cardName]');
        card.number = input('input[name=cardNum]');
        card.condition = input('select[name=condition]');
        card.lang = DOMPurify.sanitize(ell.querySelector('select[name=language]').value);
        card.buy_price = inputNumber('input[name=buyPrice]');
        card.market_value = inputNumber('input[name=marketValue]');
        card.sell_price = inputNumber('input[name=sellPrice]');
        if (card.sell_price === null) {
            card.sell_price = card.market_value;
        }
        if (card.buy_price === null) {
            card.buy_price = Number((card.market_value * 0.8).toFixed(2));
        }
        if (card.name !== null && card.market_value !== null) {
            cardsArr.push(card);
        }
    });

    if (cardsArr.length > 0) {
        const jsonbody = JSON.stringify(cardsArr);
        csrfFetch('/addToSingles', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: jsonbody,
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === 'success') {
                    window.location.href = '/';
                }
            })
            .catch((error) => {
                renderAlert('Error: ' + error, 'error');
            });
    }
});

const addCardButton = document.querySelector('.add-card');
addCardButton.addEventListener('click', () => {
    const cards = document.querySelectorAll('.card');
    const card = cards[0];
    const container = document.querySelector('.cards-container');
    const newCard = createNewCard(card.cloneNode(true));
    container.append(newCard);
});
