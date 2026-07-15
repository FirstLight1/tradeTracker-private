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

    //TODO: find better name for this endpoint 
    const response = await csrfFetch(`/partyInfo/${saleId}`);
    const data = await response.json();
    const saleInfo = data.sale;
    const originalInvoiceNum = saleInfo.invoice_number;
    const providerInfo = data.providerInfo;
    const recieverInfo = data.recieverInfo;

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



}

loadContent();
