from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime

# Настройка асинхронного подключения к SQLite3
DB_URL = "sqlite+aiosqlite:///db/database.db"
engine = create_async_engine(DB_URL)  # Асинхронный движок SQLAlchemy
Session = async_sessionmaker(expire_on_commit=False, bind=engine)  # Фабрика сессий


class Base(DeclarativeBase, AsyncAttrs):
    pass


class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)  # цена в копейках/центах
    photo_file_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)


class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(String(255), primary_key=True)  # payment_id от YooKassa
    status = Column(String(20), nullable=False, default="pending")  # pending, canceled, succeeded
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # сумма в копейках
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связи
    user = relationship("User")
    product = relationship("Product")


class StarsModel(Base):
    __tablename__ = "stars_payments"

    id = Column(String(255), primary_key=True)  # invoice_payload от Telegram
    status = Column(String(20), nullable=False, default="pending")  # pending, canceled, succeeded
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # сумма в звездах
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связи
    user = relationship("User")
    product = relationship("Product")


class CryptoModel(Base):
    __tablename__ = "crypto_payments"

    id = Column(BigInteger, primary_key=True)
    status = Column(String(20), nullable=True, default="pending")
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связи
    user = relationship("User")
    product = relationship("Product")



async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)