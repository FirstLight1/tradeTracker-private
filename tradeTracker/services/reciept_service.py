from abc import ABC, abstractmethod
import tradeTracker.services.models as models
import tradeTracker.generateInvoice as generateInvoice


class RecieptService(ABC):
    @abstractmethod
    def issue(self, sale_input, db) -> models.ReceiptResult: ...


class InvoiceReceiptService(RecieptService):
    def issue(self, sale_input, db) -> models.ReceiptResult:
        try:
            invoice_num = db.execute('SELECT invoice_number FROM sales WHERE invoice_number NOT LIKE "S%" ORDER BY id DESC LIMIT 1').fetchone()[0]
            invoice_num = int(invoice_num) + 1
        except:
            raise Exception("Failed to get invoice_number")

        pdf, invoice_num = generateInvoice.generate_invoice(
            reciever=sale_input.reciever or [],
            items=sale_input.cards or [],
            invoice_num=invoice_num,
            sealed=sale_input.sealed or [],
            bulk=sale_input.bulk,
            holo=sale_input.holo,
            ex=sale_input.ex,
            payment_methods=sale_input.payments or [],
            shipping=sale_input.shipping,
            type="invoice",
        )
        return models.ReceiptResult(
            kind="invoice", number=invoice_num, raw=pdf
        )


class EKasaReceiptService(RecieptService):
    def issue(self, sale_input, db) -> models.ReceiptResult:
        invoice_num = db.execute(
            "SELECT invoice_number FROM sales WHERE invoice_number LIKE 'S%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if invoice_num is not None and invoice_num[0] is not None:
            s = invoice_num[0][0]
            num = int(invoice_num[0][1:])
            num += 1
            invoice_num = s + str(num)
        else:
            invoice_num = "S1"
        return models.ReceiptResult(kind="ekasa", number=invoice_num)
        # neskôr: call VAROS API
        # raise NotImplementedError
