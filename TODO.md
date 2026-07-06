# TODO — Trade Tracker backlog

Features/bugfixes with concrete, codebase-grounded implementation suggestions.
Ordered by priority (item 1 = highest).

## Context

Data-model facts these suggestions rely on (verified against the code):
- `cards` — individual items; in-stock = `sold_date IS NULL`. Belongs to an `auctions` row (purchase batch).
- `bulk_items` — quantity-tracked; `sealed` — sealed products.
- A sale writes `sales` + `sale_items` and sets `cards.sold_date` (`services/sale_service.py:90`).
- Removal today is **hard delete only** (`/deleteCard`, `/deleteSealed`, `/deleteBulkItem` in `actions.py`).
- `/addToExistingAuction/<auction_id>` (`actions.py:507`) already appends **cards + sealed** to an existing auction.
- Migrations are idempotent functions in `tradeTracker/migration.py`, registered in `migrate_database()`.
- Mutations live in the `actions` blueprint; CSP forbids inline JS/CSS (put assets in `static/`).

---

## 1. Open / unbox a sealed product → add contents to the same auction tab ⭐ (top priority) => DONE

**What.** Add an **"Open"** button to a sealed item. Opening lets the user enter what came out of it —
**cards and/or other sealed items** — and those contents are inserted into the **same auction tab the
opened sealed item belongs to**. The opened box is marked **opened** (consumed): it stays for records
but drops out of sellable inventory so it isn't double-counted against its contents.

**Good news — most plumbing already exists:**
- `/addToExistingAuction/<auction_id>` (`actions.py:507`–`556`) already inserts **both cards and
  sealed** into a given auction → the unbox submit reuses it directly.
- The in-tab "add cards" / "add sealed" forms (`main.js` `~:2216` / `~:2256`) are the contents-entry UI to reuse.
- A sealed row already resolves its auction via `closest('.auction-tab').data-id` (`main.js:2872`).
- The only genuinely new piece is an **"opened" state** for sealed (none exists today).

**Where.**
- `tradeTracker/migration.py` — add `sealed.opened` flag (idempotent).
- `tradeTracker/actions.py` — mark-opened endpoint (or extend `/addToExistingAuction`); exclude opened
  sealed from `/loadSealed` sellable lists (`:421`–`430`) and `/inventoryValue` (`:439`).
- `tradeTracker/static/scripts/main.js` — "Open" button on the sealed row (`~:2066`–`2090`); open-contents
  modal reusing the add-cards/add-sealed forms; submit to `/addToExistingAuction/<that auction id>`.
- `tradeTracker/templates/index.html` — sealed row markup.

**How.**
1. **Opened flag** — `sealed.opened INTEGER NOT NULL DEFAULT 0` via idempotent migration.
2. **Open UI** — "Open" button on each sealed row → modal with the reusable card-rows + sealed-rows
   inputs (card_name, card_num, condition, market_value; sealed name + market_value). Read the box's
   `auction_id` from the parent `.auction-tab` `data-id`.
3. **Submit** — POST the entered contents to `/addToExistingAuction/<auction_id>` (already handles
   cards + sealed). Then mark the box opened.
4. **Cost basis (suggested default).** The box's cost is already in the tab's `auction_price`, so insert
   the pulled contents with **buy price 0** (cost stays sunk in the box; only market_value matters), to
   avoid double-counting. *(Alternative: distribute box cost across contents — TBD.)* Note:
   `/addToExistingAuction` defaults a null card buy price to `marketValue*0.85`, so send an explicit `0`.
5. **Exclude opened box** — opened sealed must drop out of sellable lists + inventory value (same
   exclude pass as item 2) so the box and its contents aren't both counted.

**Notes / risks.**
- Pool sealed (auction_id NULL) has no tab → either disable Open there, or send contents to the pool too.
- Ties to item 2 ("opened box stays for records but not inventory" = the same exclude logic) and
  item 3 (if `quantity` exists, open one unit at a time: decrement qty, mark one opened).
- Keep the box row for the audit trail (matches the unboxing guidance: don't delete, record stays).

---

## 2. Inventory write-off / disposal (non-sale removal) — "vyradené"

**What.** Let the user remove an item from active inventory **without recording a sale or income**,
for a non-sale reason: **giveaway** or **personal use** (collection). The item is *not deleted*
(the source guidance: *"z inventára nevymažeš nič"*) — it stays in the records tagged as written off,
with a reason, date, and (for giveaways) recipient. Covers **individual cards + sealed products**
(bulk excluded for now). VAT/margin is **not** tracked in the app — disposal note only; VAT impact
is left to the accountant (zero for margin-scheme goods anyway).

**Resulting item states.** in stock (`sold_date` NULL, no disposal) · sold (`sold_date` set) ·
written off (`disposal_reason` set).

**Where.**
- `tradeTracker/migration.py` — add idempotent migrations.
- `tradeTracker/actions.py` — new write-off + undo routes (near delete routes ~`:452`; mirror `/deleteCard` and `/orderReturn` `:651`).
- `tradeTracker/db.py` — schema reference for `cards` (`:156`) and `sealed` (`:234`).
- Renderers/templates + a `static/` JS file for the write-off modal.

**How.**
1. **Migration** — add `_add_disposal_fields_to_cards(cursor)` and `_add_disposal_fields_to_sealed(...)`,
   following the `PRAGMA table_info` idempotent pattern (`migration.py:52` `_add_sold_date_to_cards`).
   New nullable columns on both `cards` and `sealed`:
   `disposal_reason TEXT` (`'giveaway' | 'personal' | 'other'`), `disposal_date TEXT`,
   `disposal_recipient TEXT` (giveaway only), `disposal_note TEXT`. Register both in `migrate_database()`.
2. **Write-off route** — `POST /writeOffCard/<card_id>` and `POST /writeOffSealed/<sid>` in `actions.py`.
   Set the disposal fields; do **not** touch `sold_date`; do **not** create `sales`/`sale_items`.
   Reuse the existing CSRF/auth/host-routing setup that the other `actions` routes use.
3. **Undo route** — `POST /undoWriteOff/<...>` clears the disposal fields (mirror `/orderReturn:651`).
4. **Inventory queries** — audit everywhere that treats `sold_date IS NULL` as "in stock" and also
   exclude `disposal_reason IS NOT NULL`, so written-off items drop out of stock counts, profit calc,
   and available-to-sell lists. *(Main risk: these filters are scattered across renderers/tracker —
   needs a grep pass during implementation.)*
5. **UI** — "Write off" button on a card/sealed row → small modal (reason dropdown, date picker,
   recipient field shown only for giveaway). JS in `static/` (no inline, per CSP). Show a "vyradené"
   badge and the note (`vyradené — giveaway, date, recipient`) on the item / in its purchase batch view.

**Notes / risks.**
- Biggest effort is step 4 (finding every in-stock filter) — not the write-off action itself.
- `bulk_items` deliberately out of scope (quantity model would need partial write-off; revisit later).
- Keep purchase cost intact — written-off items still cost what they cost; we just record no income.
- Overlaps item 7 (tab-based disposal); if item 7's tab approach is chosen, this may fold into it.

---

## 3. Quantity for sealed products => DONE

**What.** Sealed products are currently **one row = one unit** (`sealed` has no quantity field),
unlike `bulk_items`. Add a `quantity` so a sealed product can be stocked, displayed, and **sold
in partial amounts** (sell 2 of 5; the rest stay in stock) — mirroring how `bulk_items` already works.
Quantity is enterable both in the **manual "Add Sealed" form** and the **Chrome-extension import**.

**Where.**
- `tradeTracker/migration.py` — add quantity column (`addSealedProductsTable` is at `:237`).
- `tradeTracker/actions.py` — `/addSealed` (`:386`), `/loadSealed` + `/loadSealed/<auction_id>` (`:378`–`430`), `/deleteSealed` (`:468`).
- `tradeTracker/services/sale_service.py` — sealed sale logic (`:105`–`111`); compare bulk FIFO (`:170`–`200`).
- `tradeTracker/services/models.py` — sealed dataclass/model (`:13`) if it enumerates fields.
- `tradeTracker/templates/index.html` — sealed table header (`:108`–`133`).
- `tradeTracker/static/scripts/main.js` — sealed render (`~:2454`) and cart (`addSealedToCart` `~:1327`).
- Chrome-extension import payload (sends to `/addSealed`).

**How.**
1. **Migration** — `addQuantityToSealed(db_path)`: idempotent `PRAGMA table_info(sealed)` check, then
   `ALTER TABLE sealed ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1` (DEFAULT required by SQLite for a
   NOT NULL add; existing rows become qty 1). Register in `migrate_database()`.
2. **Add** — `/addSealed` reads optional `quantity` per item (default 1) and stores it on the row.
   Do **not** upsert/merge like bulk does — sealed `name` is free-form with no stable natural key, so keep
   one row per add, carrying its quantity. Add a qty field to the manual form and to the extension payload.
3. **Display** — include `quantity` in both `loadSealed` SELECTs; in-stock filter becomes
   `sale_id IS NULL AND quantity > 0`. Add a "Qty" column in `index.html` + render it in `main.js`.
4. **Sell (partial, split-row)** — replace the whole-row `UPDATE sealed SET sale_id` (`sale_service.py:105`)
   with quantity-aware logic per sealed line (sid + qty `q`, stock row qty `Q`):
   - `q >= Q`: set `sale_id` on the row (consumes it).
   - `q <  Q`: `quantity = Q - q` on the stock row, **insert a new sealed row** copying
     name/price/market_value/auction_id with `quantity = q` and `sale_id` set.
   This preserves the existing "each sale owns its sealed rows via `sale_id`" model that invoices and
   `orderReturn` already rely on.
5. **Cart** — give sealed a quantity picker in `main.js` (mirror bulk); the current `addSealedToCart`
   de-dups by `sid` and treats each as one unit — switch to a qty field and send qty in the sale payload.
6. **Return** — `orderReturn` restores sealed by clearing `sale_id`; a split sold row simply becomes a
   stock row again (may leave fragmented rows — acceptable; optional later: merge same-name stock rows).

**Notes / risks.**
- Main complexity is the partial-sale split + adding a qty picker to the sealed cart (steps 4–5).
- `/deleteSealed` stays whole-row delete; optionally let it decrement qty later.
- Verify the extension manifest/import code is updated to send `quantity`, or it silently defaults to 1.

---

## 4. Slovenská pošta (Slovak Post) API integration

> Items 4 and 5 share one foundation (recipient fields, carrier service layer, tracking/label
> storage, fulfillment UI). It's described once here; item 5 reuses it.

### Shared shipping foundation (prerequisite for 4 & 5)

**What.** Today a sale stores only buyer name/street/city/country (AES-GCM encrypted in
`sales.notes`), a plain `shipping_info` price, and a hardcoded shipping method — **no phone, email,
postal code, tracking number, or fulfillment step**. Carriers need all of these. Build the shared
plumbing first.

**Where.**
- `tradeTracker/services/` — new `carriers/` package (mirror the `ReceiptService` abstract-class
  pattern in `reciept_service.py:11`); HTTP via `requests` (already a dep) with timeouts/error
  handling like `cfAuth.py:22`.
- `tradeTracker/migration.py` — add carrier/tracking columns to `sales`.
- `tradeTracker/services/sale_service.py:52` — receiver JSON (add phone/email/zip).
- `tradeTracker/actions.py` — decrypt sites (`:589`, `:693`) + new fulfillment route; serve label
  PDF via `send_file(BytesIO(...))` like the invoice route (`:1654`).
- `tradeTracker/templates/index.html` (sale modal) + `static/scripts/main.js` (`collectModalData` `~:875`).
- `static/scripts/sold.js` — add "Ship" button + tracking display in the sold-history detail.
- `.env` + README env table — new API credentials.

**How.**
1. **Recipient fields** — add `phone`, `email`, `psc` (postal code) to the receiver object collected
   in the sale modal; they flow into the existing encrypted `notes` JSON (no migration — it's a blob).
   Ship step decrypts `notes` to build the parcel.
2. **Migration** — `addShippingFulfillmentColumns(sales)`: idempotent `PRAGMA table_info`, add
   `carrier TEXT`, `tracking_number TEXT`, `label_path TEXT` (or label BLOB), `shipment_id TEXT`,
   `cod_amount REAL`, `pickup_point_id TEXT`. Register in `migrate_database()`.
3. **Carrier layer** — abstract `CarrierClient` with `create_shipment(sale, parcel) ->
   {tracking_number, shipment_id, label_pdf: bytes}`. Concrete clients per carrier.
4. **Fulfillment route** — `POST /createShipment/<sale_id>/<carrier>` in the **`actions`** blueprint
   (user-initiated → app host). Decrypt receiver, build parcel (weight, declared value, COD if any),
   call the client, persist tracking/shipment/label, return the label PDF as a download.
5. **Parcel inputs** — add **weight** (and optional declared value) at ship time; **COD amount**
   defaults to the sale total when COD is chosen.
6. **UI** — in sold-history detail: carrier select, COD toggle, weight input, "Create label" button;
   show stored tracking number + a "Download label" link afterward.

### Slovenská pošta specifics

**What.** Register a parcel with Slovak Post and get a tracking number (podacie číslo) + label PDF,
with COD (dobierka) and home delivery (plus BalíkoBOX if desired later).

**How.**
- Implement `SlovenskaPostaClient(CarrierClient)` calling the Slovak Post business API
  (ePH / "Tlač a podaj" online submission). Map receiver fields → SP shipment payload; request the
  label PDF and parse the returned tracking number.
- Credentials in `.env`: e.g. `POSTA_API_USER` / `POSTA_API_KEY` (+ contract/customer number).

**Notes / risks.**
- Requires a **business contract + API credentials** from Slovenská pošta; full testing needs their
  sandbox/creds — code defensively and gate behind config presence.
- Exact endpoint/payload must be confirmed against current SP API docs at implementation time.

---

## 5. Packeta (Zásilkovna) API integration

**What.** Build on the shared foundation (item 4): register a Packeta parcel for **both pickup-point
(Z-Box / výdajné miesto) and home (na adresu) delivery**, with COD, returning a tracking number +
label PDF.

**Where.** `tradeTracker/services/carriers/packeta.py` (new) + the shared route/UI/migration from item 4.

**How.**
- Implement `PacketaClient(CarrierClient)` calling the Packeta API `createPacket` (auth via API
  password / sender label in `.env`: `PACKETA_API_PASSWORD`, `PACKETA_SENDER`). Map receiver fields →
  `packetAttributes`; set `cod` for COD; then fetch the label via `packetLabelPdf` and the tracking
  barcode/number.
- **Delivery mode selector** at ship time: pickup vs home.
  - **Pickup**: needs a destination point id. Since the JS widget wasn't chosen (and `script-src
    'self'` CSP would block it anyway), populate a **server-fetched dropdown** from Packeta's
    `pickup-points` list (cached), or accept a manually entered point id; store as `pickup_point_id`.
  - **Home**: use the Packeta home-delivery carrier id + the full decrypted address.

**Notes / risks.**
- Requires a **Packeta account + API password**; Packeta provides a **test API** — wire a
  sandbox/base-URL config flag for testing.
- Pickup-point list can be large — fetch server-side and cache; don't ship it inline.
- Keep credentials out of the repo (`.env`; in prod they come from the environment, not `.env`).

---

## 6. Merge two (or more) auction tabs into one

**What.** Combine multiple auction tabs (purchase batches) into a single one — for a buyout that came
in as separate tabs but is really one purchase (e.g. Riftbound + Pokémon výkup). Select 2+ tabs via
checkboxes → "Merge selected"; all items move into one kept tab whose buy price is **summed** and
payment methods **combined**, and you **choose which name** the merged tab keeps. No existing
merge/move logic today — this is a new transactional endpoint.

**Where.**
- `tradeTracker/actions.py` — new `/mergeAuctions` route; reuse the bulk upsert from
  `_add_bulk_items_helper` (`:268`–`327`) and the payment sanitize from `/updatePaymentMethod` (`:1229`).
- `tradeTracker/static/scripts/main.js` — auction-tab rendering (`~:2619`), `loadAuctions()` redraw,
  Singles special-casing (`~:2630`, `:2843`, `:2982`).
- `tradeTracker/templates/index.html` — auction tab header (`:107`–`137`) + container toolbar (`:135`).

**How.**
1. **Route** — `POST /mergeAuctions` in the **`actions`** blueprint. Body:
   `{ "ids": [.. ≥2 ..], "target_id": <kept>, "name": "<chosen>" }`. Wrap the whole thing in **one
   transaction** (rollback on any error — never half-merge).
2. **Reassign items** from each source → target:
   - `UPDATE cards SET auction_id = target WHERE auction_id = source`
   - `UPDATE sealed SET auction_id = target WHERE auction_id = source`
   - `UPDATE barter SET auction_id = target WHERE auction_id = source` (auction↔sale links)
   - **bulk_items** can't blind-UPDATE (UNIQUE(auction_id, item_type) collisions). For each source
     bulk row, run the existing **ON CONFLICT upsert** against the target (sums quantity + total,
     recomputes avg unit_price), then `DELETE FROM bulk_items WHERE auction_id = source`.
3. **Combine metadata** onto target: `auction_price = SUM(all merged)`; `payment_method` = merged JSON
   array (concatenate entries; optionally consolidate by summing amounts per `type`, via the existing
   sanitize helper); keep target's `date_created` (note: could use earliest instead). Set
   `auction_name = <chosen name>`.
4. **Delete sources** — `DELETE FROM auctions WHERE id = source` for each non-target.
5. **UI** — add a checkbox to each `.auction-tab` header + a "Merge selected" button in the auction
   container toolbar. With ≥2 checked, open a small modal to pick which selected name to keep (radio),
   then POST. On success, redraw via existing `loadAuctions()`. JS in `static/` (CSP — no inline).

**Notes / risks.**
- **Singles (id=1) is immutable** (can't be deleted/renamed). If Singles is among the selected, it
  **must** be the target (kept) and its name stays "Singles" — enforce server-side and in the name picker.
- Require ≥2 distinct ids; reject merging an auction into itself.
- Sold items keep their `auction_id`; reassigning it is safe (`sale_items` references `card_id`, not auction).
- Inventory totals are computed globally (no cached per-auction sums), so nothing else needs reconciling.
- After item 3 ships, `sealed.quantity` moves with the row automatically — no extra handling.

---

## 7. Move a single item to another tab + custom note (tab-based disposal)

**What.** Refines item 2. Instead of (or as well as) a status flag, handle non-sale cases —
giveaway, personal, **marketing/unboxing** — by **moving the item into a separate tab** and writing a
**custom note**. Needs two things that don't exist yet: moving a *single* item between tabs, and a tab
that is **excluded from inventory** (so a "Giveaway" tab's items don't count as stock or appear in sales).

**Open design choices (decide at implementation — defaults suggested):**
- Relationship to item 2: *suggested default* — this **supersedes** item 2's per-item flag; disposal is
  done by tabs + notes. (Alternative: keep both.)
- Tab kind: *suggested default* — **free custom tabs** you create and mark as disposal. (Alternative:
  also ship pre-made Giveaway/Personal/Marketing tabs.)
- Note location: *suggested default* — **per-item note**. (Alternative: tab-level, or both.)

**Where.**
- `tradeTracker/actions.py` — new single-item move route; `/inventoryValue` (`:439`) must exclude
  disposal tabs; auction create path.
- `tradeTracker/migration.py` — add `auctions.is_disposal` (flag) and a note column
  (`cards.note` / `sealed.note`, and/or `auctions.note`).
- `tradeTracker/static/scripts/main.js` — "Move to tab" UI on an item; exclude disposal tabs from the
  sale/cart flow; show notes.
- `tradeTracker/templates/index.html` — tab create form gets a "disposal tab" toggle.

**How.**
1. **Single-item move** — `POST /moveItem` `{type: card|sealed|bulk, id, target_auction_id}` →
   `UPDATE <table> SET auction_id = ?`; for bulk, reuse the ON CONFLICT upsert (item 6) for collisions.
2. **Disposal tab flag** — `auctions.is_disposal` via idempotent migration; exclude `is_disposal=1`
   tabs from `/inventoryValue` and from sellable item lists (these items generate **no income**, per item 2).
3. **Custom note** — add note column(s); editable inline (dblclick like other fields) and shown on the item.
4. **UI** — item-row "Move to…" picker (target tab dropdown) + note field; disposal tabs visually marked.

**Notes / risks.** Overlaps items 2 and 6 — if this approach is chosen, fold item 2 into it and reuse
item 6's reassignment/upsert logic. Keep purchase cost intact; just record no income for disposed items.

---

## 8. Improve handling of special / Unicode symbols

**What.** Special characters in card names and buyer text — Pokémon names (`Nidoran♀`, `Flabébé`,
`Farfetch'd`), `™`, Slovak diacritics (`č š ž á`), smart quotes, en-dashes — get mangled/dropped in a
few places. Storage and display are already fine (SQLite UTF-8, parameterized queries, DOMPurify
display, and the **sold-report PDF already embeds `fonts/DejaVuSans.ttf`**). Fix the three real gaps.

**1 — Invoice / credit-note PDF font (HIGH, primary).** `tradeTracker/generateInvoice.py` uses the
**InvoiceGenerator** fork (reportlab) with no custom font → defaults to Helvetica (latin-1), so special
chars render as boxes or vanish in invoices.
- Fix: register the Unicode TTF already in the repo (`tradeTracker/fonts/DejaVuSans.ttf` +
  `-Bold`) with reportlab (`pdfmetrics.registerFont(TTFont(...))`) and make the generator use it.
  The InvoiceGenerator fork is pinned (`requirements.txt:22`) — confirm its font hook; if it hardcodes
  Helvetica, register the font before generation or patch the fork.
- Affects card names (`:119`–`141`), sealed names, buyer name/address (`:64,71-73,211,217-219`).

**2 — Diacritic/case-insensitive matching (MEDIUM).** SQLite's `UPPER()/LOWER()` only fold ASCII, so
accented searches/matches fail.
- Search: `actions.py` (`~:1547`–`1564`, `UPPER(...) LIKE UPPER(?)`) won't match `Flabébé` from a
  lowercase query.
- Card dedupe match: `api.py` (`:128,:149`, `lower(card_name)=?`) can mis-match accented names → dup cards.
- Fix: normalize both sides in Python (`unicodedata.normalize`/casefold), or register a Unicode-aware
  SQLite function/collation, or fold diacritics for matching. Add a small shared helper and reuse it.

**3 — PDF filenames (MEDIUM).** `generateInvoice.py` builds output filenames from the buyer name
(`:165,171,306,311`) and writes to disk via `open()` (`:174`); on Windows, invalid chars
(`: * ? " < > |`) break it, accents untested.
- Fix: sanitize/transliterate the name for the on-disk filename. For downloads, Werkzeug's
  `send_file(download_name=...)` already RFC 5987-encodes UTF-8 (`actions.py:760,829,1700,1721`) —
  verify it, but the disk write is the real risk.

**Notes / risks.** InvoiceGenerator is a third-party pinned fork — the font injection is the main
unknown; budget time to read the fork. Verify with a test invoice containing
`Nidoran♀ / Flabébé / Farfetch'd / Ján Hájek`. `capitalize()` on accented text is fine (FYI only).

---

## 9. Shopify integration — pull orders → auto-invoice + autosend email

**What.** Connect to Shopify so orders placed on the storefront flow into Trade Tracker, generate
the invoice automatically, and email it to the buyer with the PDF attached — no manual step. User
flagged this as "asi ale neviem ako to funguje" — exact mechanics are open, needs a design pass.

**Open design choices (decide at implementation — defaults suggested):**
- Source of truth: *suggested default* — Shopify owns orders; Trade Tracker subscribes to
  `orders/create` webhooks and writes a local sale + invoice. (Alternative: push Trade Tracker
  sales to Shopify as draft orders.)
- Email transport: *suggested default* — SMTP creds in `.env`, attach the existing invoice PDF.
  (Alternative: let Shopify's own email system send a link to the hosted PDF.)
- SKU mapping: *suggested default* — require an explicit `sku` per sealed/card row (new column),
  matched against Shopify line item SKU; unmatched lines flag the sale for manual reconciliation.

**Where.**
- `tradeTracker/services/` — new `shopify/` package (mirror the abstract-client pattern proposed
  for carriers in item 4); HTTP via `requests` with timeouts.
- `tradeTracker/__init__.py` — webhook host: either reuse `api.*` (extension blueprint) or add a
  dedicated `shopify.*` route under `api` so it's not gated by Cloudflare Access JWT.
- `tradeTracker/api.py` — webhook receiver; verify Shopify HMAC header (`X-Shopify-Hmac-Sha256`).
- `tradeTracker/services/sale_service.py` — order → sale translation (line items, buyer, shipping).
- `tradeTracker/generateInvoice.py` — existing invoice; reuse for the email attachment.
- `tradeTracker/migration.py` — `sales.shopify_order_id TEXT UNIQUE` (idempotency); optional
  `cards.sku` / `sealed.sku` for matching.
- `.env` + README env table — `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`, `SHOPIFY_WEBHOOK_SECRET`,
  SMTP creds (`SMTP_HOST/PORT/USER/PASS/FROM`).

**How.**
1. **Migration** — `addShopifyOrderIdToSales`, idempotent; add SKU columns to `cards`/`sealed`.
2. **Webhook** — `POST /shopify/webhook/orders-create` (no JWT, but verify HMAC). Idempotent on
   `shopify_order_id` — duplicate deliveries are a no-op.
3. **Order → sale** — map line items by SKU to existing inventory rows; reuse `sale_service` to
   write `sales` + `sale_items` + mark inventory sold. Buyer info → existing AES-GCM `notes` JSON
   (`sale_service.py:52`).
4. **Invoice + email** — call `generateInvoice` after sale insert; send via SMTP with PDF attached
   to the buyer email from the order payload; log send result on the sale row.
5. **Failure path** — if SKU match fails or HMAC is invalid, store the raw payload + reason in a
   `shopify_orders_pending` table for manual review (don't drop deliveries).

**Notes / risks.**
- Needs a Shopify dev/test store + a private/custom app to develop against — gate the whole
  feature behind config presence (no creds → routes 404).
- Fix item 8 first or buyers with diacritics get mangled invoice PDFs.
- SMTP creds are sensitive — production loads from environment (not `.env`), per the existing
  convention (README env table).
- First **inbound webhook** surface; verify HMAC strictly and rate-limit even though Shopify is
  trusted (replay attacks if the secret leaks).

---

## 10. Ťarchopis / dobropis (debit / credit note) system

**What.** Issue **credit notes (dobropis)** and **debit notes (ťarchopis)** — Slovak corrective
tax documents tied to an original invoice. Today the app only issues invoices; returns
(`/orderReturn`, `actions.py:651`) restore inventory silently and don't produce the corrective
document an accountant needs. Covers both **full returns** (dobropis for the whole amount) and
**partial corrections** (e.g. underbilled shipping → ťarchopis).

**Where.**
- `tradeTracker/generateInvoice.py` — current invoice generator (`:64`–`311`); add credit-/debit-
  note variants. Layout reuses invoice; header reads "Dobropis" / "Ťarchopis"; must reference
  original invoice number + state the reason; line amounts negative for credit.
- `tradeTracker/actions.py` — `/orderReturn` (`:651`) should auto-emit a dobropis; add
  `/issueDobropis/<sale_id>` and `/issueTarchopis/<sale_id>` for standalone corrections.
- `tradeTracker/migration.py` — new `corrective_documents` table (id, original_sale_id, type
  `'dobropis'|'tarchopis'`, document_number, date, amount, reason, pdf bytes or path).
- `tradeTracker/db.py` — schema reference.
- `tradeTracker/static/scripts/sold.js` — UI to issue from a past sale.

**How.**
1. **Migration** — `addCorrectiveDocumentsTable(db_path)`, idempotent `sqlite_master` check.
   Numbering sequence is **separate from invoices** and must be gapless per year (Slovak
   convention) — store year + sequence and compute the display number.
2. **Renderer** — extend `generateInvoice.py` with `generateCreditNote(...)` /
   `generateDebitNote(...)`, reusing layout helpers; mandatory fields: reference to original
   invoice, date of original supply, reason for correction, corrected amounts.
3. **Routes** — both POST, in `actions` blueprint. Body picks the line items being corrected
   (subset of original) + reason. Insert `corrective_documents` row, return PDF.
4. **Hook into return** — `/orderReturn` triggers `generateCreditNote` for the returned amount
   automatically; the existing return stock-restoration logic stays unchanged.
5. **UI** — sold-history detail: "Issue dobropis" / "Issue ťarchopis" buttons, reason field, line
   picker; list previously issued correctives under the sale.

**Notes / risks.**
- Slovak tax law has specific content requirements for corrective documents — confirm with the
  accountant before locking the layout (mandatory fields, retention, numbering).
- Numbering must be gapless per year — protect with a transaction + `SELECT MAX ... FOR UPDATE`
  equivalent (SQLite serialized writes already give this, but be deliberate).
- Inherits item 8's Unicode font fix — apply it to these PDFs too.

---

## 11. Unified purchases view — see all bought items including ones already sold

**What.** A single place to answer "did I ever buy X, and what happened to it?". Today auction
tabs only show in-stock items (sold ones disappear), and the sold-history (`sold.js`) is organized
per-sale, not per-purchase batch. Add the ability to see **every item ever bought in this tab** —
in-stock, sold, written off (item 2/7), opened (item 1) — with the relevant outcome badge.

**Where.**
- `tradeTracker/actions.py` — `/loadCards/<auction_id>` and `/loadSealed/<auction_id>` filter to
  in-stock (`sold_date IS NULL`); extend with `?include_sold=1` (and later `include_disposed`,
  `include_opened`).
- `tradeTracker/templates/index.html` — auction-tab header (`:107`–`137`); add a "Show sold" toggle.
- `tradeTracker/static/scripts/main.js` — card/sealed render path (`~:2454`); render sold rows
  greyed out with badge ("Sold YYYY-MM-DD · X €").
- Optional: a top-level "All purchases" page summarizing tabs (bought / sold / in stock totals).

**How.**
1. **Backend** — accept `?include_sold=1` on the existing load endpoints; when set, drop the
   in-stock filter and join `sale_items` + `sales` to attach sold price + sold date per row.
2. **Render** — toggle per auction tab (off by default — keeps tabs uncluttered); when on, sold
   rows render below in-stock, visually distinct (greyed, strikethrough on quantity), with a sold
   badge and a "view sale" link into sold-history.
3. **Cross-feature badges** — same row also surfaces disposal state (items 2 / 7: "vyradené —
   giveaway") and opened state (item 1: "Opened YYYY-MM-DD"). Single endpoint returns all
   relevant statuses — UI just picks the badge.
4. **Optional global view** — new tracker page `/purchases` listing every tab with computed
   totals (bought count + value, sold count + revenue, still-in-stock count + value).

**Notes / risks.**
- Pure read feature — no schema changes required, only an additional filter mode + render path.
- Plays directly with items 1 (opened boxes still show here) and 2/7 (disposed items still show
  here) — ship after those so the badges have something to display.
- Don't change the default — in-stock-only stays the default per-tab view; the toggle is opt-in.

---

## 12. End-user výkup (buyout) software — public-facing seller form

**What.** A **public form** where end users (sellers) submit cards they want to sell to you —
name, condition, photos, asking price — landing in Trade Tracker as a **pending buyout offer**
for admin review. Today the app is single-tenant admin-only; this is the **first externally-
exposed write surface**, so security/abuse handling drives most of the design.

**Where.**
- `tradeTracker/__init__.py` — host-based routing already isolates `api.cardanvil.sk` and
  `app.cardanvil.sk` (`restrict_by_host`); add a third host (e.g. `vykup.cardanvil.sk`) that does
  **not** require Cloudflare Access JWT, only CSRF + rate limit + CAPTCHA.
- New `tradeTracker/buyout.py` blueprint for the public routes (separate from `actions`).
- `tradeTracker/migration.py` — new `buyout_offers` table (id, submitter_name, submitter_email,
  submitter_phone, items_json, photos_json, status `pending|accepted|rejected`, created_at, ip,
  user_agent).
- `tradeTracker/templates/buyout/` — new public template (no app chrome, simpler styling).
- `tradeTracker/static/buyout/` — photo upload UI; client-side type + size validation (server
  re-validates).
- Admin: a "Buyout offers" tab in the app for review; accepting converts the offer into a new
  auction (purchase batch) via the existing `/addAuction` flow with submitter prices as cost basis.

**How.**
1. **Migration** — `addBuyoutOffersTable(db_path)`, idempotent.
2. **Public host** — new blueprint resolvable only on `vykup.*`; relax JWT for that host while
   keeping CSRF (Flask-WTF) + rate limit (Flask-Limiter) + hCaptcha. CSP `script-src` needs
   adjusting to allow the CAPTCHA provider — scope the relaxed CSP to the public host only.
3. **Upload pipeline** — photos go to a gitignored uploads dir, store relative paths in
   `photos_json`; strip EXIF; magic-byte sniff (don't trust MIME); cap per-file size + total
   payload; reject anything that isn't `image/jpeg|png|webp`.
4. **Admin review** — new tab in the app: pending offers list → detail view → "Accept" creates a
   new auction with cards/sealed at submitter-provided prices (or admin-edited), retains link to
   the original offer id; "Reject" sets status with optional reason.
5. **Notification** — optional email to admin on new submission (reuse SMTP creds from item 9).
6. **Tracking integration** — overlaps items 4/5: once accepted and the buyer ships the cards in,
   you can issue them a Packeta/Slovak Post **inbound** label from the same offer.

**Notes / risks.**
- First public write surface — **security review required** before launch: rate limiting,
  CAPTCHA, file upload hardening, magic-byte sniffing, optional AV scan, signed URLs for stored
  photos if served back.
- GDPR — submitter PII (name, email, phone, photos) needs a retention policy + deletion-on-
  request flow; add a clear privacy notice on the form.
- "Not a binding offer" disclaimer needed on the form; confirm wording with accountant/legal.
- Spam will arrive — plan for blocklist tooling (IP, email domain) and manual approval before
  any auto-actions (don't auto-create auctions on accept without human click).
- The 24-May-26 whiteboard sketch (`TCGP → APP → PACK → POST → LABELS`) describes the full
  pipeline: items 4/5 deliver PACK/POST/LABELS; the `TCGP → APP` step is already covered by the
  existing Chrome-extension import (no new feature needed there — flag to the user if a separate
  TCGPlayer marketplace integration was meant instead).

---
# DONE
##  13. Fix "Total Positive Margin" calculation on the monthly sold report (bug)

> **Related: item 15 (normal-DPH vs margin-scheme split).** Do these together — both touch the
> same margin loops (`actions.py:886`–`903`). Item 13 fixes the sign bug; item 15 stops counting
> normal-VAT goods in the margin at all. Don't fix one without the other or the buckets stay wrong.


**What.** The monthly sold report's **Total Positive Margin** is wrong. The cards and sealed loops
correctly split each item's margin into positive vs negative by sign, but the **bulk/holo loop adds
its margin to `total_pos_margin` unconditionally — no sign check** — so a *negative* bulk margin
gets folded into the positive bucket (deflating it) and never lands in negative margin. The
positive/negative split no longer means what the labels say.

**Where.**
- `tradeTracker/actions.py` — `generatePDF()` margin loops (`:886`–`903`); the bug is the bulk loop
  at `:901`–`903`. Totals are printed at `:912`–`916`.

**How.**
1. **Primary fix** — make the bulk loop mirror the cards/sealed pattern: compute
   `curr_margin = Decimal(item['total_price'] - item['quantity'] * unit_price)` then
   `if curr_margin > 0: total_pos_margin += curr_margin else: total_neg_margin += curr_margin`
   (currently it always does `total_pos_margin += ...`).
2. **Verify the sealed exclusion** — the sealed loop only counts margin when `auction_id is not None`
   (`:893`–`894`), so pool sealed (auction_id NULL) are silently dropped from *both* margin buckets
   while still counting in `total_buy_price`/`total_sell_price`/`total_profit` (`:874`–`880`).
   Confirm with the user whether that's intended; if not, drop the `auction_id` guard so sealed margin
   is split like cards.
3. **Sanity check the identity** — after the fix, `total_pos_margin + total_neg_margin` should equal
   `total_profit` (modulo the sealed-exclusion decision in step 2). Worth a quick assertion/test.

**Notes / risks.**
- This is a **correctness bug in an accounting-facing report** — prioritise over the feature items above.
- `total_profit` itself (`:880`) is computed independently and is correct; only the pos/neg split is broken.

---

# DONE
## 14. Show sale date (dátum predaja) per card on the monthly sold report

**What.** The monthly sold report lists each sold card (name, number, buy/sell price, margin) but
**not the date it sold**. Add the sale date so each card row shows when it was sold within the report month.

**Where.**
- `tradeTracker/actions.py` — cards query in `generateSoldReport()` (`:779`–`785`) selects
  `card_name, card_num, card_price, sell_price` but **not** `s.sale_date`; the cards table in
  `generatePDF()` (header `:949`–`956`, rows `:958`–`1005`, plus the page-break header redraw `:976`–`983`).

**How.**
1. **Query** — add `s.sale_date` (and alias it) to the cards SELECT at `:780`–`784`; it's already
   joined via `sales s` so no new join is needed.
2. **PDF table** — add a "Sale Date" column to the cards table header (both the initial draw `:951`–`955`
   and the page-break redraw `:978`–`982`) and render `card['sale_date']` per row (`:998`–`1002`).
   Format to date-only (`sale_date` is a datetime string — slice/parse to `YYYY-MM-DD`).
3. **Widths** — current columns total 175mm (50+35+30+30+30) within ~190mm usable A4 width; shrink the
   existing cells (e.g. trim Card Name / numeric columns) to fit the new ~25–30mm date column.

**Notes / risks.**
- Pure read/display change — no schema or migration needed (`sales.sale_date` already exists).
- Optionally extend the same date column to the sealed and bulk tables for consistency, but bulk rows
  are GROUP BY'd across the month (`:791`–`796`) so they have no single sale date — leave bulk as-is.

---

## 15. Keep normal-DPH goods out of the margin — report them separately (bug + feature)

**What.** The business runs the **§66 margin scheme** (used collectibles — DPH is included in the
margin, `tax=Decimal("0")` is hardcoded in every invoice line, see `generateInvoice.py:124` and the
§66 notes at `:59`/`:87`/`:234`). But **not everything is margin-scheme**: sealed/new goods bought
from a distributor carry **normal 23% DPH** — the app already half-knows this (the "no VAT" column
divides sealed price by 1.23, `templates/index.html:119` + `static/scripts/main.js:2483`). The
**monthly sold report folds every item into the same positive/negative margin buckets** regardless of
tax regime (`actions.py:886`–`903`), so normal-DPH goods get counted as if they were margin-scheme
goods — **the margin total is wrong** (margin is a §66 concept and shouldn't include normal-VAT items).

**Goal.** Normal-DPH items must **not** be added to `total_pos_margin` / `total_neg_margin`. They
**still belong in the sales report** (buy/sell/profit totals + their own table) but as a **separate
section** with their own DPH breakdown (base / 23% DPH / total), kept apart from the margin items.

**Where.**
- `tradeTracker/migration.py` — new idempotent flag marking an item's tax regime (none today).
- `tradeTracker/actions.py` — `generateSoldReport()` queries (`:779`–`796`) must select the flag;
  `generatePDF()` margin loops (`:886`–`903`) must skip normal-DPH items; totals print at `:912`–`919`.
- `tradeTracker/actions.py` `/addSealed` (`:386`) + the Chrome-extension import payload — set the flag
  on intake (sealed/distributor goods default to normal-DPH; singles default to margin-scheme).
- `tradeTracker/static/scripts/main.js` (add/import forms) + `templates/index.html` — flag input/column.

**How.**
1. **Decide the flag's home (open choice — suggested default below).**
   - *Suggested default:* a per-item boolean on `cards`/`sealed` (and `bulk_items`), e.g.
     `is_margin_scheme INTEGER NOT NULL DEFAULT 1` (existing rows = margin, the current behaviour).
     Set it to `0` for normal-DPH goods. Most flexible, mixes regimes within one auction tab.
   - *Alternatives:* a tax-regime flag on the **auction tab** (`auctions`), or infer from item kind
     (all sealed = normal-DPH) — simpler but wrong if a sealed item is ever resold as margin goods.
     **Confirm with the user / accountant which granularity they actually need.**
2. **Migration** — add the column(s) via the `PRAGMA table_info` idempotent pattern
   (`migration.py:52` `_add_sold_date_to_cards`), register in `migrate_database()`.
3. **Intake** — `/addSealed` + extension import accept the regime; default sealed/new goods to
   normal-DPH, singles to margin-scheme. Add the toggle to the manual forms.
4. **Report — exclude from margin.** In the three margin loops (`:886`–`903`), `continue` when the
   item is normal-DPH so it never touches `total_pos_margin`/`total_neg_margin`. (Do this **on top of**
   item 13's sign fix — the bulk loop also needs the `> 0` split.)
5. **Report — separate DPH section.** Accumulate normal-DPH items into their own totals
   (base = sell/1.23, DPH = sell − base, like the existing `total_shipping_*` block at `:905`–`910`)
   and render a distinct "Normal DPH goods" table + subtotal, separate from the margin tables.
6. **Keep them in the headline totals.** `total_buy_price`/`total_sell_price`/`total_profit`
   (`:874`–`880`) should still include normal-DPH items (they're real sales) — only the **margin**
   buckets exclude them. Make the report state both figures clearly so the accountant sees the split.

**Notes / risks.**
- **Accounting-facing correctness** — margin (§66) and normal-DPH (§2) are different tax regimes that
  must not be commingled; mislabeling either way is a tax error. Confirm the exact split + wording
  with the accountant before locking the report layout.
- Tightly coupled to **item 13** — same loops; ship them in one pass (see the cross-ref on item 13).
- The `total_pos_margin + total_neg_margin == total_profit` identity from item 13 step 3 **no longer
  holds** once normal-DPH items are excluded from margin but kept in profit — update that check to
  `margin_buckets == profit_of_margin_items_only`.
- Ties to item 8 (Unicode) only incidentally; no overlap with the carrier/Shopify items.
