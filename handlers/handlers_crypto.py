import logging
import uuid

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiocryptopay import AioCryptoPay, Networks

from bot import bot
from config import CRYPTO_PAY_API_KEY
from db.models import Session, Product, CryptoModel
from keyboard import create_kb

logger = logging.getLogger(__name__)
router = Router()

# Инициализация Crypto Pay
crypto = AioCryptoPay(CRYPTO_PAY_API_KEY, network=Networks.MAIN_NET)


@router.callback_query(F.data.startswith("cryptobot_"))
async def process_cryptobot(callback: CallbackQuery):
    product_id = int(callback.data.split('_')[1])
    try:
        asset = "USDT"
        bot_info = await bot.get_me()
        username = bot_info.username
        bot_link = f"https://t.me/{username}"

        async with Session() as session:
            # Получаем информацию о товаре
            product = await session.get(Product, product_id)
            if not product:
                await callback.answer("❌ Товар не найден", show_alert=True)
                return

            # Конвертируем цену в криптовалюту
            crypto_amount = float(f"{product.price / 8500:.2f}")

            # Создаем счет в Crypto Pay
            invoice = await crypto.create_invoice(
                asset=asset,
                amount=crypto_amount,
                description="Покупка в боте услуги",
                hidden_message="Спасибо за оплату!",
                paid_btn_name="openBot",
                paid_btn_url=bot_link,
                payload=str(uuid.uuid4()),
                expires_in=900
            )

            # Сохраняем запись в базе данных
            crypto_payment = CryptoModel(
                id=invoice.invoice_id,
                user_id=callback.from_user.id,
                product_id=product_id,
                amount=crypto_amount,
                status="active"
            )
            session.add(crypto_payment)
            await session.commit()

            # Создаем клавиатуру с кнопками проверки и возврата
            payment_keyboard = create_kb(
                1,
                **{
                    f"check_crypto___{invoice.invoice_id}": "🔄 Проверить оплату",
                    f"buy_{product_id}": "◀️ Назад"
                }
            )

            await callback.message.edit_text(
                f"💳 Для пополнения баланса:\n"
                f"1. Переведите {crypto_amount} {asset}\n"
                f"2. [Оплатить]({invoice.bot_invoice_url})\n"
                f"⌛ Счет действителен 15 минут\n\n"
                f"⚠️ Внимание:\n"
                f"• После оплаты нажмите кнопку \"🔄 Проверить оплату\"\n"
                f"• После подтверждения оплаты заявка будет отправлена разработчику, "
                f"Вам будут предоставлены контакты разработчика",
                parse_mode="Markdown",
                reply_markup=payment_keyboard
            )

    except Exception as e:
        logging.error(f"Ошибка создания счета: {e}")
        await callback.message.answer("❌ Не удалось создать счет")


@router.callback_query(F.data.startswith("check_crypto___"))
async def check_crypto_payment(callback: CallbackQuery):
    payment_id = callback.data.split('___')[1]

    async with Session() as session:
        # Находим платеж в базе
        crypto_payment = await session.get(CryptoModel, payment_id)
        if not crypto_payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return

        # Проверяем статус в Crypto Pay
        try:
            invoices = await crypto.get_invoices(invoice_ids=payment_id)
            if not invoices:
                await callback.answer("❌ Платеж не найден в системе", show_alert=True)
                return

            invoice = invoices[0]

            if invoice.status == 'paid':
                # Обновляем статус платежа
                crypto_payment.status = "paid"

                # Получаем информацию о товаре
                product = await session.get(Product, crypto_payment.product_id)

                await session.commit()

                # Уведомляем пользователя
                await callback.message.edit_text(
                    f'''✅ Платеж прошел успешно!

📦 Товар: {product.name}
💰 Сумма: {crypto_payment.amount} USDT

👨‍💻 Контакты разработчика: @AltiBalti, в ближайшее время он с Вами свяжется для уточнения деталей''',
                    reply_markup=create_kb(1, view_products='В главное меню')
                )

                # Уведомляем администратора
                admin_message = (
                    f"🛒 Новый заказ через Crypto Pay!\n"
                    f"👤 Пользователь: {callback.from_user.username} (ID: {callback.from_user.id})\n"
                    f"📦 Товар: {product.name}\n"
                    f"💰 Сумма: {crypto_payment.amount} USDT\n"
                    f"🆔 ID платежа: {payment_id}"
                )
                await bot.send_message(1012882762, admin_message)

            elif invoice.status in ['expired', 'failed']:
                crypto_payment.status = invoice.status
                await session.commit()
                await callback.answer('❌ Платеж отменен или просрочен', show_alert=True)

            else:
                await callback.answer('⏳ Оплата еще не прошла или возникла ошибка', show_alert=True)

        except Exception as e:
            logging.error(f"Ошибка проверки крипто-платежа: {e}")
            await callback.answer('❌ Ошибка при проверке платежа', show_alert=True)
