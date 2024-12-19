from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.models import User, Class

router = Router()

class ClassState(StatesGroup):
    name = State()
    select_class = State()

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
        teacher_id=user.id  # Use teacher_id instead of teacher
    )
    
    await message.answer(
        f"✅ {message.text} sinfi muvaffaqiyatli yaratildi!\n"
        f"👨‍🏫 O'qituvchi: {user.full_name}"
    )
    await state.clear()

@router.message(F.text == "🎓 Sinfga a'zo bo'lish")
async def select_class_for_student(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user or not user.is_student:
        await message.answer("⚠️ Faqat o'quvchilar sinfga a'zo bo'lishi mumkin!")
        return
    
    # Mavjud sinflarni olish
    classes = await Class.all().prefetch_related('teacher')
    
    if not classes:
        await message.answer("🚫 Hozircha sinflar mavjud emas!")
        return
    
    # Keyboard yaratish
    keyboard = []
    for class_obj in classes:
        # Explicitly fetch the teacher
        teacher = await User.get_or_none(id=class_obj.teacher_id)
        
        if teacher:
            keyboard.append([types.InlineKeyboardButton(
                text=f"🏫 {class_obj.name} (O'qituvchi: {teacher.full_name})",
                callback_data=f"join_class_{class_obj.id}"
            )])
    
    if not keyboard:
        await message.answer("🚫 Hozircha sinflar mavjud emas!")
        return
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await state.set_state(ClassState.select_class)
    await message.answer("🏫 Qaysi sinfga a'zo bo'lmoqchisiz?", reply_markup=markup)

@router.callback_query(F.data.startswith("join_class_"))
async def process_class_selection(callback: types.CallbackQuery, state: FSMContext):
    class_id = int(callback.data.split('_')[2])
    user = await User.get_or_none(user_id=callback.from_user.id)
    
    if not user or not user.is_student:
        await callback.message.answer("⚠️ Faqat o'quvchilar sinfga a'zo bo'lishi mumkin!")
        return
    
    try:
        class_obj = await Class.get(id=class_id)
        
        # Explicitly fetch the teacher
        teacher = await User.get_or_none(id=class_obj.teacher_id)
        
        if not teacher:
            await callback.message.answer("❌ Sinf uchun o'qituvchi topilmadi!")
            return
        
        # Tekshirish: foydalanuvchi allaqachon shu sinfga a'zo bo'lganmi
        existing_classes = await user.enrolled_classes.all()
        if class_obj in existing_classes:
            await callback.message.answer(f"❗ Siz allaqachon '{class_obj.name}' sinfiga a'zo bo'lgansiz!")
            return
        
        # Sinfga a'zo bo'lish
        await class_obj.students.add(user)
        
        await state.clear()
        await callback.message.answer(
            f"✅ Siz '{class_obj.name}' sinfiga muvaffaqiyatli a'zo bo'ldingiz!\n"
            f"👨‍🏫 O'qituvchi: {teacher.full_name}"
        )
    except Exception as e:
        await callback.message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")
        print(f"Class join error: {e}")
    
    await callback.answer()

@router.message(F.text == "📋 Mening sinflarim")
async def list_student_classes(message: types.Message):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user:
        await message.answer("⚠️ Foydalanuvchi topilmadi!")
        return
    
    if user.is_student:
        classes = await user.enrolled_classes.all()
        
        if not classes:
            await message.answer("🚫 Siz hech qanday sinfga a'zo emassiz!")
            return
        
        text = "🏫 Sizning sinflaringiz:\n\n"
        for class_obj in classes:
            # Explicitly fetch the teacher
            teacher = await User.get_or_none(id=class_obj.teacher_id)
            
            if teacher:
                text += f"• {class_obj.name} (O'qituvchi: {teacher.full_name})\n"
        
        await message.answer(text)
    else:
        await message.answer("⚠️ Ushbu funktsiya faqat o'quvchilar uchun!")
