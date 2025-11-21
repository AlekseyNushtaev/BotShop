# handlers_yookassa.py - полная версия файла
import logging
import uuid

from aiogram import Router, F
from aiogram.types import CallbackQuery
from yookassa import Payment

from bot import bot
from db.models import Session, PaymentModel, Product
from keyboard import create_kb

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("yookassa_"))
async def process_yookassa(callback: CallbackQuery):
    product_id = int(callback.data.split('_')[1])

    async with Session() as session:
        # Получаем информацию о товаре
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("❌ Товар не найден", show_alert=True)
            return

        payment_uuid = str(uuid.uuid4())

        # Создаем платеж в YooKassa
        bot_info = await bot.get_me()
        username = bot_info.username
        bot_link = f"https://t.me/{username}"

        yookassa_payment = Payment.create({
            "amount": {
                "value": f"{product.price / 100:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": bot_link
            },
            "capture": True,
            "metadata": {
                "user_id": callback.from_user.id,
                "product_id": product_id
            },
            "description": product.name
        }, payment_uuid)
        payment_record = PaymentModel(
            id=yookassa_payment.id,
            user_id=callback.from_user.id,
            product_id=product_id,
            amount=product.price,
            status="pending"
        )
        session.add(payment_record)
        await session.commit()
        payment_keyboard = create_kb(
            1,
            **{
                f"check_yookassa___{yookassa_payment.id}": "🔄 Проверить оплату",
                f"buy_{product_id}": "◀️ Назад"
            }
        )

        await callback.message.edit_text(
            f'''💳 Платеж создан

💰 Сумма: {product.price // 100} руб
🆔 ID платежа: {yookassa_payment.id}
📝 Назначение: {product.name}

👇 Для оплаты перейдите по ссылке:
{yookassa_payment.confirmation.confirmation_url}

⚠️ Внимание: 
• После оплаты нажмите кнопку "🔄 Проверить оплату"
• После подтверждения оплаты заявка будет отправлена разработчику, Вам будут предоставлены контакты разработчика''',
            reply_markup=payment_keyboard
        )


@router.callback_query(F.data.startswith("check_yookassa___"))
async def check_yookassa(callback: CallbackQuery):
    payment_id = callback.data.split('___')[1]
    print(payment_id)

    async with Session() as session:
        # Обновляем статус платежа в базе
        payment = await session.get(PaymentModel, payment_id)
        if not payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        # Проверяем статус в YooKassa
        yookassa_payment = Payment.find_one(payment_id)

        if yookassa_payment.status == 'succeeded':
            # Обновляем статус в базе
            payment.status = 'succeeded'
            await session.commit()

            # Получаем информацию о товаре
            product = await session.get(Product, payment.product_id)

            await callback.message.edit_text(
                f'''✅ Платеж прошел успешно!

📦 Товар: {product.name}
💰 Сумма: {product.price // 100} руб

👨‍💻 Контакты разработчика: @AltiBalti, в ближайшее время он с Вами свяжется для уточнения деталей''',
                reply_markup=create_kb(1, view_products='В главное меню')
            )

            # Уведомляем администратора
            await bot.send_message(
                1012882762,
                f"🛒 Новый заказ!\n"
                f"👤 Пользователь: {callback.from_user.id}\n"
                f"📦 Товар: {product.name}\n"
                f"💰 Сумма: {product.price // 100} руб"
            )

        elif yookassa_payment.status == 'canceled':
            payment.status = 'canceled'
            await session.commit()
            await callback.answer('❌ Платеж отменен', show_alert=True)
        else:
            await callback.answer('⏳ Оплата еще не прошла или возникла ошибка', show_alert=True)
