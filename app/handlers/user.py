from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from app.models import User, Class, Subject, Grade, Attendance
from app.keyboards import get_teacher_keyboard, get_student_keyboard, get_register_keyboard
import logging
import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Store pending teacher registrations
pending_teachers = {}

router = Router()
logger = logging.getLogger(__name__)

class UserStates(StatesGroup):
    waiting_for_role = State()
    waiting_for_full_name = State()
    waiting_approval = State()

class TeacherActions(StatesGroup):
    waiting_for_class_name = State()
    waiting_for_subject_name = State()
    waiting_for_grade = State()

class StudentActions(StatesGroup):
    waiting_for_class_selection = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await User.filter(user_id=message.from_user.id).first()
    if user:
        if user.is_teacher:
            await message.answer("Xush kelibsiz, o'qituvchi!", reply_markup=get_teacher_keyboard())
        else:
            await message.answer("Xush kelibsiz, o'quvchi!", reply_markup=get_student_keyboard())
    else:
        await message.answer(
            "Botga xush kelibsiz! Iltimos, rolingizni tanlang:",
            reply_markup=get_register_keyboard()
        )
        await state.set_state(UserStates.waiting_for_role)

@router.message(UserStates.waiting_for_role)
async def process_role_selection(message: types.Message, state: FSMContext):
    if message.text not in ["👨‍🎓 O'quvchi", "👨‍🏫 O'qituvchi"]:
        await message.answer("Iltimos, tugmalardan birini tanlang")
        return

    await state.update_data(role=message.text)
    await message.answer("To'liq ismingizni kiriting:")
    await state.set_state(UserStates.waiting_for_full_name)

@router.message(UserStates.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    role = user_data.get("role")
    
    if role == "👨‍🏫 O'qituvchi":
        # Store pending teacher registration
        pending_teachers[str(message.from_user.id)] = message.text
        
        # Notify admin
        admin_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve:{message.from_user.id}"),
                    types.InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{message.from_user.id}")
                ]
            ]
        )
        
        await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"👨‍🏫 Yangi o'qituvchi so'rovi:\n"
                f"👤 Ism: {message.text}\n"
                f"🆔 ID: {message.from_user.id}"
            ),
            reply_markup=admin_markup
        )
        
        await message.answer(
            "👨‍🏫 O'qituvchi so'rovingiz adminga yuborildi.\n"
            "⏳ Iltimos, tasdiqlashini kuting...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(UserStates.waiting_approval)
    else:
        # Register student immediately
        user = await User.create(
            user_id=message.from_user.id,
            full_name=message.text,
            is_teacher=False,
            is_student=True
        )
        
        await message.answer(
            f"Siz o'quvchi sifatida ro'yxatdan o'tdingiz!",
            reply_markup=get_student_keyboard()
        )
        await state.clear()

@router.callback_query(lambda c: c.data.startswith(('approve:', 'reject:')))
async def process_teacher_approval(callback: types.CallbackQuery):
    action, user_id = callback.data.split(":")
    user_id = int(user_id)
    
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Siz admin emassiz!")
        return
    
    full_name = pending_teachers.get(str(user_id))
    if not full_name:
        await callback.answer("⚠️ Foydalanuvchi ma'lumotlari topilmadi!")
        return
    
    if action == "approve":
        # Approve teacher registration
        user = await User.create(
            user_id=user_id,
            full_name=full_name,
            is_teacher=True,
            is_student=False
        )
        
        await callback.bot.send_message(
            chat_id=user_id,
            text="✅ Sizning o'qituvchilik so'rovingiz tasdiqlandi!"
        )
        await callback.message.edit_text(
            f"✅ O'qituvchi {user.full_name} tasdiqlandi!"
        )
    else:
        # Reject teacher registration
        await callback.bot.send_message(
            chat_id=user_id,
            text="❌ Kechirasiz, sizning o'qituvchilik so'rovingiz rad etildi."
        )
        await callback.message.edit_text(
            f"❌ O'qituvchi so'rovi rad etildi."
        )
    
    pending_teachers.pop(str(user_id), None)

# O'qituvchi uchun fan qo'shish
@router.message(F.text == "➕ Fan qo'shish")
async def add_subject_handler(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_teacher:
        await message.answer("Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    await message.answer("Fan nomini kiriting:")
    await state.set_state(TeacherActions.waiting_for_subject_name)

@router.message(TeacherActions.waiting_for_subject_name)
async def process_subject_name(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    
    subject = await Subject.create(
        title=message.text,
        teacher=user
    )
    
    await message.answer(f"{subject.title} fani muvaffaqiyatli qo'shildi!", reply_markup=get_teacher_keyboard())
    await state.clear()

# O'qituvchi uchun sinf qo'shish
@router.message(F.text == "➕ Sinf qo'shish")
async def add_class_handler(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_teacher:
        await message.answer("Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    await message.answer("Sinf nomini kiriting:")
    await state.set_state(TeacherActions.waiting_for_class_name)

@router.message(TeacherActions.waiting_for_class_name)
async def process_class_name(message: types.Message, state: FSMContext):
    user = await User.get(user_id=message.from_user.id)
    
    # Check if a class with the same name already exists
    existing_class = await Class.filter(name=message.text, teacher=user).first()
    if existing_class:
        await message.answer(f"Sinf '{message.text}' allaqachon mavjud!")
        return
    
    class_obj = await Class.create(
        name=message.text,
        teacher=user
    )
    
    await message.answer(f"{class_obj.name} sinfi muvaffaqiyatli qo'shildi!", reply_markup=get_teacher_keyboard())
    await state.clear()

# O'quvchi uchun sinfga a'zo bo'lish
@router.message(F.text == "🏫 Sinfga a'zo bo'lish")
async def join_class_handler(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_student:
        await message.answer("Bu funksiya faqat o'quvchilar uchun!")
        return
    
    classes = await Class.all()
    if not classes:
        await message.answer("Hozircha sinflar mavjud emas")
        return
    
    buttons = []
    for class_obj in classes:
        buttons.append([
            types.InlineKeyboardButton(
                text=class_obj.name,
                callback_data=f"join_class_{class_obj.id}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Qaysi sinfga a'zo bo'lmoqchisiz?", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('join_class_'))
async def process_join_class(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[2])
    user = await User.get(user_id=callback.from_user.id)
    class_obj = await Class.get(id=class_id)
    
    # Add student to class
    await class_obj.students.add(user)
    
    await callback.message.edit_text(
        f"Siz {class_obj.name} sinfiga muvaffaqiyatli a'zo bo'ldingiz!",
        reply_markup=None
    )

# Natijalarni ko'rish
@router.message(F.text == "📊 Natijalar")
async def show_results(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    
    if user.is_teacher:
        # O'qituvchi uchun sinflarni ko'rsatish
        classes = await Class.filter(teacher=user)
        if not classes:
            await message.answer("Siz hali sinf qo'shmagansiz")
            return
            
        buttons = []
        for class_obj in classes:
            buttons.append([
                types.InlineKeyboardButton(
                    text=class_obj.name,
                    callback_data=f"class_results_{class_obj.id}"
                )
            ])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Qaysi sinfning natijalarini ko'rmoqchisiz?", reply_markup=keyboard)
    else:
        # O'quvchi uchun o'zining natijalarini ko'rsatish
        grades = await Grade.filter(student=user).prefetch_related('subject')
        if not grades:
            await message.answer("Sizda hali baholar yo'q")
            return
            
        text = "📊 Sizning baholaringiz:\n\n"
        subjects_grades = {}
        
        for grade in grades:
            if grade.subject.title not in subjects_grades:
                subjects_grades[grade.subject.title] = []
            subjects_grades[grade.subject.title].append(grade.value)
        
        for subject, values in subjects_grades.items():
            average = sum(values) / len(values)
            text += f"📚 {subject}:\n"
            text += f"Baholar: {', '.join(map(str, values))}\n"
            text += f"O'rtacha: {average:.1f}\n\n"
        
        await message.answer(text)

@router.callback_query(lambda c: c.data.startswith('class_results_'))
async def process_class_results(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[2])
    class_obj = await Class.get(id=class_id).prefetch_related('students')
    
    if not class_obj.students:
        await callback.message.edit_text("Bu sinfda hali o'quvchilar yo'q")
        return
        
    text = f"📊 {class_obj.name} sinfi natijalari:\n\n"
    
    for student in await class_obj.students.all():
        grades = await Grade.filter(student=student).prefetch_related('subject')
        if grades:
            text += f"👤 {student.full_name}:\n"
            subjects_grades = {}
            
            for grade in grades:
                if grade.subject.title not in subjects_grades:
                    subjects_grades[grade.subject.title] = []
                subjects_grades[grade.subject.title].append(grade.value)
            
            for subject, values in subjects_grades.items():
                average = sum(values) / len(values)
                text += f"  📚 {subject}: {average:.1f}\n"
            text += "\n"
    
    await callback.message.edit_text(text)

# Davomat
@router.message(F.text == "✅ Davomat")
async def show_attendance(message: types.Message):
    try:
        logger.info(f"Showing attendance for user {message.from_user.id}")
        user = await User.get(user_id=message.from_user.id)
        
        if not user.is_teacher:
            # O'quvchi uchun o'zining davomati
            from datetime import datetime
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_month = today.replace(day=1)
            
            attendances = await Attendance.filter(
                user=user,
                date__gte=start_of_month
            ).prefetch_related('class_id')
            
            if not attendances:
                await message.answer("Bu oy uchun davomat ma'lumotlari yo'q")
                return
                
            text = f"📅 {today.strftime('%B %Y')} oyi davomati:\n\n"
            present_count = sum(1 for a in attendances if a.is_present)
            absent_count = len(attendances) - present_count
            
            text += f"✅ Kelgan kunlar: {present_count}\n"
            text += f"❌ Kelmagan kunlar: {absent_count}\n"
            text += f"📊 Davomat foizi: {(present_count/len(attendances)*100):.1f}%\n\n"
            
            # Kunlik davomat
            text += "Kunlik davomat:\n"
            for attendance in sorted(attendances, key=lambda x: x.date):
                status = "✅ Keldi" if attendance.is_present else "❌ Kelmadi"
                text += f"{attendance.date.strftime('%d.%m.%Y')}: {status}\n"
                
            await message.answer(text)
            
        else:
            # O'qituvchi uchun sinf tanlash
            classes = await Class.filter(teacher=user)
            if not classes:
                await message.answer("Siz hali sinf qo'shmagansiz")
                return
                
            buttons = []
            for class_obj in classes:
                buttons.append([
                    types.InlineKeyboardButton(
                        text=class_obj.name,
                        callback_data=f"attendance_{class_obj.id}"
                    )
                ])
            
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("Qaysi sinfning davomatini ko'rmoqchisiz?", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in show_attendance: {e}")
        await message.answer("Xatolik yuz berdi")

@router.callback_query(lambda c: c.data.startswith('attendance_'))
async def process_attendance(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[1])
    class_obj = await Class.get(id=class_id).prefetch_related('students')
    
    if not class_obj.students:
        await callback.message.edit_text("Bu sinfda hali o'quvchilar yo'q")
        return
    
    buttons = []
    for student in await class_obj.students.all():
        buttons.append([
            types.InlineKeyboardButton(
                text=f"✅ {student.full_name}",
                callback_data=f"markpresent_{class_id}_{student.id}"
            ),
            types.InlineKeyboardButton(
                text=f"❌ {student.full_name}",
                callback_data=f"markabsent_{class_id}_{student.id}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "O'quvchilarning bugungi davomatini belgilang:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data.startswith(('markpresent_', 'markabsent_')))
async def process_attendance_mark(callback: types.CallbackQuery):
    try:
        # Log the callback data for debugging
        logger.info(f"Received callback data: {callback.data}")
        
        # Split the callback data and log the result
        parts = callback.data.split('_')
        logger.info(f"Split parts: {parts}")
        
        if len(parts) != 3:
            raise ValueError(f"Unexpected number of parts: {len(parts)}")
        
        action, class_id, student_id = parts
        is_present = action == 'markpresent'
        
        student = await User.get(id=int(student_id))
        class_obj = await Class.get(id=int(class_id))
        
        # Check if attendance already exists for today
        from datetime import datetime
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        attendance = await Attendance.get_or_create(
            user=student,
            class_id=class_obj,
            date=today,
            defaults={'is_present': is_present}
        )
        
        if not attendance[1]:  # If attendance already existed
            attendance[0].is_present = is_present
            await attendance[0].save()
        
        status = "✅ Keldi" if is_present else "❌ Kelmadi"
        await callback.answer(f"{student.full_name}: {status}")
    except Exception as e:
        # Log the full exception message
        logger.error(f"Error processing attendance mark: {e}")
        await callback.answer(f"Xatolik yuz berdi: {str(e)}")

@router.message(F.text == "📊 Baholar")
async def show_grades(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    today = datetime.now().date()
    
    if user.is_teacher:
        # O'qituvchi uchun: Sinfdagi barcha o'quvchilarning bugungi baholarini ko'rsatish
        classes = await Class.filter(teacher=user)
        if not classes:
            await message.answer("Siz hali sinf yaratmagansiz!")
            return
        
        buttons = []
        for class_obj in classes:
            buttons.append([
                types.InlineKeyboardButton(
                    text=class_obj.name,
                    callback_data=f"view_class_grades_{class_obj.id}"
                )
            ])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Qaysi sinfning bugungi baholarini ko'rmoqchisiz?", reply_markup=keyboard)
    else:
        # O'quvchi uchun: Faqat bugungi baholarni ko'rsatish
        grades = await Grade.filter(
            student=user,
            date=today
        ).prefetch_related('subject')
        
        if not grades:
            await message.answer("Bugun sizga hali baho qo'yilmagan!")
            return
        
        text = f"📊 Bugungi baholar ({today.strftime('%d.%m.%Y')}):\n\n"
        for grade in grades:
            text += f"📝 {grade.subject.title}: {grade.value}\n"
        
        await message.answer(text)

@router.callback_query(lambda c: c.data.startswith('view_class_grades_'))
async def show_class_grades(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[3])
    class_obj = await Class.get(id=class_id)
    
    grades = await Grade.filter(
        class_id=class_id
    ).prefetch_related('student', 'subject')
    
    if not grades:
        await callback.message.edit_text("Bu sinfda hali baholar yo'q!")
        return
    
    text = f"📊 {class_obj.name} sinfi baholari:\n\n"
    current_student = None
    
    for grade in sorted(grades, key=lambda x: (x.student.id, x.date)):
        if current_student != grade.student.id:
            current_student = grade.student.id
            text += f"\n👤 {grade.student.full_name}:\n"
        text += f"📝 {grade.subject.title}: {grade.value} ({grade.date.strftime('%d.%m.%Y')})\n"
    
    # Agar xabar juda uzun bo'lsa, bir necha qismga bo'lib yuborish
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await callback.message.answer(text[x:x+4096])
    else:
        await callback.message.edit_text(text)

# Baho qo'yish
@router.message(F.text == "📝 Baho qo'yish")
async def start_grade_process(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    if not user.is_teacher:
        await message.answer("Faqat o'qituvchilar baho qo'ya oladi!")
        return
    
    classes = await Class.filter(teacher=user)
    if not classes:
        await message.answer("Siz hali sinf yaratmagansiz!")
        return
    
    buttons = []
    for class_obj in classes:
        buttons.append([
            types.InlineKeyboardButton(
                text=class_obj.name,
                callback_data=f"grade_class_{class_obj.id}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Qaysi sinfga baho qo'ymoqchisiz?", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('grade_class_'))
async def select_student_for_grade(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[2])
    class_obj = await Class.get(id=class_id).prefetch_related('students')
    
    if not class_obj.students:
        await callback.message.edit_text("Bu sinfda hali o'quvchilar yo'q")
        return
    
    buttons = []
    for student in await class_obj.students.all():
        buttons.append([
            types.InlineKeyboardButton(
                text=f"{student.full_name}",
                callback_data=f"grade_student_{class_id}_{student.id}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "Qaysi o'quvchiga baho qo'ymoqchisiz?",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data.startswith('grade_student_'))
async def select_subject_for_grade(callback: types.CallbackQuery):
    class_id, student_id = map(int, callback.data.split('_')[2:])
    class_obj = await Class.get(id=class_id)
    teacher = await class_obj.teacher
    
    subjects = await Subject.filter(teacher_id=teacher.id)
    if not subjects:
        await callback.message.edit_text("Siz hali birorta fan qo'shmagansiz!")
        return
    
    buttons = []
    for subject in subjects:
        buttons.append([
            types.InlineKeyboardButton(
                text=subject.title,
                callback_data=f"grade_subject_{class_id}_{student_id}_{subject.id}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "Qaysi fanga baho qo'ymoqchisiz?",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data.startswith('grade_subject_'))
async def enter_grade_value(callback: types.CallbackQuery, state: FSMContext):
    class_id, student_id, subject_id = map(int, callback.data.split('_')[2:])
    await state.update_data(class_id=class_id, student_id=student_id, subject_id=subject_id)
    await state.set_state(TeacherActions.waiting_for_grade)
    await callback.message.edit_text("Iltimos, bahoni kiriting (1-100):")

@router.message(TeacherActions.waiting_for_grade)
async def process_grade_value(message: types.Message, state: FSMContext):
    try:
        grade_value = int(message.text)
        if not 1 <= grade_value <= 100:
            await message.answer("Baho 1 dan 100 gacha bo'lishi kerak!")
            return
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting!")
        return
    
    data = await state.get_data()
    class_id = data['class_id']
    student_id = data['student_id']
    subject_id = data['subject_id']
    
    student = await User.get(id=student_id)
    subject = await Subject.get(id=subject_id)
    
    # Bahoni saqlash
    today = datetime.now()
    grade = await Grade.create(
        student=student,
        subject=subject,
        class_id=class_id,
        value=grade_value,
        date=today.date()
    )
    
    # O'quvchiga xabar yuborish
    await message.bot.send_message(
        chat_id=student.user_id,
        text=f"Sizga yangi baho qo'yildi!\n\n"
             f"Fan: {subject.title}\n"
             f"Baho: {grade_value}\n"
             f"Sana: {today.strftime('%d.%m.%Y')}"
    )
    
    await message.answer(f"{student.full_name}ga {subject.title} fanidan {grade_value} baho qo'yildi!")
    await state.clear()

# O'quvchi uchun kunlik baholarni ko'rish
@router.message(F.text == "📊 Baholar")
async def show_grades(message: types.Message):
    user = await User.get(user_id=message.from_user.id)
    today = datetime.now().date()
    
    if user.is_teacher:
        # O'qituvchi uchun
        classes = await Class.filter(teacher=user)
        if not classes:
            await message.answer("Siz hali sinf yaratmagansiz!")
            return
        
        buttons = []
        for class_obj in classes:
            buttons.append([
                types.InlineKeyboardButton(
                    text=class_obj.name,
                    callback_data=f"view_class_grades_{class_obj.id}"
                )
            ])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Qaysi sinfning baholarini ko'rmoqchisiz?", reply_markup=keyboard)
    else:
        # O'quvchi uchun
        grades = await Grade.filter(
            student=user,
            date=today
        ).prefetch_related('subject')
        
        if not grades:
            await message.answer("Bugun sizga hali baho qo'yilmagan!")
            return
        
        text = f"📊 Bugungi baholar ({today.strftime('%d.%m.%Y')}):\n\n"
        for grade in grades:
            text += f"📝 {grade.subject.title}: {grade.value}\n"
        
        await message.answer(text)

@router.callback_query(lambda c: c.data.startswith('view_class_grades_'))
async def show_class_grades(callback: types.CallbackQuery):
    class_id = int(callback.data.split('_')[3])
    class_obj = await Class.get(id=class_id)
    
    grades = await Grade.filter(
        class_id=class_id
    ).prefetch_related('student', 'subject')
    
    if not grades:
        await callback.message.edit_text("Bu sinfda hali baholar yo'q!")
        return
    
    text = f"📊 {class_obj.name} sinfi baholari:\n\n"
    current_student = None
    
    for grade in sorted(grades, key=lambda x: (x.student.id, x.date)):
        if current_student != grade.student.id:
            current_student = grade.student.id
            text += f"\n👤 {grade.student.full_name}:\n"
        text += f"📝 {grade.subject.title}: {grade.value} ({grade.date.strftime('%d.%m.%Y')})\n"
    
    # Agar xabar juda uzun bo'lsa, bir necha qismga bo'lib yuborish
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await callback.message.answer(text[x:x+4096])
    else:
        await callback.message.edit_text(text)
