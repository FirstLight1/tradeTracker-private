import {renderField, replaceWithPElement, renderAlert} from './main.js';

function appendEuroSign(value, dataset){
    if (dataset === 'card_num' || dataset === 'card_name'){
        return value;
    }
    if (isNaN(value)){
        return value;
    } else{
        return value + '€';
    }
}

async function removeCard(id, div){
    try{
        const response = await fetch(`/deleteFromCollection/${id}`, {
            method: 'DELETE',
        })
        const data = await response.json();
        if(data.status === "success"){
            div.remove();
            return true;
        }else{
            renderAlert('Failed to remove card: ' + JSON.stringify(data), 'error');
            return false;
        }
    }catch(err){
        renderAlert('Error removing card: ' + err, 'error');
        return false;
    }
}

async function patchValue(id, value, dataset){
    value = String(value);
    value = value.replace('€', '');
    return fetch(`/updateCollection/${id}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ field: dataset, value: value })
    });
}

async function getInputValueAndPatch(value, element, dataset, cardId){
    if (!Boolean(value)){
            return null;
        }
        replaceWithPElement(dataset, value, element);
        await patchValue(cardId, value, dataset);
}

async function getCollectionValue(){
    try{
        const response = await fetch('/collectionValue');
        const data = await response.json();
        return data.value;
    } catch(e){
        renderAlert('Error loading collection value: ' + e, 'error');
    }
}


export async function updateCollectionValue() {
        const value = await getCollectionValue();
        const inventoryValueElement = document.querySelector('.inventory-value-value');
        if(value != null){
            inventoryValueElement.textContent = appendEuroSign(value.toFixed(2));
        } else{
            inventoryValueElement.textContent = '0.00€';
        }
    
}

async function fetchCollection(){
    const collectionContainer = document.querySelector('.collection');
    
    try{
        const response = await fetch('/loadCollection');
        const data = await response.json();
    
        data.forEach(card => {
            const cardDiv = document.createElement('div');
            cardDiv.classList.add('card');
            cardDiv.innerHTML = `
            ${renderField(card.card_name, 'text', ['card-info', 'card-name'], 'Card name', 'card_name')}
            ${renderField(card.card_num, 'text', ['card-info', 'card-num'], 'Card number', 'card_num')}
            <p class='card-info condition' data-field="condition">${card.condition ? card.condition : 'Unknown'}</p>
            ${renderField(card.buy_price ? card.buy_price + '€' : null,'text', ['card-info', 'buy-price'], 'Buy price', 'buy_price')}
            ${renderField(card.market_value ? card.market_value + '€' : null,'text', ['card-info', 'market-value'], 'Market value', 'market_value')}
            <span hidden class="card-id">${card.id}</span>
            <button class="delete-btn" data-id="${card.id}">Delete</button>
            `;
            collectionContainer.appendChild(cardDiv);
        });

        const deleteButton = document.querySelectorAll('.delete-btn');
        deleteButton.forEach(button => {
            button.addEventListener('click',async () => {
                const cardId = button.getAttribute('data-id');
                const cardDiv = button.closest('.card');
                await removeCard(cardId, cardDiv);
                await updateCollectionValue();
                if (collectionContainer.childElementCount === 0){
                    const inventoryValueElement = document.querySelector('.inventory-value-value');
                    inventoryValueElement.textContent = '0€';
                }
            });
        });

        collectionContainer.addEventListener('dblclick', (event) => {
            if(event.target.closest('.card') && event.target.tagName !== "DIV"){
                const cardDiv = event.target.closest('.card');
                const cardId = cardDiv.querySelector('.card-id').textContent;
                if (event.target.classList.contains('condition')) {
                    const value = event.target.textContent;
                    const select = document.createElement('select');
                    const options = ['Mint', 'Near Mint', 'Excellent', 'Good', 'Light Played', 'Played', 'Poor'];
                    const dataset = event.target.dataset.field;
                    options.forEach(option => {
                        const opt = document.createElement('option');
                        opt.value = option;
                        opt.textContent = option;
                        if (option === value) {
                            opt.selected = true;
                        }
                        select.appendChild(opt);
                    });
                    event.target.replaceWith(select);
                    select.addEventListener('change', (event) => {
                        const selectedValue = event.target.value;
                        const p = document.createElement('p');
                        p.classList.add('card-info', 'condition');
                        p.textContent = selectedValue || value;
                        select.replaceWith(p);
                        patchValue(cardId, p.textContent, dataset);
                    });
                }
                if (event.target.tagName === "P") {
                    let value = event.target.textContent.replace('€','');
                    if(isNaN(value)){
                        value = value.toUpperCase();
                    }
                    const dataset = event.target.dataset.field;
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = value;
                    input.classList.add(...event.target.classList);
                    event.target.replaceWith(input);
                    input.focus();
                    input.addEventListener('blur', async (blurEvent) => {
                        let newValue = blurEvent.target.value;
                        if(isNaN(newValue)){
                            newValue = newValue.toUpperCase();
                        }
                        await getInputValueAndPatch(newValue || value, input, dataset, cardId);
                        if(blurEvent.target.classList.contains('market-value')){
                            await updateCollectionValue();
                        }
                    });
                    input.addEventListener('keydown', (event) => {
                        if (event.key === 'Enter') {
                            input.blur();
                        }
                    });
                }
            }
        });

        const inputFields = collectionContainer.querySelectorAll('input[type="text"]');
        inputFields.forEach((input) => {
            input.addEventListener('blur', async (event) =>{
                const cardId = event.target.closest('.card').querySelector('.card-id').textContent;
                const value = event.target.value;
                const dataset = event.target.dataset;
                await getInputValueAndPatch(value, input, dataset.field, cardId);
                if(event.target.classList.contains('market-value')){
                    await updateCollectionValue();
                }
            })
            input.addEventListener('keydown', (event) => {
                if(event.key === 'Enter'){
                    input.blur();
                }
            });
        });


    } catch(err){
        renderAlert('Error loading collection: ' + err, 'error');
    }

}

if (document.title === "Collection"){
    fetchCollection()
    updateCollectionValue(); 

}
