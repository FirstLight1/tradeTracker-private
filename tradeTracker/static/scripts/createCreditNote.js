import { renderField, renderAlert, scrollOnLoad, downloadFile } from "./utils/renderUtil.js";
import { sanitizeNumericId, sanitizeClassToken, csrfFetch } from "./utils/sanitizers.js";


async function loadContent() {
    const params = new Proxy(new URLSearchParams(window.location.search), {
        get: (searchParams, prop) => searchParams.get(prop),
    });

    const saleId = sanitizeNumericId(params.saleId);

    const recieverDiv = document.querySelector('creditnote-reciever-content');
    const itemsContainer = document.querySelector('creditnote-item-content');

    const response = await csrfFetch(`/loadSale/${saleId}`);
    const sale = await response.json();
    if (sale.status !== 'success') {
        renderAlert('Failed to load sale: ' + sale.message, 'error');
        return;
        //spawn try agian later type shit
    };
    saleInfo = sale.data.sale
    recieverInfo = saleInfo.reciever;
    items = sale.data.items;
    shipping = sale.data.shipping;

    recieverDiv.innerHTML = `
        <p>${recieverInfo.nameAndSurname}</p>
        <p>${recieverInfo.address}</p>
        <p>${recieverInfo.city}</p>
        <p>${recieverInfo.state}</p>
        `;

    items.forEach(item => {
        const div = document.createElement('div');
        if (item.card_num) {
            div.classList.add('card');
            div.innerHTML = `
                <input type="checkbox" class="card-checkbox" checked>
                <p>${item.card_name}</p>
                <p>${item.card_num}</p>
                <p>${item.condition}</p>
                <p>${item.market_value}</p>
                `;
        } else {
            for (let i = 0; i < item.quantity; i++) {
                div.classList.add('sealed-item');
                div.innerHTML = `
                <input type="checkbox" class="sealed-checkbox" checked>
                <p>1</p>
                <p>${item.name}</p>
                <p>${item.market_value}</p>
            `;
            }
        };
        itemsContainer.appendChild(div);
    });

    const shippingDiv = document.createElement('div');
    shippingDiv.classList.add('shipping-info');
    shippingDiv.innerHTML = `
        <p>Doprava / Poštovné – samostatná služba </p>
        <p>${shipping.shippingPrice}</p>
        `;
    itemsContainer.appendChild(shippingDiv);

    const totalPriceDiv = document.querySelector('.total-price');
    totalPriceDiv.innerHTML = `<p class="total-amount">${saleInfo.total_amount}</p> <span class="total-price-currency">€</span>`;


    cardCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', async (event) => {
            const checked = event.target.checked;
            const marketValue = event.target.closest('.card').querySelector('.market-value').textContent;
            const totalValue = document.querySelector('.total-amount').textContent;
            if (checked) {
                totalValue += marketValue;
            } else {
                totalValue -= marketValue;
            }
        });
    });

    sealedCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', async (event) => {
            const checked = event.target.checked;
            const marketValue = event.target.closest('.sealed-item').querySelector('.market-value').textContent;
            const totalValue = document.querySelector('.total-amount').textContent;
            if (checked) {
                totalValue += marketValue;
            } else {
                totalValue -= marketValue;
            };
        });
    });
}

loadContent();
