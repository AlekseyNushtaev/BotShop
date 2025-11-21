import logging
import uuid

from aiogram import Router, F
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot
from db.models import Session, StarsModel, Product
from keyboard import create_kb

logger = logging.getLogger(__name__)
router = Router()


def payment_keyboard(value):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {value} ⭐️", pay=True)
    return builder.as_markup()


@router.callback_query(F.data.startswith("stars_"))
async def process_stars(callback: CallbackQuery):
    product_id = callback.data.split('_')[1]

    async with Session() as session:
        # Получаем информацию о товаре
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("❌ Товар не найден", show_alert=True)
            return

        # Создаем запись о платеже в базе
        stars_payment_id = str(uuid.uuid4())
        stars_payment = StarsModel(
            id=stars_payment_id,
            user_id=callback.from_user.id,
            product_id=product.id,
            amount=product.price // 200,  # сумма в звездах (предполагаем 1 звезда = 1 рубль)
            status="pending"
        )
        session.add(stars_payment)
        await session.commit()

    # Формируем цены для платежа
    prices = [LabeledPrice(label=product.name, amount=product.price // 200)]  # сумма в звездах

    await bot.send_invoice(
        callback.from_user.id,
        title=product.name,
        description=f'''
🆔 ID платежа: {stars_payment_id}        

После подтверждения оплаты заявка будет отправлена разработчику, Вам будут предоставлены контакты разработчика
        ''',
        prices=prices,
        provider_token="",  # Для Stars provider_token не требуется
        payload=stars_payment_id,  # Используем наш ID платежа как payload
        currency="XTR",  # Валюта для Telegram Stars
        reply_markup=payment_keyboard(product.price // 200),
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    # Проверяем наличие платежа в базе
    async with Session() as session:
        payment = await session.get(StarsModel, pre_checkout_query.invoice_payload)
        if not payment:
            await pre_checkout_query.answer(ok=False, error_message="Платеж не найден")
            return

        if payment.status != "pending":
            await pre_checkout_query.answer(ok=False, error_message="Платеж уже обработан")
            return

    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_payment_handler(msg: Message):
    payment_payload = msg.successful_payment.invoice_payload

    async with Session() as session:
        # Находим платеж в базе
        stars_payment = await session.get(StarsModel, payment_payload)
        if not stars_payment:
            logger.error(f"Платеж Stars не найден: {payment_payload}")
            await msg.answer("❌ Ошибка при обработке платежа")
            return

        # Обновляем статус платежа
        stars_payment.status = "succeeded"

        # Получаем информацию о товаре
        product = await session.get(Product, stars_payment.product_id)

        await session.commit()

    # Уведомляем пользователя
    await msg.answer(
        f'''✅ Платеж прошел успешно!

📦 Товар: {product.name}
💰 Сумма: {stars_payment.amount} ⭐️

👨‍💻 Контакты разработчика: @AltiBalti, в ближайшее время он с Вами свяжется для уточнения деталей''',
        reply_markup=create_kb(1, view_products='В главное меню')
    )

    # Уведомляем администратора
    admin_message = (
        f"🛒 Новый заказ через Stars!\n"
        f"👤 Пользователь: {msg.from_user.username} (ID: {msg.from_user.id})\n"
        f"📦 Товар: {product.name}\n"
        f"💰 Сумма: {stars_payment.amount} ⭐️\n"
        f"🆔 ID платежа: {payment_payload}"
    )
    await bot.send_message(1012882762, admin_message)
