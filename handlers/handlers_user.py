# handlers_user.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot
from db.models import Session, User, Product
from keyboard import create_kb

logger = logging.getLogger(__name__)
router = Router()

# Кэш для хранения текущих позиций пользователей
user_positions = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    # Регистрируем пользователя в БД
    async with Session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            session.add(user)
            await session.commit()
            logger.info(f"Зарегистрирован новый пользователь: {message.from_user.id}")

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍️ Просмотреть товары", callback_data="view_products")

    await message.answer(
        "🎉 Добро пожаловать в магазин Ботов для управления каналом! 🤖\n\n"
        "Здесь вы найдете лучшие решения для автоматизации "
        "и управления вашими Telegram-каналами! 💫",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "view_products")
async def view_products(callback: CallbackQuery):
    async with Session() as session:
        products = await session.execute(
            Product.__table__.select().where(Product.is_active == True)
        )
        products = products.fetchall()

    if not products:
        await callback.message.edit_text(
            "😔 В настоящий момент товаров нет в наличии.\n"
            "Пожалуйста, проверьте позже! 🔄"
        )
        return

    # Сохраняем позицию пользователя
    user_positions[callback.from_user.id] = 0
    await show_product(callback.from_user.id, callback.message, 0)


async def show_product(user_id: int, message: Message, product_index: int):
    async with Session() as session:
        products = await session.execute(
            Product.__table__.select().where(Product.is_active == True)
        )
        products = products.fetchall()

    if not products:
        await message.edit_text("😔 Товары временно недоступны")
        return

    product = products[product_index]

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить", callback_data=f"buy_{product.id}")

    # Добавляем кнопки навигации если товаров больше 1
    if len(products) > 1:
        builder.row()
        builder.button(text="◀️ Назад", callback_data="prev_product")
        builder.button(text="Вперед ▶️", callback_data="next_product")
        builder.adjust(1, 2)

    caption = (f"📦 {product.name}\n\n"
               f"📝 {product.description}\n\n"
               f"💰 Цена: {product.price // 100} руб. 💎")

    try:
        if message.photo:
            await message.edit_media(
                media=InputMediaPhoto(media=product.photo_file_id, caption=caption),
                reply_markup=builder.as_markup()
            )
        else:
            await message.answer_photo(
                product.photo_file_id,
                caption=caption,
                reply_markup=builder.as_markup()
            )
            await message.delete()
    except Exception as e:
        logger.error(f"Ошибка при отображении товара: {e}")
        # Если не удалось отправить фото, отправляем текстовое сообщение
        await message.answer(
            caption,
            reply_markup=builder.as_markup()
        )
        await message.delete()


@router.callback_query(F.data == "next_product")
async def next_product(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_position = user_positions.get(user_id, 0)

    async with Session() as session:
        products = await session.execute(
            Product.__table__.select().where(Product.is_active == True)
        )
        products = products.fetchall()

    if not products:
        await callback.answer("😔 Товаров нет", show_alert=True)
        return

    new_position = (current_position + 1) % len(products)
    user_positions[user_id] = new_position

    await show_product(user_id, callback.message, new_position)
    await callback.answer()


@router.callback_query(F.data == "prev_product")
async def prev_product(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_position = user_positions.get(user_id, 0)

    async with Session() as session:
        products = await session.execute(
            Product.__table__.select().where(Product.is_active == True)
        )
        products = products.fetchall()

    if not products:
        await callback.answer("😔 Товаров нет", show_alert=True)
        return

    new_position = (current_position - 1) % len(products)
    user_positions[user_id] = new_position

    await show_product(user_id, callback.message, new_position)
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_id = callback.data.split('_')[1]

    # Создаем клавиатуру с выбором способа оплаты
    payment_keyboard = create_kb(
        1,
        **{
            f"yookassa_{product_id}": "💳 YooKassa",
            f"stars_{product_id}": "⭐ Telegram Stars",
            f"cryptobot_{product_id}": "₿ Cryptobot",
            f"view_products": "◀️ Назад"
        }
    )

    await callback.message.answer(
        "Выберите способ оплаты 💫",
        reply_markup=payment_keyboard
    )


@router.callback_query(F.data.startswith("cryptobot_"))
async def process_cryptobot(callback: CallbackQuery):
    product_id = callback.data.split('_')[1]
    await callback.answer("Оплата через Cryptobot временно недоступна", show_alert=True)
