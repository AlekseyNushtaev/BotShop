import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.models import Session, Product
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    photo = State()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для выполнения этой команды")
        return

    await message.answer(
        "🛍️ Давайте добавим новый товар!\n\n"
        "Введите название товара:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)


@router.message(StateFilter(AddProduct.name))
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📝 Введите описание товара:")
    await state.set_state(AddProduct.description)


@router.message(StateFilter(AddProduct.description))
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("💰 Введите цену товара (в рублях, только число):")
    await state.set_state(AddProduct.price)


@router.message(StateFilter(AddProduct.price))
async def process_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await message.answer("🖼️ Отправьте фото товара:")
        await state.set_state(AddProduct.photo)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную цену (целое число больше 0):")


@router.message(StateFilter(AddProduct.photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    data = await state.get_data()

    async with Session() as session:
        product = Product(
            name=data['name'],
            description=data['description'],
            price=data['price'] * 100,  # сохраняем в копейках
            photo_file_id=photo_file_id
        )
        session.add(product)
        await session.commit()

    await message.answer_photo(
        photo_file_id,
        caption=f"✅ Товар успешно добавлен!\n\n"
                f"📦 Название: {data['name']}\n"
                f"📝 Описание: {data['description']}\n"
                f"💰 Цена: {data['price']} руб."
    )
    await state.clear()


@router.message(StateFilter(AddProduct.photo))
async def process_photo_invalid(message: Message, state: FSMContext):
    await message.answer("❌ Пожалуйста, отправьте фото товара:")