from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.models import User, Exam, Grade, Subject, Lesson
from app.handlers.user import get_teacher_keyboard, get_student_keyboard
from datetime import datetime
import logging

router = Router()

class ExamStates(StatesGroup):
    select_subject = State()
    waiting_for_title = State()
    waiting_for_student = State()
    waiting_for_grade = State()

def get_teacher_exam_keyboard():
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="📝 Yangi imtihon yaratish"),
                types.KeyboardButton(text="📊 Imtihon natijalari")
            ],
            [
                types.KeyboardButton(text="🔙 Orqaga")
            ]
        ],
        resize_keyboard=True
    )
    return markup

def get_student_exam_keyboard():
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="📊 Mening baholarim")
            ],
            [
                types.KeyboardButton(text="🔙 Orqaga")
            ]
        ],
        resize_keyboard=True
    )
    return markup

@router.message(F.text == "🔙 Orqaga")
async def back_to_main_menu(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    if user.is_teacher:
        markup = get_teacher_keyboard()
    else:
        markup = get_student_keyboard()
    await message.answer("🏠 Asosiy menyu:", reply_markup=markup)

@router.message(F.text == "📚 Imtihonlar")
async def show_exam_menu(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    
    if user.is_teacher:
        markup = get_teacher_exam_keyboard()
        await message.answer("📚 Imtihon menyusi:", reply_markup=markup)
    else:
        markup = get_student_exam_keyboard()
        await message.answer("📚 Imtihon menyusi:", reply_markup=markup)

@router.message(F.text == "📝 Yangi imtihon yaratish")
async def create_exam(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_teacher:
        await message.answer("❌ Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    # Get teacher's subjects
    subjects = await Subject.filter(teacher=user)
    if not subjects:
        await message.answer(
            "❌ Siz hali birorta fan yaratmagansiz!\n"
            "Iltimos, avval fan yarating.",
            reply_markup=get_teacher_keyboard()
        )
        return
    
    # Create inline keyboard with subjects
    buttons = []
    for subject in subjects:
        buttons.append([
            types.InlineKeyboardButton(
                text=subject.title,
                callback_data=f"select_subject:{subject.id}"
            )
        ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "📚 Imtihon uchun fanni tanlang:",
        reply_markup=markup
    )
    await state.set_state(ExamStates.select_subject)

@router.callback_query(lambda c: c.data.startswith("select_subject:"))
async def process_subject_selection(callback: types.CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split(":")[1])
    
    await state.update_data(subject_id=subject_id)
    await callback.message.answer(
        "📝 Imtihon nomini kiriting:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(ExamStates.waiting_for_title)
    await callback.answer()

@router.message(ExamStates.waiting_for_title)
async def process_exam_title(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    data = await state.get_data()
    subject = await Subject.get(id=data['subject_id'])
    
    exam = await Exam.create(
        title=message.text,
        subject=subject,
        teacher=user
    )
    await state.update_data(exam_id=exam.id)
    
    # Get all students
    students = await User.filter(is_student=True)
    if not students:
        await message.answer(
            "❌ Hozircha o'quvchilar yo'q!",
            reply_markup=get_teacher_exam_keyboard()
        )
        await state.clear()
        return
    
    # Create inline keyboard with students
    buttons = []
    for student in students:
        buttons.append([
            types.InlineKeyboardButton(
                text=student.full_name,
                callback_data=f"grade_student:{student.user_id}:{exam.id}"
            )
        ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "👨‍🎓 O'quvchini tanlang:",
        reply_markup=markup
    )

@router.callback_query(lambda c: c.data.startswith("grade_student:"))
async def select_student_for_grade(callback: types.CallbackQuery, state: FSMContext):
    _, student_id, exam_id = callback.data.split(":")
    
    await state.update_data(student_id=int(student_id), exam_id=int(exam_id))
    await callback.message.answer(
        "📝 O'quvchi uchun bahoni kiriting (0-100):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(ExamStates.waiting_for_grade)
    await callback.answer()

@router.message(ExamStates.waiting_for_grade)
async def process_grade(message: types.Message, state: FSMContext):
    try:
        score = int(message.text)
        if not 0 <= score <= 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri baho! Iltimos, 0 dan 100 gacha son kiriting.")
        return
    
    data = await state.get_data()
    exam = await Exam.get(id=data['exam_id'])
    student = await User.get(user_id=data['student_id'])

    # Save grade
    await Grade.create(
        student=student,
        exam=exam,
        score=score
    )
    
    await message.answer(f"✅ {student.full_name} uchun {score} baho qo'yildi!")
    await state.clear()

@router.message(F.text == "📊 Imtihon natijalari")
async def show_exam_results(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_teacher:
        await message.answer("❌ Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    subjects = await Subject.filter(teacher=user).prefetch_related('exams')
    if not subjects:
        await message.answer("❌ Siz hali birorta fan yaratmagansiz!")
        return
    
    for subject in subjects:
        exams = await Exam.filter(subject=subject).prefetch_related('grades', 'grades__student')
        if not exams:
            continue
        
        subject_text = f"📚 Fan: {subject.title}\n\n"
        
        for exam in exams:
            grades = exam.grades
            if not grades:
                result_text = "❌ Hali baholar qo'yilmagan"
            else:
                result_text = "\n".join([
                    f"👤 {grade.student.full_name}: {grade.score}"
                    for grade in grades
                ])
            
            subject_text += (
                f"📝 Imtihon: {exam.title}\n"
                f"📅 Sana: {exam.created_at.strftime('%d.%m.%Y')}\n"
                f"{result_text}\n\n"
            )
        
        await message.answer(subject_text)

@router.message(F.text == "📊 Mening baholarim")
async def show_student_grades(message: types.Message):
    try:
        user = await User.get(user_id=message.from_user.id)
        
        if not user or not user.is_student:
            await message.answer("❌ Bu funksiya faqat o'quvchilar uchun!")
            return
        
        # Get all grades for the student
        grades = await Grade.filter(student=user).prefetch_related('exam', 'lesson')
        
        if not grades:
            await message.answer("📚 Sizda hali baholangan imtihonlar mavjud emas.")
            return
        
        # Format the grades message
        grades_message = "📊 Sizning baholaringiz:\n\n"
        
        # Separate exam grades and lesson grades
        exam_grades = [g for g in grades if g.exam]
        lesson_grades = [g for g in grades if g.lesson]
        
        if exam_grades:
            grades_message += "📝 Imtihon baholari:\n"
            for grade in exam_grades:
                grades_message += f"• {grade.exam.title}: {grade.score}/100\n"
            grades_message += "\n"
            
        if lesson_grades:
            grades_message += "📚 Dars baholari:\n"
            for grade in lesson_grades:
                grades_message += f"• {grade.lesson.title}: {grade.score}/5\n"
        
        await message.answer(grades_message)
        
    except Exception as e:
        print(f"Error in show_student_grades: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

@router.callback_query(F.data.startswith("grade:"))
async def process_grade(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, student_id, subject_id, grade = callback.data.split(":")
        student = await User.get(id=int(student_id))
        subject = await Subject.get(id=int(subject_id))
        
        current_date = datetime.now()
        
        # Bahoni saqlash
        await Grade.create(
            student=student,
            subject=subject,
            value=int(grade),
            month=current_date.month,
            year=current_date.year
        )
        
        # Baho qo'yilgani haqida xabar
        await callback.answer(
            f"✅ {student.full_name}ga {grade} baho qo'yildi",
            show_alert=True
        )
        
        # O'quvchiga xabar yuborish
        await callback.bot.send_message(
            student.telegram_id,
            f"📝 Sizga {subject.title} fanidan {grade} baho qo'yildi"
        )
        
        # Baholar ro'yxatini yangilash
        grades = await Grade.filter(
            student=student,
            subject=subject,
            month=current_date.month,
            year=current_date.year
        )
        
        text = f"{student.full_name}ning {subject.title} fani bo'yicha baholari:\n\n"
        month_name = {
            1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
            5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
            9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
        }[current_date.month]
        
        text += f"📅 {month_name} oyi:\n"
        text += ", ".join(str(g.value) for g in grades)
        if grades:
            avg = sum(g.value for g in grades) / len(grades)
            text += f"\n📊 O'rtacha: {avg:.1f}"
            
        markup = await get_grade_markup(student.id, subject.id)
        await callback.message.edit_text(text, reply_markup=markup)
        
    except Exception as e:
        logging.error(f"Error in process_grade: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

async def get_grade_markup(student_id: int, subject_id: int):
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    for grade in range(1, 6):
        buttons.append(
            types.InlineKeyboardButton(
                text=str(grade),
                callback_data=f"grade:{student_id}:{subject_id}:{grade}"
            )
        )
    markup.add(*buttons)
    return markup