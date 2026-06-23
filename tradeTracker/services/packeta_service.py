from zeep import Client
import os
from postal.parser import parse_address

class PacketaService:
    def __init__(self):
        self.client = Client('https://www.zasilkovna.cz/api/soap.wsdl')
        self.api_key = os.environ.get('PACKETA_API_KEY')
        self.FORMAT = "105x35mm on A4"
        self.OFFSET = 0

    def create_packet(self, order, homeDelivery = False):
        client = self.client
        name, *surname = order.reciever.nameAndSurname.split(' ')
        surname = ' '.join(surname)

        #TODO: create dict with categories
        weight = 0.99
        if ordes.reveiver.articleInfo.articleCategory.contains("Booster"):
            weight = 1.99
        elif ordes.reveiver.articleInfo.articleCategory.contains("Booster") and orders.reciever.articleInfo.articles >= 5:
            weight = 2.99

        #TODO: required attributes should raise exceptions
        attributes = {
                'number': order.orderId,
                'name': name,
                'surname': surname,
                'addressId': "NEED implementation",
                'email': getattr(order.reciever, 'email', None),
                'value': getattr(order.reciever, 'total', 0),
                'weight': weight,
                }


        if homeDelivery:
            address = dict(parse_address(order.reciever.address))
            homeDeliveryAttributes = {
                    'phone': order.reciever.phone,
                    'addressId': TBD,
                    'street': address.get('road'),
                    'houseNumber': address.get('house_number'),
                    'city': order.reciever.city,
                    'zip': order.reciever.zipCode,
                    # TODO real length and width
                    'size': {
                        'length': order.size.length,
                        'width': order.size.width,
                        }
                    }
            attributes.update(homeDeliveryAttributes)

        try:
            packetIdDetail = client.service.createPacket(self.api_key, attributes)
            packetId = packetIdDetail.packetId
        except Exception as e:
            raise e
        return packetId


    def packets_labels_pdf(self, packetIds: list):
        labes = client.service.packetsLabelsPdf(self.api_key, packetIds, self.OFFSET, self.FORMAT)
        return labes

    #This returns Best Delivery Solution, should look more into the carriers
    def packet_courier_number(self, packetId):
        res = client.service.packetCourierNumberV2(self.api_key, packetId)
        return res


    def packet_courier_labels_pdf(self, packetIds: list):
        packets = []
        for id in packetIds:
            packet = {
                    "packetId": id,
                    "courierNumber": self.packet_courier_number(id)
                    }
            packets.append(packet)

        labels = client.service.packetsCourierLabelsPdf(self.api_key, packets, self.OFFSET,self.FORMAT)
        return labels 
