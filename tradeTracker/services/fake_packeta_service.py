from uuid import uuid4
from tradeTracker.utils.fake_pdf_gen import make_fake_label_pdf
from tradeTracker.services.models import LabelResult

class FakePacketaService:
    def __init__(self):
        pass

    def create_packet(self, order, homeDelivery=False):
        return f"fake-packet-{uuid4()}"

    def packets_labels_pdf(self, packetIds: list):
        return make_fake_label_pdf(packetIds[0], "PACKETA")

    def packet_courier_number(self, packetId):
        return "fake-courier-number"

    def packet_courier_labels_pdf(self, packetIds: list):
        return make_fake_label_pdf(packetIds[0], "PACKETA")
