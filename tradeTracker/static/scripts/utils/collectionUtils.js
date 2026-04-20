import { renderAlert } from "./renderUtil.js";
import { csrfFetch } from "./sanitizers.js";

export async function getCollectionValue(){
    try{
        const response = await csrfFetch('/collectionValue', {
            method: 'GET',
        });
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
