
from decimal import Decimal
from itertools import count
import os
import sys
from datetime import date, datetime

os.environ["INVOICE_LANG"] = "sk"
from InvoiceGenerator.api import Invoice, CreditNote, Item, Client, Provider, Creator
from InvoiceGenerator.pdf import SimpleInvoice, CreditNoteInvoice
from flask import current_app


BULK_ITEM_DEFAULTS = {
    'bulk': {'unit_price': Decimal('0.01'), 'description': 'Common bulk cards'},
    'holo': {'unit_price': Decimal('0.03'), 'description': 'Holo bulk cards'},
    'ex': {'unit_price': Decimal('0.15'), 'description': 'EX bulk cards'}
}


def add_bulk_invoice_item(invoice, item, item_type):
    if not item:
        return
    item_defaults = BULK_ITEM_DEFAULTS[item_type]
    invoice.add_item(Item(
        count=item.get("quantity", 0),
        price=Decimal(str(item.get("unit_price", item_defaults['unit_price']))),
        unit="ks",
        description=item_defaults['description'],
        tax=Decimal("0")
    ))

def generate_invoice(reciever, items=None, sealed=None , bulk=None, holo=None, ex=None, payment_methods=None, shipping=None):
    # Read invoice number from env.txt
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        env_dir = os.path.join(os.environ['APPDATA'], 'TradeTracker')
        os.makedirs(env_dir, exist_ok=True)
        env_path = os.path.join(env_dir, 'env.txt')
        # Get the base path where PyInstaller unpacks files
        base_path = sys._MEIPASS
        logo_path = os.path.join(base_path, 'tradeTracker', 'static', 'images', 'logo.png')
    else:
        # Running in development
        env_path = os.path.join(os.path.dirname(__file__), 'env.txt')
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'logo.png')
    
    # Read or create env.txt with invoice_num
    ## TODO error handling
    try:
        with open(env_path, 'r') as f:
            invoice_num = f.read().strip()
            if not invoice_num:
                return 
                #return jsonify({'status': 'error', 'message':'Failed to get invoice number'}), 500
    except FileNotFoundError:
        return
        #return jsonify({'status':'error', 'message': 'Failed to open env.txt'}), 500
    
    invoice_date = date.today()
    # Set language to Slovak (or English 'en') if supported by your system locale

    # 1. Define the Supplier (Dominik Forró - CARD ANVIL)
    # Data extracted from source: 39-48, 52-63
    provider = Provider(
        summary="Dominik Forró - CARD ANVIL",
        address="Vahovce 94",
        city="Váhovce",
        zip_code="92562",
        phone="0949 759 023",
        email="dominikforro95@gmail.com",
        bank_name="Tatra banka, a.s.",
        bank_account="SK9511000000002945283029",  # IBAN
        # Mapping Slovak IDs to library fields:
        ir="57310041",       # IČO
        vat_id="1130287664", # DIČ
        tax_id="SK1130287664", # IČ DPH
        note="Osoba zapísaná v Živnostenskom registri pod číslom \n220-42582, vydal Okresný úrad Galanta dňa\n 5.11.2025. \nPlatiteľ DPH formou §66.\n Úprava zdaňovania prirážky - použitý tovar\n(§ 74 ods. 1 pism. n) zákona o DPH\nsa vztahuje len na marzove polozky)",
        logo_filename=logo_path
    )
    
    try:
        nameAndSurname = " ".join([part.capitalize() for part in reciever.get("nameAndSurname").split(" ")])
    except:
        ##TODO - change this to an error message
        nameAndSurname = ' '
    # 2. Define the Client
    # Data extracted from source: 50-51
    client = Client(
        summary = nameAndSurname,
        address=reciever.get("address").capitalize() if reciever.get("address") is not None else ' ',
        city=reciever.get("city").capitalize() if reciever.get("city") is not None else ' ',
        country=reciever.get("state", "").capitalize() if reciever.get("state") is not None else ' '
    )

    # 3. Create the Invoicegene
    invoice = Invoice(client, provider, Creator("Dominik Forró"))
    invoice.number = invoice_num                # Invoice No.
    invoice.variable_symbol = invoice_num       # VS
    invoice.currency = u'€'
    invoice.currency_locale = 'en_US.UTF-8'
    invoice.currency_code = 'EUR'
    invoice.date = invoice_date          # Date of exposure (Dátum vystavenia)
    invoice.qr_due_date = invoice_date 


    invoice.note = "Uplatnený osobitný režim zdaňovania podľa §66 zákona o DPH – daň z pridanej hodnoty je zahrnutá v marži.\nPredmet plnenia je použitý zberateľský tovar – individuálne ocenené kusy.\nReklamácia je možná výlučne pri preukázateľnej neautenticite alebo nesúlade s deklarovaným stavom.\nKupujúci nemá nárok na vrátenie tovaru bez uvedenia dôvodu.\nÚprava zdaňovania prirážky - použitý tovar (§ 74 ods. 1 písm. n) zákona o DPH)"
    
    # Format payment methods for display
    print(payment_methods)
    if payment_methods and len(payment_methods) > 0:
        result = {}
        for payment in payment_methods:
            t = payment['type']
            result[t] = result.get(t, 0) + payment['amount']
    
        unique_payment = [{'type': t, 'amount': round(amt, 2)} for t, amt in result.items()]
        payment_strings = ", ".join(f"{item['type']} :{item['amount']}€ " for item in unique_payment)
        invoice.paytype = payment_strings
    else:
        # Fallback to old single payment method for backwards compatibility
        invoice.paytype = reciever.get("paymentMethod", "Hotovosť")
    
    invoice.taxable_date = datetime.now() # Dátum splatnosti
    invoice.use_tax=True
    
    # Convert paybackDate string to date object (HTML date input format: YYYY-MM-DD)
    payback_str = reciever.get("paybackDate")
    if payback_str:
        invoice.payback = datetime.strptime(payback_str, "%Y-%m-%d").date()
    else:
        invoice.payback = invoice_date  # Default to today if not provided
    # 4. Add Items
    if len(items) > 0 and items is not None:
        for item in items:
            mv = item.get("marketValue")
            if mv is None or str(mv) == "":
                continue
            market_value_decimal = Decimal(str(mv))
            invoice.add_item(Item(
                count=1,
                price=market_value_decimal,
                unit="ks",
                description=item.get("cardName") + " " + item.get("cardNum"),
                tax=Decimal("0") # Neplatiteľ DPH (Non-VAT payer)
                ))
           
    if sealed:
        for item in sealed:
            if item.get("auctionId") == None:
                tax = Decimal("23")
                price = Decimal(str(item.get("marketValue").replace("€",""))) / Decimal('1.23')
            else:
                tax = Decimal("0")
                price = Decimal(str(item.get("marketValue").replace("€","")))
            invoice.add_item(Item(
                count=1,
                price=price,
                unit="ks",
                description=item.get("sealedName"),
                tax=tax
            ))

    add_bulk_invoice_item(invoice, bulk, 'bulk')
    add_bulk_invoice_item(invoice, holo, 'holo')
    add_bulk_invoice_item(invoice, ex, 'ex')

    if shipping:
        shippingPrice = Decimal(str(shipping.get('shippingPrice'))) / Decimal('1.23')
        invoice.add_item(Item(
            count=1,
            price=shippingPrice,
            description=shipping.get("shippingWay"),
            unit="ks",
            tax=Decimal("23")
        ))

    # 5. Generate PDF
    pdf = SimpleInvoice(invoice)
    
    # Determine the save path based on environment
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        app_data_dir = os.path.join(os.environ['APPDATA'], 'TradeTracker', 'Invoices')
        os.makedirs(app_data_dir, exist_ok=True)
        output_filename = f"{invoice_num}_Invoice_{invoice_date.strftime('%Y%m%d')}_{reciever.get('nameAndSurname', 'client').replace(' ', '_')}.pdf"
        output_path = os.path.join(app_data_dir, output_filename)
    else:
        # Running in development
        invoices_dir = os.path.join(current_app.instance_path, 'invoices')
        os.makedirs(invoices_dir, exist_ok=True)
        output_filename = f"{invoice_num}_Invoice_{invoice_date.strftime('%Y%m%d')}_{reciever.get('nameAndSurname', 'client').replace(' ', '_')}.pdf"
        output_path = os.path.join(invoices_dir, output_filename)
    
    pdf.gen(output_path, generate_qr_code=True)

    print(f"Successfully generated: {output_path}")


    # Write incremented invoice number back
    with open(env_path, 'w') as f:
        f.write(str(int(invoice_num) + 1))
    
    return output_path, invoice_num

def generateCreditNote(reciever, items=None, sealed=None, bulk=None, holo=None, ex=None, payment_methods=None, shipping=None, original_invoice_num=None):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        logo_path = os.path.join(base_path, 'tradeTracker', 'static', 'images', 'logo.png')
    else:
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'logo.png')

    cn_num = '1'

    invoice_date = date.today()

    provider = Provider(
        summary="Dominik Forró - CARD ANVIL",
        address="Vahovce 94",
        city="Váhovce",
        zip_code="92562",
        phone="0949 759 023",
        email="dominikforro95@gmail.com",
        bank_name="Tatra banka, a.s.",
        bank_account="SK9511000000002945283029",
        ir="57310041",
        vat_id="1130287664",
        tax_id="SK1130287664",
        note="Osoba zapísaná v Živnostenskom registri pod číslom \n220-42582, vydal Okresný úrad Galanta dňa\n 5.11.2025. \nPlatiteľ DPH formou §66.\n Úprava zdaňovania prirážky - použitý tovar\n(§ 74 ods. 1 pism. n) zákona o DPH\nsa vztahuje len na marzove polozky)",
        logo_filename=logo_path
    )

    try:
        nameAndSurname = " ".join([part.capitalize() for part in reciever.get("nameAndSurname").split(" ")])
    except:
        nameAndSurname = ' '

    client = Client(
        summary=nameAndSurname,
        address=reciever.get("address", "").capitalize() if reciever.get("address") is not None else ' ',
        city=reciever.get("city", "").capitalize() if reciever.get("city") is not None else ' ',
        country=reciever.get("state", "").capitalize() if reciever.get("state") is not None else ' '
    )

    invoice = CreditNote(client, provider, Creator("Dominik Forró"))
    invoice.number = f"CN{cn_num}"
    invoice.variable_symbol = f"CN{cn_num}"
    invoice.currency = u'€'
    invoice.currency_locale = 'en_US.UTF-8'
    invoice.currency_code = 'EUR'
    invoice.date = invoice_date


    ref_note = f"Dobropis k faktúre č. {original_invoice_num}. " if original_invoice_num else ""
    invoice.note = (
        ref_note +
        "Uplatnený osobitný režim zdaňovania podľa §66 zákona o DPH – daň z pridanej hodnoty je zahrnutá v marži.\n"
        "Predmet plnenia je použitý zberateľský tovar – individuálne ocenené kusy."
    )

    if payment_methods and len(payment_methods) > 0:
        result = {}
        for payment in payment_methods:
            t = payment['type']
            result[t] = result.get(t, 0) + payment['amount']
        unique_payment = [{'type': t, 'amount': round(amt, 2)} for t, amt in result.items()]
        payment_strings = ", ".join(f"{item['type']} :{item['amount']}€ " for item in unique_payment)
        invoice.paytype = payment_strings
    else:
        invoice.paytype = reciever.get("paymentMethod", "Hotovosť")

    invoice.taxable_date = datetime.now()
    invoice.use_tax = True

    payback_str = reciever.get("paybackDate")
    if payback_str:
        invoice.payback = datetime.strptime(payback_str, "%Y-%m-%d").date()
    else:
        invoice.payback = invoice_date

    if items and len(items) > 0:
        for item in items:
            mv = item.get("marketValue")
            if mv is None or str(mv) == "":
                continue
            invoice.add_item(Item(
                count=1,
                price=Decimal(str(mv)),
                unit="ks",
                description=item.get("cardName", "") + " " + item.get("cardNum", ""),
                tax=Decimal("0")
            ))

    if sealed:
        for item in sealed:
            if item.get("auctionId") is None:
                tax = Decimal("23")
            else:
                tax = Decimal("0")
            mv = item.get("marketValue") or item.get("market_value", "0")
            invoice.add_item(Item(
                count=1,
                price=Decimal(str(mv).replace("€", "")),
                unit="ks",
                description=item.get("sealedName") or item.get("name", ""),
                tax=tax
            ))

    add_bulk_invoice_item(invoice, bulk, 'bulk')
    add_bulk_invoice_item(invoice, holo, 'holo')
    add_bulk_invoice_item(invoice, ex, 'ex')

    if shipping:
        shippingPrice = Decimal(str(shipping.get('shippingPrice'))) / Decimal('1.23')
        invoice.add_item(Item(
            count=1,
            price=shippingPrice,
            description=shipping.get("shippingWay"),
            unit="ks",
            tax=Decimal("23")
        ))

    pdf = CreditNoteInvoice(invoice)

    if getattr(sys, 'frozen', False):
        app_data_dir = os.path.join(os.environ['APPDATA'], 'TradeTracker', 'Invoices')
        os.makedirs(app_data_dir, exist_ok=True)
        output_filename = f"Dobropis:{cn_num}_CreditNote_{invoice_date.strftime('%Y%m%d')}_{reciever.get('nameAndSurname', 'client').replace(' ', '_')}.pdf"
        output_path = os.path.join(app_data_dir, output_filename)
    else:
        invoices_dir = os.path.join(current_app.instance_path, 'invoices')
        os.makedirs(invoices_dir, exist_ok=True)
        output_filename = f"Dobropis:{cn_num}_CreditNote_{invoice_date.strftime('%Y%m%d')}_{reciever.get('nameAndSurname', 'client').replace(' ', '_')}.pdf"
        output_path = os.path.join(invoices_dir, output_filename)

    pdf.gen(output_path, generate_qr_code=False)
    print(f"Successfully generated credit note: {output_path}")

    
    return output_path, f"CN{cn_num}"


if __name__ == "__main__":
    generate_invoice()
