import asyncio
import logging
from yookassa import Payment as YooPayment

from bot import bot
from db.models import Session, PaymentModel, Product, CryptoModel
from handlers.handlers_crypto import crypto
from keyboard import create_kb

logger = logging.getLogger(__name__)


async def check_pending_payments():
    """
    Периодическая проверка pending платежей
    """
    while True:
        print("Проверка")
        try:
            await check_yookassa_payments()
            await check_crypto_payments()
        except Exception as e:
            logger.error(f"Ошибка в check_pending_payments: {e}")

        # Ожидаем 5 минут перед следующей проверкой
        await asyncio.sleep(300)


async def check_yookassa_payments():
    """
    Периодическая проверка pending платежей
    """
    try:
        async with Session() as session:
            # Получаем все pending платежи
            pending_payments = await session.execute(
                PaymentModel.__table__.select().where(
                    PaymentModel.status == "pending"
                )
            )
            pending_payments = pending_payments.fetchall()

            for payment_record in pending_payments:
                try:
                    # Проверяем статус в YooKassa
                    yookassa_payment = YooPayment.find_one(payment_record.id)

                    if yookassa_payment.status == 'succeeded':
                        # Обновляем статус в базе
                        await session.execute(
                            PaymentModel.__table__.update()
                            .where(PaymentModel.id == payment_record.id)
                            .values(status='succeeded')
                        )
                        await session.commit()

                        # Получаем информацию о товаре
                        product = await session.get(Product, payment_record.product_id)
                        user_id = payment_record.user_id

                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                user_id,
                                f'''✅ Платеж прошел успешно!

📦 Товар: {product.name}
💰 Сумма: {product.price // 100} руб

👨‍💻 Контакты разработчика: @AltiBalti, в ближайшее время он с Вами свяжется для уточнения деталей''',
                                reply_markup=create_kb(1, view_products='В главное меню')
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

                        # Уведомляем администратора
                        try:
                            await bot.send_message(
                                1012882762,
                                f"🛒 Новый заказ!\n"
                                f"👤 Пользователь: {user_id}\n"
                                f"📦 Товар: {product.name}\n"
                                f"💰 Сумма: {product.price // 100} руб"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить сообщение администратору: {e}")

                    elif yookassa_payment.status == 'canceled':
                        # Обновляем статус в базе
                        await session.execute(
                            PaymentModel.__table__.update()
                            .where(PaymentModel.id == payment_record.id)
                            .values(status='canceled')
                        )
                        await session.commit()

                except Exception as e:
                    logger.error(f"Ошибка при проверке платежа юкасса {payment_record.id}: {e}")
                    continue


    except Exception as e:
        logger.error(f"Ошибка в check_pending_payments юкасса: {e}")


async def check_crypto_payments():
    """Проверка pending платежей Crypto Pay"""
    async with Session() as session:
        # Получаем все pending платежи Crypto Pay
        pending_crypto_payments = await session.execute(
            CryptoModel.__table__.select().where(
                CryptoModel.status == "active"
            )
        )
        pending_crypto_payments = pending_crypto_payments.fetchall()

        for crypto_payment in pending_crypto_payments:
            try:
                # Проверяем статус в Crypto Pay
                invoice = await crypto.get_invoices(invoice_ids=crypto_payment.id)
                print(invoice.invoice_id)
                print(invoice.status)

                if invoice.status == 'paid':
                    # Обновляем статус в базе
                    await session.execute(
                        CryptoModel.__table__.update()
                        .where(CryptoModel.id == crypto_payment.id)
                        .values(status='paid')
                    )
                    await session.commit()

                    # Получаем информацию о товаре
                    product = await session.get(Product, crypto_payment.product_id)
                    user_id = crypto_payment.user_id

                    # Уведомляем пользователя
                    try:
                        await bot.send_message(
                            user_id,
                            f'''✅ Платеж прошел успешно!

📦 Товар: {product.name}
💰 Сумма: {crypto_payment.amount} usdt

👨‍💻 Контакты разработчика: @AltiBalti, в ближайшее время он с Вами свяжется для уточнения деталей''',
                            reply_markup=create_kb(1, view_products='В главное меню')
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

                    # Уведомляем администратора
                    try:
                        await bot.send_message(
                            1012882762,
                            f"🛒 Новый заказ через Crypto Pay!\n"
                            f"👤 Пользователь: {user_id}\n"
                            f"📦 Товар: {product.name}\n"
                            f"💰 Сумма: {crypto_payment.amount} usdt\n"
                            f"🆔 ID платежа: {crypto_payment.id}"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение администратору: {e}")

                elif invoice.status in ['expired', 'failed']:
                    # Обновляем статус в базе
                    await session.execute(
                        CryptoModel.__table__.update()
                        .where(CryptoModel.id == crypto_payment.id)
                        .values(status='invoice.status')
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Ошибка при проверке крипто-платежа {crypto_payment.id}: {e}")
                continue


async def start_background_tasks():
    """
    Запуск фоновых задач
    """
    asyncio.create_task(check_pending_payments())