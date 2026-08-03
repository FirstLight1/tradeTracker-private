import { csrfFetch } from "./sanitizers.js";
import { renderAlert } from "./renderUtil.js";

export async function searchCard(query, cartIds = [], individualCards = false) {
    const response = await csrfFetch('/searchCard', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: query.toUpperCase(), cartIds, individualCards }),
    });
    const data = await response.json();
    if (data.status === 'success') return data.value;
    renderAlert('Search failed', 'error');
    return null;
}
