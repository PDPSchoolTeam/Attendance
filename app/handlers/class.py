from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.models import User, Class

router = Router()

class ClassState(StatesGroup):
    name = State()

@router.message(F.text == "🏫 Sinf qo'shish")
async def add_class(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user or not user.is_teacher:
        await message.answer("⚠️ Faqat o'qituvchilar sinf qo'sha oladi!")
        return
    
    await message.answer("📝 Sinf nomini kiriting:")
    await state.set_state(ClassState.name)

@router.message(ClassState.name)
async def process_class_name(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    # Sinf nomini tekshirish
    if len(message.text) < 2:
        await message.answer("⚠️ Sinf nomi juda qisqa!")
        return
    
    # Sinf yaratish
    new_class = await Class.create(
        name=message.text,
        teacher=user
    )
    
    await message.answer(
        f"✅ {message.text} sinfi muvaffaqiyatli yaratildi!\n"
        f"👨‍🏫 O'qituvchi: {user.full_name}"
    )
    await state.clear()
