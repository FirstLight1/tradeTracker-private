import { renderField, renderAlert, scrollOnLoad } from "./main.js";

const BULK_TYPE_BUY_PRICES = {
    bulk: 0.01,
    holo: 0.03,
    ex: 0.15
};

async function loadContent(button, soldDate) {
    const formattedDate = `${soldDate.getDate().toString().padStart(2, '0')}.${(soldDate.getMonth() + 1).toString().padStart(2, '0')}.${soldDate.getFullYear()}`;
    const saleId = button.getAttribute('data-id');
    const saleEntry = button.closest('.auction-tab');
    const cardsContainer = saleEntry.querySelector('.cards-container');
    if (cardsContainer.childElementCount === 0 || cardsContainer.style.display === 'none') {
        const response = await fetch('/loadSoldCards/' + saleId);
        const soldItems = await response.json();
        cardsContainer.style.display = 'flex';
        button.textContent = 'Hide';

        if (soldItems.length === 0) {
            cardsContainer.innerHTML = '';
        } else {
            cardsContainer.innerHTML = `
                <div class="cards-header">
                    <p>Card name</p>
                    <p>Card number</p>
                    <p>Condition</p>
                    <p>Buy price</p>
                    <p>Market value</p>
                    <p>Sell price</p>
                    <p>Margin</p>
                    <p>Sold Date</p>
                </div>
            `;
            const soldCards = soldItems.cards;
            const sealedSales = soldItems.sealed;
            const bulkSales = soldItems.bulk_sales;

            soldCards.forEach(card => {
                const cardElement = document.createElement('div');
                cardElement.classList.add('card');



                cardElement.innerHTML = `
                    ${renderField(card.card_name, 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                    ${renderField(card.card_num, 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                    <p class='card-info condition ${card.condition.split(' ').join('_').toLowerCase()}' data-field="condition">${card.condition ? card.condition : 'Unknown'}</p>
                    ${renderField(card.card_price ? card.card_price + '€' : null, 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                    ${renderField(card.market_value ? card.market_value + '€' : null, 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                    ${renderField(card.invoice_sell_price ? card.invoice_sell_price + '€' : null, 'text', ['card-info', 'sell-price'], 'Sell Price', 'sell_price')}
                    <p>${card.invoice_sell_price && card.card_price ? (card.invoice_sell_price - card.card_price).toFixed(2) + '€' : 'Unknown'}</p>
                    <p>${formattedDate}</p>
                    
                    <span hidden class = "card-id">${card.id}</span>
                `;
                cardsContainer.appendChild(cardElement);
            });
            sealedSales.forEach(item => {
                const sealedDiv = document.createElement('div');
                sealedDiv.classList.add('card');

                sealedDiv.innerHTML = `
                    <p class='card-info card-name'>${item.name}</p>
                    <p class='card-info card-num'></p>
                    <p class='card-info condition'></p>
                    <p class='card-info card-price'></p>
                    <p class='card-info market-value'>${item.market_value}</p>
                    <p class='card-info sell-price'>${item.market_value}</p>
                    <p>${item.market_value !== null && item.price !== null ? (item.market_value - item.price).toFixed(2) + '€' : 'Unknown'}</p>
                    <p>${formattedDate}</p>
                    <span hidden class = "sid">${item.id}</span>
                    `;
                cardsContainer.appendChild(sealedDiv);
            });

            bulkSales.forEach(bulk => {
                const bulkElement = document.createElement('div');
                bulkElement.classList.add('card');

                const buy_price = BULK_TYPE_BUY_PRICES[bulk.item_type] ?? 0;
                bulkElement.innerHTML = `
                    <p class='card-info card-name'>${bulk.item_type}</p>
                    <p class='card-info card-num'></p>
                    <p class='card-info condition'></p>
                    <p class='card-info card-price'></p>
                    <p class='card-info market-value'>Počet: ${bulk.quantity}</p>
                    <p class='card-info sell-price'>${bulk.total_price != null ? bulk.total_price + '€' : 'Unknown'}</p>
                    <p>${bulk.total_price !== null && bulk.quantity !== null && bulk.unit_price !== null ? (bulk.total_price - bulk.quantity * buy_price).toFixed(2) + '€' : 'Unknown'}</p>
                    <p>${formattedDate}</p>
                    <span hidden class = "bulk-id">${bulk.id}</span>
                `;
                cardsContainer.appendChild(bulkElement);
            });
        }
    } else {
        cardsContainer.style.display = 'none';
        button.textContent = 'View';
    }
}

async function loadHistory() {
    const response = await fetch('/loadSoldHistory');
    const sales = await response.json();
    const historyContainer = document.querySelector('.sales-history-container');
    sales.forEach(sale => {
        const saleElement = document.createElement('div');
        saleElement.classList.add('sold-tab');
        saleElement.classList.add('auction-tab');
        saleElement.id = `${sale.id}`;
        saleElement.setAttribute('data-id', sale.id);
        const saleDate = new Date(sale.sale_date);
        const formattedDate = `${saleDate.getDate().toString().padStart(2, '0')}.${(saleDate.getMonth() + 1).toString().padStart(2, '0')}.${saleDate.getFullYear()}`;
        let name = "";
        try {
            const recieverInfo = JSON.parse(sale.notes);
            name = recieverInfo.nameAndSurname;
        } catch (e) {
            name = sale.notes;
        }
        saleElement.innerHTML = `
            <p class="auction-name">Invoice #${sale.invoice_number} - ${formattedDate}</p>
            <p class="auction-price">Celková suma: ${sale.total_amount}€</p>
            <p>Marža: ${sale.total_profit ? sale.total_profit.toFixed(2) : '0.00'}€</p>
            <p>${name}</p>
            <button class="view-auction" data-id="${sale.id}">View</button>
            <button class="return" data-id="${sale.id}" >Return</button>
            ${sale.auction_id === null ?
                `<p></p>`
                : `<span class='auction-link-hint'><a href='/#${sale.auction_id}'><img class='link-img' src="https://upload.wikimedia.org/wikipedia/en/3/3d/480px-Gawr_Gura_-_Portrait_01.png" alt="Show auction"></a></span>`
            } 
            <div class="cards-container">
            <!-- Cards will be loaded here -->
            </div>
            `;
        historyContainer.appendChild(saleElement);

        const viewButton = saleElement.querySelector('.view-auction');
        viewButton.addEventListener('click', () => {
            loadContent(viewButton, saleDate);
        });
        saleElement.addEventListener('click', (event) => {
            if (event.target !== viewButton) {
                loadContent(viewButton, saleDate);
            }
        });

        const returnButton = saleElement.querySelector('.return');
        returnButton.addEventListener('click', async (event) => {
            event.stopPropagation();
            const saleId = returnButton.getAttribute('data-id');
            if (returnButton.textContent === 'Confirm') {
                returnButton.disabled = true;
                returnButton.textContent = 'Processing...';
                try {
                    const cnResponse = await fetch(`/generateCreditNote/${saleId}`);
                    const cnData = await cnResponse.json();
                    //TODO - This needs a refactor, cause CN is generated even tho the return could fail
                    if (cnData.status !== 'success') {
                        renderAlert('Error generating credit note: ' + cnData.message, 'error');
                        returnButton.disabled = false;
                        returnButton.textContent = 'Return';
                        return;
                    }
                    const returnResponse = await fetch(`/orderReturn/${saleId}`);
                    const returnData = await returnResponse.json();
                    if (returnData.status !== 'success') {
                        renderAlert('Error processing return: ' + returnData.message, 'error');
                        returnButton.disabled = false;
                        returnButton.textContent = 'Return';
                        return;
                    }
                    alert(`${cnData.pdf_path}`);
                    //TODO - improve this, cause rn you can barely see the alert let alone copy it
                    window.location.reload();
                } catch (e) {
                    renderAlert('Error processing return: ' + e, 'error');
                    returnButton.disabled = false;
                    returnButton.textContent = 'Return';
                }
            } else {
                returnButton.textContent = 'Confirm';
                const timerID = setTimeout(() => {
                    returnButton.textContent = 'Return';
                }, 3000);
                document.addEventListener('click', function handler(e) {
                    if (e.target !== returnButton) {
                        returnButton.textContent = 'Return';
                        document.removeEventListener('click', handler);
                        clearTimeout(timerID);
                    }
                });
            }
        });
    });
}

loadHistory();
scrollOnLoad();
