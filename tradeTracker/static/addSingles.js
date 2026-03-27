import {createNewCard, struct} from './addAuction.js'
import {renderAlert} from './main.js'

const cardsArr = [];
const saveButton = document.querySelector('.save-btn')

saveButton.addEventListener('click', () => {
    let auction = {};
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
            card.soldDate = null;
            if(card.sellPrice === null){
            card.sellPrice = card.marketValue;
            }
            if(card.buyPrice === null){
                card.buyPrice = (card.marketValue * 0.80).toFixed(2);
            }
            if(card.cardName !== null && card.marketValue !== null){
                cardsArr.push(card);
            }
        });


        if (cardsArr.length !== 1){
            const jsonbody = JSON.stringify(cardsArr);
            fetch('/addToSingles', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: jsonbody,
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    window.location.href = '/';
                }
            })
                .catch(error => {
                    renderAlert('Error: ' + error, 'error');
                });
        }
});

const addCardButton = document.querySelector('.add-card');
addCardButton.addEventListener('click', () =>{
    const cards = document.querySelectorAll('.card');
    const card = cards[0];
    const container = document.querySelector(".cards-container")
    const newCard = createNewCard(card.cloneNode(true));
})
