from abc import ABC, abstractmethod
import tradeTracker.services.models as models
import tradeTracker.generateInvoice as generateInvoice

class RecieptService(ABC):
    @abstractmethod
    def issue(self, sale_input) -> models.ReceiptResult:
        ...

class InvoiceReceiptService(RecieptService):
    def issue(self, sale_input) -> models.ReceiptResult:
        pdf_path, invoice_num = generateInvoice.generate_invoice(
            reciever=sale_input.reciever or [],
            items=sale_input.cards or [],
            sealed=sale_input.sealed or [],
            bulk=sale_input.bulk,
            holo=sale_input.holo,
            ex=sale_input.ex,
            payment_methods=sale_input.payments or [],
            shipping=sale_input.shipping,
        )
        return models.ReceiptResult(kind="invoice", number=invoice_num, file_path=pdf_path)

class EKasaReceiptService(RecieptService):
    def issue(self, sale_input) -> models.ReceiptResult:
        # neskôr: call VAROS API
        raise NotImplementedError
