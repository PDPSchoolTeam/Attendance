from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from app.models.user import User

class UserState(StatesGroup):
    role = State()
    full_name = State()
    select_class = State()

async def cmd_start(message: types.Message):
    await message.reply(
        "Assalomu alaykum! Botdan foydalanish uchun ro'yxatdan o'ting.\n"
        "Siz kimsiz?",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="O'qituvchi"),
                    types.KeyboardButton(text="O'quvchi")
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await UserState.role.set()

async def process_role(message: types.Message, state: FSMContext):
    role = message.text.lower()
    if role not in ["o'qituvchi", "o'quvchi"]:
        await message.reply("Iltimos, to'g'ri tanlovni amalga oshiring")
        return

    await state.update_data(is_teacher=(role == "o'qituvchi"))
    await message.reply("Iltimos, to'liq ismingizni kiriting")
    await UserState.full_name.set()

async def process_full_name(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    is_teacher = user_data.get('is_teacher', False)
    
    # Create user in database
    await User.create(
        user_id=message.from_user.id,
        full_name=message.text,
        is_teacher=is_teacher,
        is_student=not is_teacher
    )

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_teacher:
        keyboard.add(types.KeyboardButton("Sinf qo'shish"))
        keyboard.add(types.KeyboardButton("Davomat olish"))
        keyboard.add(types.KeyboardButton("Davomat jurnali"))
        await message.reply("Siz o'qituvchi sifatida ro'yxatdan o'tdingiz!", reply_markup=keyboard)
    else:
        keyboard.add(types.KeyboardButton("Mening davomatim"))
        await message.reply(
            "Siz o'quvchi sifatida ro'yxatdan o'tdingiz!\n"
            "Endi o'z sinfingizni tanlang.",
            reply_markup=keyboard
        )
        await UserState.select_class.set()

    await state.finish()

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'])
    dp.register_message_handler(process_role, state=UserState.role)
    dp.register_message_handler(process_full_name, state=UserState.full_name)
