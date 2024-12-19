from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.models import User, Subject, Class

router = Router()

class SubjectCreation(StatesGroup):
    title = State()

class LessonCreation(StatesGroup):
    subject = State()
    class_id = State()
    title = State()
    description = State()
    days = State()  # Darsning kunlarini belgilash uchun

@router.message(F.text == "📚 Fan qo'shish")
async def cmd_add_subject(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    if not user or not user.is_teacher:
        await message.answer("⚠️ Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    await message.answer("📚 Fan nomini kiriting:")
    await state.set_state(SubjectCreation.title)

@router.message(SubjectCreation.title)
async def process_subject_title(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    subject = await Subject.create(
        title=message.text,
        teacher=user
    )
    
    await message.answer(
        f"✅ {subject.title} fani muvaffaqiyatli qo'shildi!"
    )
    await state.clear()

@router.message(F.text == "➕ Dars qo'shish")
async def cmd_add_lesson(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    if not user or not user.is_teacher:
        await message.answer("⚠️ Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    # O'qituvchining barcha fanlari
    subjects = await Subject.filter(teacher=user)
    if not subjects:
        await message.answer("⚠️ Avval fan qo'shing!")
        return
    
    # Fanlarni keyboard sifatida ko'rsatish
    keyboard = []
    for subject in subjects:
        keyboard.append([types.InlineKeyboardButton(
            text=f"📘 {subject.title}",
            callback_data=f"subject:{subject.id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("📚 Qaysi fan uchun dars qo'shmoqchisiz?", reply_markup=markup)

@router.callback_query(lambda c: c.data.startswith("subject:"))
async def process_subject_selection(callback: types.CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split(":")[1])
    subject = await Subject.get(id=subject_id)
    
    # O'qituvchining sinflari
    user = await User.get(user_id=callback.from_user.id)
    classes = await Class.filter(teacher=user)
    
    if not classes:
        await callback.message.answer("⚠️ Avval sinf yarating!")
        return
    
    # Sinflarni keyboard sifatida ko'rsatish
    keyboard = []
    for class_obj in classes:
        keyboard.append([types.InlineKeyboardButton(
            text=f"🏫 {class_obj.name}",
            callback_data=f"class:{class_obj.id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await state.update_data(subject_id=subject_id)
    await callback.message.edit_text("🏫 Qaysi sinf uchun dars qo'shmoqchisiz?", reply_markup=markup)

@router.callback_query(lambda c: c.data.startswith("class:"))
async def process_class_selection(callback: types.CallbackQuery, state: FSMContext):
    class_id = int(callback.data.split(":")[1])
    
    # Oldingi ma'lumotlarni olish
    data = await state.get_data()
    subject_id = data.get('subject_id')
    
    await state.update_data(class_id=class_id)
    await callback.message.edit_text("📝 Dars nomini kiriting:")
    await state.set_state(LessonCreation.title)

@router.message(LessonCreation.title)
async def process_lesson_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📝 Dars tavsifini kiriting:")
    await state.set_state(LessonCreation.description)

@router.message(LessonCreation.description)
async def process_lesson_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    
    # Kunlarni tanlash uchun keyboard
    keyboard = [
        [types.InlineKeyboardButton(text="Dushanba", callback_data="day:monday")],
        [types.InlineKeyboardButton(text="Seshanba", callback_data="day:tuesday")],
        [types.InlineKeyboardButton(text="Chorshanba", callback_data="day:wednesday")],
        [types.InlineKeyboardButton(text="Payshanba", callback_data="day:thursday")],
        [types.InlineKeyboardButton(text="Juma", callback_data="day:friday")],
        [types.InlineKeyboardButton(text="Shanba", callback_data="day:saturday")],
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer("📅 Dars qaysi kunlari bo'ladi?", reply_markup=markup)
    await state.set_state(LessonCreation.days)

@router.callback_query(lambda c: c.data.startswith("day:"))
async def process_lesson_days(callback: types.CallbackQuery, state: FSMContext):
    day = callback.data.split(":")[1]
    
    # Oldingi ma'lumotlarni olish
    data = await state.get_data()
    subject_id = data.get('subject_id')
    class_id = data.get('class_id')
    title = data.get('title')
    description = data.get('description')
    
    # O'qituvchini olish
    user = await User.get(user_id=callback.from_user.id)
    
    # Darsni yaratish
    lesson = await Lesson.create(
        title=title,
        description=description,
        class_id=class_id,
        subject=subject_id,
        teacher=user,  # O'qituvchini qo'shamiz
        days=day
    )
    
    await callback.message.edit_text(
        f"✅ {lesson.title} darsi muvaffaqiyatli qo'shildi!\n"
        f"📅 Kunlari: {day}"
    )
    await state.clear()