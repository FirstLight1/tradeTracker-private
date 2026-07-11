import { renderField, renderAlert, scrollOnLoad, downloadFile } from "./utils/renderUtil.js";
import { sanitizeNumericId, sanitizeClassToken, csrfFetch } from "./utils/sanitizers.js";

function conditionClass(condition) {
    if (!condition) return '';
    const norm = condition.toLowerCase().replace(/[\s_-]+/g, '');
    const map = {
        mint: 'mint',
        mt: 'mint',
        nearmint: 'near_mint',
        nm: 'near_mint',
        excellent: 'excellent',
        ex: 'excellent',
        good: 'good',
        gd: 'good',
        lightplayed: 'light_played',
        lp: 'light_played',
        played: 'played',
        pl: 'played',
        poor: 'poor',
        po: 'poor',
    };
    return map[norm] || '';
}

function renderAddressBlock(container, data) {
    container.innerHTML = `
        <div class="creditnote-address-block">
            <p class="address-name">${data.name || data.summary || ''}</p>
            <p class="address-line">${data.address || ''}</p>
            <p class="address-line"><span class="address-zip">${data.zip_code || ''}</span> <span class="address-city">${data.city || ''}</span></p>
            <p class="address-line">${data.state || data.country || ''}</p>
            ${data.phone ? `<p class="address-line address-contact">${data.phone}</p>` : ''}
            ${data.email ? `<p class="address-line address-contact">${data.email}</p>` : ''}
            ${data.ico ? `<p class="address-line address-id"><span>IČO:</span> ${data.ico}</p>` : ''}
            ${data.dic ? `<p class="address-line address-id"><span>DIČ:</span> ${data.dic}</p>` : ''}
            ${data.ic_dph ? `<p class="address-line address-id"><span>IČ DPH:</span> ${data.ic_dph}</p>` : ''}
        </div>
    `;
}

async function loadContent() {
    const params = new Proxy(new URLSearchParams(window.location.search), {
        get: (searchParams, prop) => searchParams.get(prop),
    });

    const saleId = sanitizeNumericId(params.saleId);

    const providerDiv = document.querySelector('.creditnote-box-content');
    const recieverDiv = document.querySelector('.creditnote-reciver-content');
    const itemsContainer = document.querySelector('.creditnote-item-content');

    const response = await csrfFetch(`/loadSale/${saleId}`);
    const sale = await response.json();
    if (sale.status !== 'success') {
        renderAlert('Failed to load sale: ' + sale.message, 'error');
        return;
        //spawn try agian later type shit
    };
    const saleInfo = sale.data.sale
    console.log(saleInfo);
    const providerInfo = sale.data.provider;
    const recieverInfo = sale.data.reciever;
    const items = sale.data.items;
    const shipping = saleInfo.shipping_info;

    renderAddressBlock(providerDiv, {
        ...providerInfo,
        name: providerInfo.summary,
        state: providerInfo.country,
    });

    renderAddressBlock(recieverDiv, {
        ...recieverInfo,
        name: recieverInfo.nameAndSurname,
        country: recieverInfo.state,
    });

    items.forEach(item => {
        if (item.card_num) {
            const div = document.createElement('div');
            div.classList.add('card', 'creditnote-item-row');
            const condClass = conditionClass(item.condition);
            div.innerHTML = `
                <input type="checkbox" class="card-checkbox" checked>
                <div class="item-info">
                    <p class="item-name">${item.card_name}</p>
                    <p class="item-number">${item.card_num}</p>
                </div>
                <p class="item-condition ${condClass}">${item.condition}</p>
                <p class="market-value">${item.sell_price}<span class="currency">€</span></p>
            `;
            itemsContainer.appendChild(div);
        } else {
            for (let i = 0; i < item.quantity; i++) {
                const div = document.createElement('div');
                div.classList.add('sealed-item', 'creditnote-item-row');
                div.innerHTML = `
                    <input type="checkbox" class="sealed-checkbox" checked>
                    <p class="item-quantity">1</p>
                    <p class="item-name">${item.name}</p>
                    <p class="market-value">${item.market_value}<span class="currency">€</span></p>
                `;
                itemsContainer.appendChild(div);
            }
        }
    });

    const shippingDiv = document.createElement('div');
    shippingDiv.classList.add('shipping-info');
    shippingDiv.innerHTML = `
        <input type="checkbox" class="shipping-checkbox" checked>
        <p>Doprava / Poštovné – samostatná služba </p>
        <p class="shipping-price">${shipping}<span class="currency">€</span></p>
        `;
    itemsContainer.appendChild(shippingDiv);



    const totalPriceDiv = document.querySelector('.total-price');
    totalPriceDiv.innerHTML = `<p class="total-amount">${saleInfo.total_amount}</p><span class="total-price-currency">€</span>`;

    const cardCheckboxes = document.querySelectorAll('.card-checkbox');
    cardCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (event) => {
            const checked = event.target.checked;
            const marketValue = parseFloat(event.target.closest('.creditnote-item-row').querySelector('.market-value').textContent) || 0;
            const totalAmountEl = document.querySelector('.total-amount');
            let totalValue = parseFloat(totalAmountEl.textContent) || 0;
            if (checked) {
                totalValue += marketValue;
            } else {
                totalValue -= marketValue;
            }
            totalAmountEl.textContent = totalValue.toFixed(2);
        });
    });

    const sealedCheckboxes = document.querySelectorAll('.sealed-checkbox');
    sealedCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (event) => {
            const checked = event.target.checked;
            const marketValue = parseFloat(event.target.closest('.creditnote-item-row').querySelector('.market-value').textContent) || 0;
            const totalAmountEl = document.querySelector('.total-amount');
            let totalValue = parseFloat(totalAmountEl.textContent) || 0;
            if (checked) {
                totalValue += marketValue;
            } else {
                totalValue -= marketValue;
            }
            totalAmountEl.textContent = totalValue.toFixed(2);
        });
    });

    const shippingCheckbox = document.querySelector('.shipping-checkbox');
    shippingCheckbox.addEventListener('change', (event) => {
        const checked = event.target.checked;
        const shippingPrice = parseFloat(shippingDiv.querySelector('.shipping-price').textContent) || 0;
        const totalAmountEl = document.querySelector('.total-amount');
        let totalValue = parseFloat(totalAmountEl.textContent) || 0;
        if (checked) {
            totalValue += shippingPrice;
        } else {
            totalValue -= shippingPrice;
        }
        totalAmountEl.textContent = totalValue.toFixed(2);
    });
}

loadContent();
