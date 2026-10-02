from flask import current_app

def get_eph_service():
    if current_app.config.get("EPH_ENABLED"):
        from .eph_service import EPHService
        return EPHService()
        
    from .fake_eph_service import FakeEPHService
    return FakeEPHService()

def get_packeta_service():
    if current_app.config.get("PACKETA_ENABLED"):
        from .packeta_service import PacketaService
        return PacketaService()

    from .fake_packeta_service import FakePacketaService
    return FakePacketaService()
