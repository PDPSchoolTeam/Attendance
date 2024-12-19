from aiogram import types
from aiogram.dispatcher import FSMContext

from app.states import LessonState
from app.models.user import User
from app.models.lesson import Lesson

async def add_lesson(message: types.Message):
    user = await User.filter(user_id=message.from_user.id).first()
    if not user or not user.is_teacher:
        await message.answer("Sizda bu amalni bajarish uchun huquq yo'q!")
        return

    await LessonState.title.set()
    await message.answer("Dars nomini kiriting:")

async def process_lesson_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await LessonState.description.set()
    await message.answer("Dars haqida qisqacha ma'lumot kiriting:")

async def process_lesson_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = await User.filter(user_id=message.from_user.id).first()

    lesson = await Lesson.create(
        title=data['title'],
        description=message.text,
        teacher=user
    )

    await state.finish()
    await message.answer(
        f"Dars muvaffaqiyatli qo'shildi:\nNomi: {lesson.title}\nTavsif: {lesson.description}"
    )

async def list_lessons(message: types.Message):
    user = await User.filter(user_id=message.from_user.id).first()
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz!")
        return

    if user.is_teacher:
        lessons = await Lesson.filter(teacher=user)
        if not lessons:
            await message.answer("Siz hali dars qo'shmagansiz!")
            return
        
        text = "Sizning darslaringiz:\n\n"
        for lesson in lessons:
            text += f"📚 {lesson.title}\n📝 {lesson.description}\n\n"
    else:
        lessons = await Lesson.all()
        if not lessons:
            await message.answer("Hozircha darslar mavjud emas!")
            return
        
        text = "Mavjud darslar:\n\n"
        for lesson in lessons:
            teacher = await lesson.teacher
            text += f"📚 {lesson.title}\n👨‍🏫 O'qituvchi: {teacher.full_name}\n📝 {lesson.description}\n\n"
    
    await message.answer(text)
