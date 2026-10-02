import os


APP_ENV = os.environ.get("FLASK_ENV", "development")

class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY") 
    R2_ENABLED = True
    EPH_ENABLED = True
    PACKETA_ENABLED = True
    CHROME_EXTENSION_ID = os.environ.get("CHROME_EXTENSION_ID")
    ALLOWED_ORIGINS = [
        "https://app.cardanvil.sk",
        f"chrome-extension://{os.environ['CHROME_EXTENSION_ID']}",
        "https://www.cardmarket.com",
    ]

class DevelopmentConfig(BaseConfig):
    R2_ENABLED = False
    EPH_ENABLED = False
    PACKETA_ENABLED = False


class StagingConfig(BaseConfig):
    R2_ENABLED = True
    R2_BUCKET_NAME = "tradetracker-staging"
    EPH_ENABLED = False
    PACKETA_ENABLED = False
    ALLOWED_ORIGINS = [
        "https://staging.app.cardanvil.sk",
        f"chrome-extension://{os.environ['CHROME_EXTENSION_ID']}",
        "https://www.cardmarket.com",
    ]

class ProductionConfig(BaseConfig):
    R2_ENABLED = True
    R2_BUCKET_NAME = "tradetracker"

config = {
        "development": DevelopmentConfig,
        "staging": StagingConfig,
        "prod": ProductionConfig
        }
