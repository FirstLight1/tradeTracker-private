import { getInventoryValue } from "./renderUtil.js";

export async function updateInventoryValueAndTotalProfit() {
    const value = await getInventoryValue();
    const inventoryValueElement = document.querySelector('.inventory-value-value');
    if (value != null) {
        inventoryValueElement.textContent = appendEuroSign(value.toFixed(2));
    } else {
        inventoryValueElement.textContent = '0.00 €';
    }
}