import { renderField, renderAlert, scrollOnLoad, downloadFile } from "./utils/renderUtil.js";
import { escapeHtml, sanitizeNumericId, sanitizeClassToken, csrfFetch } from "./utils/sanitizers.js";
import "./headerActions.js";


function parsePaymentMethods(paymentMethodData) {
    if (!paymentMethodData) return [];

    try {
        const parsed = JSON.parse(paymentMethodData);
        if (Array.isArray(parsed)) return parsed;
    } catch (e) {
        return paymentMethodData.trim().split(' ').map(type => ({ type: type, amount: 0 }));
    }

    return [];
}

function formatPaymentDisplay(payments) {
    if (!payments || payments.length === 0) return 'No payment method';

    return payments.map(p => {
        const type = escapeHtml(p.type || '');
        const amount = parseFloat(p.amount || 0).toFixed(2);
        return `${type}: ${amount}€`;
    }).join('<br>');
}

function isEmpty(obj) {
    return Object.keys(obj).length === 0;
}

function formatSealedDate(rawDate) {
    if (!rawDate) return '';
    const timeStamp = String(rawDate).replace('Z', '');
    const date = new Date(timeStamp);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

async function loadAuctionContent(button) {
    const auctionId = Number(button.getAttribute('data-id'));
    const cardsUrl = '/loadAllCards/' + auctionId;
    const sealedUrl = '/loadAllSealed/' + auctionId;
    const auctionDiv = button.closest('.auction-tab');
    const cardsContainer = auctionDiv.querySelector('.cards-container');
    try {
        if (cardsContainer.childElementCount === 0 || cardsContainer.hidden) {
            cardsContainer.hidden = false;
            button.textContent = 'Hide';

            if (cardsContainer.childElementCount === 0) {
                const response = await csrfFetch(cardsUrl);
                const cards = await response.json();
                if (isEmpty(cards)) {
                    cardsContainer.innerHTML = '';
                } else {
                    cardsContainer.innerHTML = `
                    <div class="cards-header">
                        <p>Card name</p>
                        <p>Card number</p>
                        <p>Condition</p>
                        <p>Buy price</p>
                        <p>Market value</p>
                        <p>Margin</p>
                        <p></p>
                        <p></p>
                        <p></p>
                    </div>
                `;
                    cards.forEach(card => {
                        const safeCardConditionClass = sanitizeClassToken(card.condition || 'Unknown');
                        const cardDiv = document.createElement('div');
                        cardDiv.classList.add('card');
                        cardDiv.innerHTML = `
                        ${renderField(card.card_name != null ? DOMPurify.sanitize(card.card_name) : '', 'text', ['card-info', 'card-name'], 'Card Name', 'card_name')}
                        ${renderField(card.card_num != null ? DOMPurify.sanitize(card.card_num) : '', 'text', ['card-info', 'card-num'], 'Card Number', 'card_num')}
                        <p class='card-info condition ${safeCardConditionClass}' data-field="condition">${DOMPurify.sanitize(card.condition) ? DOMPurify.sanitize(card.condition) : 'Unknown'}</p>
                        ${renderField(card.card_price != null ? DOMPurify.sanitize(card.card_price) + '€' : '', 'text', ['card-info', 'card-price'], 'Card Price', 'card_price')}
                        ${renderField(card.market_value != null ? DOMPurify.sanitize(card.market_value) + '€' : '', 'text', ['card-info', 'market-value'], 'Market Value', 'market_value')}
                        ${renderField(card.card_price !== null && card.market_value !== null ? (card.market_value - card.card_price).toFixed(2) + '€' : '', 'text', ['card-info', 'profit'], 'profit', true)}
                        <p>${card.sold_date != null ? 'Sold' : ''}</p>
                        <p></p>
                        <p></p>
                    `;
                        cardsContainer.appendChild(cardDiv);
                    });
                }

                try {
                    const responseSealed = await csrfFetch(sealedUrl);
                    const sealedData = await responseSealed.json();

                    sealedData.forEach(sealedItem => {
                        const sealedDiv = document.createElement('div');
                        sealedDiv.classList.add('sealed-item');
                        console.log(sealedItem);
                        let state = '';
                        if (sealedItem.opened) {
                            state = 'Opened';
                        } else if (sealedItem.sale_id != null) {
                            state = 'Sold';
                        }

                        const margin = (Number(sealedItem.market_value) - Number(sealedItem.price)).toFixed(2);

                        sealedDiv.innerHTML = `
                            <p class='sealed-quantity'>${DOMPurify.sanitize(sealedItem.quantity)}</p>
                            <p class="sealed-name">${DOMPurify.sanitize(sealedItem.name)}</p>
                            <p class="sealed-price">${DOMPurify.sanitize(sealedItem.price)}€</p>
                            <p class="VAT-sealed">${(Number(DOMPurify.sanitize(sealedItem.price)) / 1.23).toFixed(2)}</p>
                            <p class="sealed-market-value">${DOMPurify.sanitize(sealedItem.market_value)}€</p>
                            <p class="sealed-margin">${DOMPurify.sanitize(margin)}€</p>
                            <p></p>
                            <p>${state}</p>
                            <p></p>
                            <p></p>
                        `;

                        cardsContainer.appendChild(sealedDiv);
                    });
                } catch (error) {
                    renderAlert('Error loading sealed items: ' + error, 'error');
                }
            }
        } else {
            cardsContainer.hidden = true;
            button.textContent = 'View';
        }
    } catch (error) {
        renderAlert('Error loading cards: ' + error, 'error');
    }
}

async function loadAuctions() {
    const auctionContainer = document.querySelector('.auction-container');
    try {
        const response = await csrfFetch('/loadPurchases');
        const data = await response.json();
        data.forEach(auction => {
            const safeAuctionId = sanitizeNumericId(auction.id);
            const auctionDiv = document.createElement('div');
            auctionDiv.classList.add('auction-tab');
            auctionDiv.id = safeAuctionId;
            if (auction.auction_name === 'Singles') {
                auctionDiv.classList.add('singles');
            }
            auctionDiv.setAttribute('data-id', safeAuctionId);
            const auctionName = auction.auction_name || "Auction " + (auction.id - 1);
            const auctionPrice = auction.auction_price;
            const buyDate = new Date(auction.date_created);
            let formatedDate = buyDate.toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
            if (formatedDate === 'Invalid Date') {
                formatedDate = new Date(String(auction.date_created).split('T')[0]).toLocaleDateString('sk-SK', { year: 'numeric', month: '2-digit', day: '2-digit' });
            }

            const payments = parsePaymentMethods(auction.payment_method);
            const paymentDisplay = formatPaymentDisplay(payments);

            auctionDiv.innerHTML = `
                <p class="auction-name">${DOMPurify.sanitize(auctionName)}</p>
                <p class="auction-price" data-field="auction_price">${auctionPrice != null ? DOMPurify.sanitize(auctionPrice) + '€' : ''}</p>
                <p class="buy-date">${DOMPurify.sanitize(formatedDate)}</p>
                <div class="payment-method-container">
                    <div class="payment-method">${paymentDisplay}</div>
                </div>
                <button class="view-auction" data-id="${safeAuctionId}">View</button>
                <button class="buy-report" data-id="${safeAuctionId}">Buy report</button>
                <div class="cards-container">
                    <!-- Cards will be loaded here -->
                </div>
            `;
            auctionContainer.appendChild(auctionDiv);
        });


        const buyReportButtons = document.querySelectorAll('.auction-container .buy-report');
        buyReportButtons.forEach(button => {
            button.addEventListener('click', async () => {
                const auctionId = Number(button.getAttribute('data-id'));
                const response = await csrfFetch(`/generateBuyReport?auctionId=${auctionId}`);
                const contentType = response.headers.get('content-type') || '';

                if (!response.ok || contentType.includes('application/json')) {
                    const err = await response.json();
                    renderAlert(`Error generating buy report: ${err}`, 'error');
                    return;
                }
                try {
                    downloadFile(response)
                } catch (e) {
                    renderAlert('Error: ' + e, 'error');
                }

            });
        });

        const viewButtons = document.querySelectorAll('.auction-container .view-auction');
        viewButtons.forEach(button => {
            button.addEventListener('click', () => loadAuctionContent(button));
        });

        const auctionsTabs = document.querySelectorAll('.auction-container .auction-tab');
        auctionsTabs.forEach(tab => {
            tab.addEventListener('click', async (event) => {
                if (event.target === tab) {
                    const viewButton = tab.querySelector('.view-auction');
                    if (viewButton) {
                        loadAuctionContent(viewButton);
                    }
                }
            });
        });
    } catch (error) {
        renderAlert('Error loading auctions: ' + error, 'error');
    }
}

async function initializeSealed() {
    const sealedContainer = document.querySelector('.sealed-container');
    const viewButton = sealedContainer.querySelector('.view-sealed');
    viewButton.addEventListener('click', () => {
        loadSealed(viewButton);
    });
}

async function loadSealed(viewButton) {
    const sealedTab = document.querySelector('.sealed-tab');
    const contentDiv = document.querySelector('.sealed-tab-content');
    if (sealedTab.hidden || sealedTab.childElementCount === 0) {
        sealedTab.hidden = false;
        viewButton.innerHTML = 'Hide';

        if (contentDiv.childElementCount === 0) {
            try {
                const response = await csrfFetch('/loadSealed');
                const data = await response.json();
                if (data.status != 'success') {
                    renderAlert('Failed to load sealed products', 'error');
                    return;
                }

                data.data.forEach((sealedData) => {
                    const sealedDiv = document.createElement('div');
                    sealedDiv.classList.add('sealed-item');
                    const margin = (Number(DOMPurify.sanitize(sealedData.market_value)) - Number(DOMPurify.sanitize(sealedData.price))).toFixed(2);
                    const formatedDate = formatSealedDate(sealedData.date);
                    let state = '';
                    console.log(sealedData);
                    if (sealedData.opened) {
                        state = 'Opened';
                    } else if (sealedData.sale_id != null) {
                        state = 'Sold';
                    }
                    sealedDiv.innerHTML = `
                        <p class='sealed-quantity'>${DOMPurify.sanitize(sealedData.quantity)}</p>
                        <p class='sealed-name'>${DOMPurify.sanitize(sealedData.name)}</p>
                        <p class='unit-price'>${DOMPurify.sanitize(sealedData.price)}</p>
                        <p class='VAT-sealed sealed-market-value'>${(DOMPurify.sanitize(sealedData.price) / 1.23).toFixed(2)}</p>
                        <p class='market-value-sealed'>${DOMPurify.sanitize(sealedData.market_value)}</p>
                        <p class='margin'>${margin}</p>
                        <p class='add-date'>${formatedDate}</p>
                        <p>${state}</p>
                        <p></p>
                        <p></p>
                    `;
                    contentDiv.append(sealedDiv);
                });
            } catch (e) {
                renderAlert('Error loading sealed: ' + e, 'error');
            }
        }
    } else {
        sealedTab.hidden = true;
        viewButton.innerHTML = 'View';
    }
}

loadAuctions();
initializeSealed();
scrollOnLoad();
