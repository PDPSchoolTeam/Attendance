from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.models import User, Class
from app.keyboards import get_class_list_keyboard

router = Router()

class ClassState(StatesGroup):
    name = State()
    select_class = State()

@router.message(F.text == "➕ Sinf qo'shish")
async def add_class(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    if not user or not user.is_teacher:
        await message.answer("Sizda bu amalni bajarish uchun huquq yo'q!")
        return

    await state.set_state(ClassState.name)
    await message.answer("Yangi sinf nomini kiriting:")

@router.message(ClassState.name)
async def process_class_name(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user:
        await message.answer("Foydalanuvchi topilmadi!")
        return

    class_obj = await Class.create(
        name=message.text,
        teacher=user
    )

    await state.clear()
    await message.answer(f"Yangi sinf '{class_obj.name}' muvaffaqiyatli qo'shildi!")

@router.message(F.text == "📋 Sinflar ro'yxati")
async def list_classes(message: types.Message):
    user = await User.get_or_none(user_id=message.from_user.id)
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz!")
        return

    if user.is_teacher:
        classes = await Class.filter(teacher=user)
        if not classes:
            await message.answer("Siz hali sinf qo'shmagansiz!")
            return
    else:
        classes = await user.enrolled_classes.all()
        if not classes:
            await message.answer("Siz hali birorta sinfga a'zo emassiz!")
            return

    text = "Sinflar ro'yxati:\n\n"
    for class_obj in classes:
        student_count = await class_obj.students.all().count()
        text += f"📚 {class_obj.name} - {student_count} ta o'quvchi\n"

    await message.answer(text)

@router.message(F.text == "🏫 Sinfga a'zo bo'lish")
async def select_class_for_student(message: types.Message, state: FSMContext):
    classes = await Class.all()
    if not classes:
        await message.answer("Hozircha sinflar mavjud emas!")
        return

    await state.set_state(ClassState.select_class)
    keyboard = []
    for class_obj in classes:
        keyboard.append([types.InlineKeyboardButton(
            text=f"🏫 {class_obj.name}",
            callback_data=f"join_class_{class_obj.id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("O'zingizning sinfingizni tanlang:", reply_markup=markup)

@router.callback_query(F.data.startswith("join_class_"))
async def process_class_selection(callback: types.CallbackQuery, state: FSMContext):
    class_id = int(callback.data.split('_')[2])
    user = await User.get_or_none(user_id=callback.from_user.id)
    class_obj = await Class.get(id=class_id)

    if not user:
        await callback.message.answer("Foydalanuvchi topilmadi!")
        return

    if user.is_student:
        await class_obj.students.add(user)
        await state.clear()
        await callback.message.answer(f"Siz '{class_obj.name}' sinfiga muvaffaqiyatli a'zo bo'ldingiz!")
    else:
        await callback.message.answer("Faqat o'quvchilar sinfga a'zo bo'lishi mumkin!")

    await callback.answer()
