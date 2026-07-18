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
    const res = await csrfFetch(`/partyInfo/${saleId}`);
    const partyInfo = await res.json();
    console.log(partyInfo);

    const saleInfo = partyInfo.sale;
    const originalInvoiceNum = saleInfo.invoice_number;
    const providerInfo = partyInfo.providerInfo;
    const recieverInfo = partyInfo.recieverInfo;
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
            div.setAttribute('data-id', item.id);
            div.innerHTML = `
                <input type="checkbox" class="item-checkbox" checked>
                <div class="item-info">
                    <p class="item-name">${item.card_name}</p>
                    <p class="item-number">${item.card_num}</p>
                </div>
                <p class="item-condition ${condClass}">${item.condition}</p>
                <p class="market-value">${item.sell_price * -1}<span class="currency">€</span></p>
            `;
            itemsContainer.appendChild(div);
        } else {
            for (let i = 0; i < item.quantity; i++) {
                const div = document.createElement('div');
                div.classList.add('sealed-item', 'creditnote-item-row');
                div.setAttribute('data-id', item.id);
                div.innerHTML = `
                    <input type="checkbox" class="item-checkbox" checked>
                    <p class="item-quantity">1</p>
                    <p class="item-name">${item.name}</p>
                    <p class="market-value">${item.market_value * -1}<span class="currency">€</span></p>
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
        <p class="shipping-price">${shipping * -1}<span class="currency">€</span></p>
        `;
    itemsContainer.appendChild(shippingDiv);



    const totalPriceDiv = document.querySelector('.total-price');
    totalPriceDiv.innerHTML = `<p class="total-amount">${saleInfo.total_amount * -1}</p><span class="total-price-currency">€</span>`;

    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(checkbox => {
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

    const confirmBtn = document.querySelector('.confirm-btn');
    confirmBtn.addEventListener('click', async (event) => {
        const returnNote = {
            items: [],
            shipping: false
        }
        const payload = {};
        itemsContainer.querySelectorAll('.creditnote-item-row').forEach(item => {
            if (item?.querySelector('.item-checkbox').checked) {
                const id = item.getAttribute('data-id');
                returnNote.items.push(id);
            }
        });
        if (shippingCheckbox.checked) {
            payload.shipping = {
                shippingWay: 'Doprava / Poštovné – samostatná služba',
                shippingPrice: shipping,
            }
        };

        const itemsToReturn = items.filter((item) => returnNote.items.includes(String(item.id)));
        payload.items = itemsToReturn.filter((item) => item.card_num);
        const sealedReturnCounts = {};
        itemsContainer.querySelectorAll('.sealed-item .item-checkbox:checked').forEach(cb => {
            const id = cb.closest('.creditnote-item-row').getAttribute('data-id');
            sealedReturnCounts[id] = (sealedReturnCounts[id] || 0) + 1;
        });
        payload.sealed = itemsToReturn
            .filter((item) => !item.card_num)
            .map((s) => ({ ...s, returnQuantity: sealedReturnCounts[s.id] || 0 }))
            .filter((s) => s.returnQuantity > 0);
        //bulk, holo, ex 
        payload.reciever = recieverInfo;
        payload.originalInvoiceNum = originalInvoiceNum;
        payload.valueChanged = itemsToReturn.reduce((acc, curr) => acc + Number(curr.sell_price), 0);
        const body = JSON.stringify(payload);

        const response = await csrfFetch(`/generateCreditNote/${saleId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: body,
        });
        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            renderAlert('Error: ' + (await response.json()).message, 'error');
            return;
        };
        await downloadFile(response);
        window.location.href = `/sold`;

    });

}

loadContent();
