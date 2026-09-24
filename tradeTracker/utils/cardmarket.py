import logging

logger = logging.getLogger(__name__)


def resolve_cardmarket_id(db, item, name_key, card_num_key):
    """Use an imported ID when present, otherwise resolve one external match."""
    supplied_id = item.get("cardmarketId")
    if supplied_id is not None and str(supplied_id).strip():
        return str(supplied_id).strip()

    name = item.get(name_key)
    card_num = item.get(card_num_key) or ""
    if not name:
        logger.warning("Unable to resolve CardMarket ID: item has no name")
        return None

    matches = db.execute(
        "SELECT cardmarketId FROM external "
        "WHERE lower(trim(card_name)) = lower(trim(?)) "
        "AND lower(trim(COALESCE(card_num, ''))) = lower(trim(?))",
        (name, card_num),
    ).fetchall()
    if len(matches) == 1:
        return matches[0]["cardmarketId"]

    reason = "no match" if not matches else "multiple matches"
    logger.warning(
        "Unable to resolve CardMarket ID: %s | name: %s | card_num: %s",
        reason,
        name,
        card_num,
    )
    return None


# TODO: change this to default
def resolve_cardmarket_id_model(db, item, name_key, card_num_key):
    """Use an imported ID when present, otherwise resolve one external match."""
    supplied_id = item.cardmarketId
    if supplied_id is not None and str(supplied_id).strip():
        return str(supplied_id).strip()

    name = item.name
    card_num = item.number
    if not name:
        logger.warning("Unable to resolve CardMarket ID: item has no name")
        return None

    matches = db.execute(
        "SELECT cardmarketId FROM external "
        "WHERE lower(trim(card_name)) = lower(trim(?)) "
        "AND lower(trim(COALESCE(card_num, ''))) = lower(trim(?))",
        (name, card_num),
    ).fetchall()
    if len(matches) == 1:
        return matches[0]["cardmarketId"]

    reason = "no match" if not matches else "multiple matches"
    logger.warning(
        "Unable to resolve CardMarket ID: %s | name: %s | card_num: %s",
        reason,
        name,
        card_num,
    )
    return None
