from dotenv import load_dotenv
import os
from typing import Optional, List

# Загрузка переменных окружения из .env файла
load_dotenv()

TG_TOKEN: Optional[str] = os.environ.get("TG_TOKEN")
SHOP_ID: Optional[str] = os.environ.get("SHOP_ID")
SECRET_KEY: Optional[str] = os.environ.get("SECRET_KEY")
CRYPTO_PAY_API_KEY: Optional[str] = os.environ.get("CRYPTO_PAY_API_KEY")
CRYPTO_PAY_API_URL: Optional[str] = os.environ.get("CRYPTO_PAY_API_URL")
ADMIN_IDS: List[int] = [int(x) for x in os.environ.get("ADMIN_IDS", "").split()]

