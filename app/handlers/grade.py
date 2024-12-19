from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.models import User, Lesson, Grade, Class

router = Router()

class GradeState(StatesGroup):
    score = State()

@router.message(F.text == "📝 Baho Qo'yish")
async def cmd_add_grade(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    if not user or not user.is_teacher:
        await message.answer("⚠️ Faqat o'qituvchilar baho qo'ya oladi!")
        return
    
    # O'qituvchining darslarini olish
    lessons = await Lesson.filter(teacher=user)
    
    keyboard = []
    for lesson in lessons:
        keyboard.append([types.InlineKeyboardButton(
            text=f"📚 {lesson.title}",
            callback_data=f"select_lesson:{lesson.id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("📚 Qaysi dars uchun baho qo'ymoqchisiz?", reply_markup=markup)

@router.callback_query(lambda c: c.data.startswith("select_lesson:"))
async def process_lesson_selection(callback: types.CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split(":")[1])
    lesson = await Lesson.get(id=lesson_id)
    
    # Shu darsga tegishli sinfni olish
    class_obj = await lesson.class_id
    
    # Sinfga a'zo bo'lgan o'quvchilarni olish
    students = await class_obj.students.all()
    
    keyboard = []
    for student in students:
        keyboard.append([types.InlineKeyboardButton(
            text=f"👤 {student.full_name}",
            callback_data=f"select_student:{student.id}:{lesson_id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text("👥 Baho qo'yiladigan o'quvchini tanlang:", reply_markup=markup)

@router.callback_query(lambda c: c.data.startswith("select_student:"))
async def process_student_selection(callback: types.CallbackQuery, state: FSMContext):
    student_id, lesson_id = map(int, callback.data.split(":")[1:])
    
    student = await User.get(id=student_id)
    lesson = await Lesson.get(id=lesson_id)
    
    await state.update_data(student_id=student_id, lesson_id=lesson_id)
    await callback.message.edit_text(f"👤 {student.full_name} uchun baho kiriting (2-5 oralig'ida):")
    await state.set_state(GradeState.score)

@router.message(GradeState.score)
async def process_grade_input(message: types.Message, state: FSMContext):
    try:
        score = int(message.text)
        if score < 2 or score > 5:
            await message.answer("⚠️ Baho 2-5 oralig'ida bo'lishi kerak!")
            return
        
        data = await state.get_data()
        student_id = data.get('student_id')
        lesson_id = data.get('lesson_id')
        
        student = await User.get(id=student_id)
        lesson = await Lesson.get(id=lesson_id)
        
        # Baho yaratish
        grade = await Grade.create(
            student=student,
            lesson=lesson,
            score=score
        )
        
        await message.answer(
            f"✅ {student.full_name} uchun {lesson.title} darsidan {score} baho qo'yildi!"
        )
        await state.clear()
    
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat raqam kiriting (2-5 oralig'ida)!")
