from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.models import User, Class, Attendance
from datetime import datetime, timedelta
import logging
from functools import lru_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = Router()
rate_limit_dict = {}

class AttendanceState(StatesGroup):
    select_class = State()
    mark_attendance = State()
    view_date = State()
    selecting_class = State()
    marking_attendance = State()

async def check_rate_limit(user_id: int, limit: int = 5, window: int = 60) -> bool:
    current_time = datetime.now()
    if user_id in rate_limit_dict:
        requests = rate_limit_dict[user_id]
        requests = [time for time in requests if (current_time - time).seconds < window]
        if len(requests) >= limit:
            return False
        requests.append(current_time)
        rate_limit_dict[user_id] = requests
    else:
        rate_limit_dict[user_id] = [current_time]
    return True

@lru_cache(maxsize=100)
async def get_cached_class_groups(teacher_id: int):
    return await Class.filter(teacher_id=teacher_id).prefetch_related('students')

async def start_attendance(message: types.Message):
    try:
        logger.info(f"Starting attendance for user {message.from_user.id}")
        if not await check_rate_limit(message.from_user.id):
            await message.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        user = await User.filter(user_id=message.from_user.id).first()
        if not user or not user.is_teacher:
            await message.answer("Sizda bu amalni bajarish uchun huquq yo'q!")
            return

        classes = await get_cached_class_groups(user.id)
        if not classes:
            await message.answer("Siz hali sinf qo'shmagansiz!")
            return

        await AttendanceState.select_class.set()
        await message.answer(
            "Davomat olish uchun sinfni tanlang:",
            reply_markup=get_class_list_keyboard(classes)
        )
    except Exception as e:
        logger.error(f"Error in start_attendance: {e}")
        await message.answer("Xatolik yuz berdi")

async def process_class_selection_for_attendance(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        if not await check_rate_limit(callback_query.from_user.id):
            await callback_query.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        class_id = int(callback_query.data.split('_')[1])
        await state.update_data(class_id=class_id)
        
        # Optimized query with prefetch_related
        class_group = await Class.get(id=class_id).prefetch_related('students')
        students = await User.filter(class_group=class_group, is_student=True).prefetch_related('attendances')
        
        if not students:
            await callback_query.message.answer("Bu sinfda hali o'quvchilar yo'q!")
            await state.finish()
            return

        await AttendanceState.mark_attendance.set()
        await callback_query.message.answer(
            f"{class_group.name} sinfi davomati:\n"
            "O'quvchilarning davomat holatini belgilang:",
            reply_markup=get_student_attendance_keyboard(students)
        )
    except Exception as e:
        logger.exception(f"Error in process_class_selection: {e}")
        await callback_query.message.answer("Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

async def process_attendance_mark(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        if not await check_rate_limit(callback_query.from_user.id):
            await callback_query.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        action, student_id = callback_query.data.split('_')[1:]
        student_id = int(student_id)
        
        data = await state.get_data()
        class_id = data.get('class_id')
        
        teacher = await User.filter(user_id=callback_query.from_user.id).first()
        student = await User.get(id=student_id)
        class_group = await Class.get(id=class_id)

        # Create or update attendance
        attendance, created = await Attendance.get_or_create(
            student=student,
            date=datetime.now().date(),
            defaults={
                'is_present': action == 'yes',
                'marked_by': teacher
            }
        )

        if not created:
            attendance.is_present = action == 'yes'
            await attendance.save()

        await callback_query.message.edit_text(
            f"O'quvchi: {student.full_name}\n"
            f"Holati: {'✅ Keldi' if action == 'yes' else '❌ Kelmadi'}"
        )
    except Exception as e:
        logger.exception(f"Error in process_attendance_mark: {e}")
        await callback_query.message.answer("Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

async def view_attendance(message: types.Message):
    try:
        if not await check_rate_limit(message.from_user.id):
            await message.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        user = await User.get_or_none(user_id=message.from_user.id)
        
        if not user:
            await message.answer("⚠️ Avval ro'yxatdan o'ting!")
            return
        
        if user.is_teacher:
            # O'qituvchi uchun darslar ro'yxati
            lessons = await Lesson.filter(teacher=user)
            
            if not lessons:
                await message.answer("🚫 Sizda hozircha darslar yo'q.")
                return
            
            keyboard = []
            for lesson in lessons:
                keyboard.append([types.InlineKeyboardButton(
                    text=f"📚 {lesson.title}",
                    callback_data=f"lesson_attendance:{lesson.id}"
                )])
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer("📚 Qaysi dars bo'yicha davomat ko'rmoqchisiz?", reply_markup=markup)
        
        elif user.is_student:
            # O'quvchi uchun o'zi a'zo bo'lgan sinflar
            classes = await user.enrolled_classes.all()
            
            if not classes:
                await message.answer("🚫 Siz hech qanday sinfga a'zo emassiz.")
                return
            
            keyboard = []
            for class_obj in classes:
                keyboard.append([types.InlineKeyboardButton(
                    text=f"🏫 {class_obj.name}",
                    callback_data=f"class_attendance:{class_obj.id}"
                )])
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer("🏫 Qaysi sinf bo'yicha davomat ko'rmoqchisiz?", reply_markup=markup)
        
        logger.info(f"Attendance view initiated for user {user.id}")
    
    except Exception as e:
        logger.error(f"Error in view_attendance: {e}")
        await message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")

async def process_date_navigation(callback_query: types.CallbackQuery):
    try:
        if not await check_rate_limit(callback_query.from_user.id):
            await callback_query.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        action, date_str, class_id = callback_query.data.split('_')[1:]
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        if action == 'prev':
            new_date = current_date - timedelta(days=1)
        else:
            new_date = current_date + timedelta(days=1)

        await show_attendance_for_date(callback_query.message, int(class_id), new_date)
    except Exception as e:
        logger.exception(f"Error in process_date_navigation: {e}")

async def show_attendance_for_date(message: types.Message, class_id: int, date: datetime.date = None):
    try:
        if not await check_rate_limit(message.from_user.id):
            await message.answer("Iltimos, biroz kuting va qayta urinib ko'ring.")
            return

        if date is None:
            date = datetime.now().date()

        class_group = await Class.get(id=class_id).prefetch_related('students')
        students = await User.filter(class_group=class_group, is_student=True).prefetch_related('attendances')
        attendances = await Attendance.filter(
            date=date
        ).prefetch_related('student')

        # Create a dictionary for quick lookup
        attendance_dict = {a.student.id: a.is_present for a in attendances}

        text = f"📅 {date.strftime('%Y-%m-%d')} kuni uchun {class_group.name} sinfi davomati:\n\n"
        
        for student in students:
            is_present = attendance_dict.get(student.id)
            status = "✅ Kelgan" if is_present else "❌ Kelmagan" if is_present is not None else "❓ Belgilanmagan"
            text += f"{student.full_name}: {status}\n"

        keyboard = get_date_navigation_keyboard(date.strftime('%Y-%m-%d'), class_id)
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.exception("Error in show_attendance_for_date: %s" % e)

def get_date_navigation_keyboard(date_str: str, class_id: int):
    keyboard = [
        [
            types.InlineKeyboardButton(
                text="⬅️ Oldingi kun", 
                callback_data=f"date_nav_prev_{date_str}_{class_id}"
            ),
            types.InlineKeyboardButton(
                text="Keyingi kun ➡️", 
                callback_data=f"date_nav_next_{date_str}_{class_id}"
            )
        ]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_class_list_keyboard(classes):
    keyboard = []
    for class_group in classes:
        keyboard.append([types.InlineKeyboardButton(
            text=f"🏫 {class_group.name}",
            callback_data=f"select_class_{class_group.id}"
        )])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_student_attendance_keyboard(students):
    keyboard = []
    for student in students:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"✅ {student.full_name}", 
                callback_data=f"student_yes_{student.id}"
            ),
            types.InlineKeyboardButton(
                text=f"❌ {student.full_name}", 
                callback_data=f"student_no_{student.id}"
            )
        ])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "📊 Davomat ko'rish")
async def view_attendance_handler(message: types.Message, state: FSMContext):
    try:
        user = await User.get_or_none(user_id=message.from_user.id)
        
        if not user:
            await message.answer("⚠️ Avval ro'yxatdan o'ting!")
            return
        
        if user.is_teacher:
            # O'qituvchi uchun darslar ro'yxati
            lessons = await Lesson.filter(teacher=user)
            
            if not lessons:
                await message.answer("🚫 Sizda hozircha darslar yo'q.")
                return
            
            keyboard = []
            for lesson in lessons:
                keyboard.append([types.InlineKeyboardButton(
                    text=f"📚 {lesson.title}",
                    callback_data=f"lesson_attendance:{lesson.id}"
                )])
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer("📚 Qaysi dars bo'yicha davomat ko'rmoqchisiz?", reply_markup=markup)
        
        elif user.is_student:
            # O'quvchi uchun o'zi a'zo bo'lgan sinflar
            classes = await user.enrolled_classes.all()
            
            if not classes:
                await message.answer("🚫 Siz hech qanday sinfga a'zo emassiz.")
                return
            
            keyboard = []
            for class_obj in classes:
                keyboard.append([types.InlineKeyboardButton(
                    text=f"🏫 {class_obj.name}",
                    callback_data=f"class_attendance:{class_obj.id}"
                )])
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer("🏫 Qaysi sinf bo'yicha davomat ko'rmoqchisiz?", reply_markup=markup)
        
        logger.info(f"Attendance view initiated for user {user.id}")
    
    except Exception as e:
        logger.error(f"Error in view_attendance: {e}")
        await message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")

@router.callback_query(F.data.startswith("lesson_attendance:"))
async def process_lesson_attendance(callback: types.CallbackQuery):
    try:
        lesson_id = int(callback.data.split(":")[1])
        lesson = await Lesson.get(id=lesson_id)
        
        # Shu darsga tegishli o'quvchilar
        students = await lesson.class_id.students.all()
        
        if not students:
            await callback.message.answer("🚫 Ushbu darsda o'quvchilar yo'q.")
            return
        
        keyboard = get_student_attendance_keyboard(students)
        await callback.message.answer(f"📚 {lesson.title} darsi uchun davomat:", reply_markup=keyboard)
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error in process_lesson_attendance: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")
        await callback.answer()

@router.callback_query(F.data.startswith("class_attendance:"))
async def process_class_attendance(callback: types.CallbackQuery):
    try:
        class_id = int(callback.data.split(":")[1])
        class_obj = await Class.get(id=class_id)
        
        # Shu sinfga tegishli darslar
        lessons = await Lesson.filter(class_id=class_obj)
        
        if not lessons:
            await callback.message.answer("🚫 Ushbu sinfda darslar yo'q.")
            return
        
        keyboard = []
        for lesson in lessons:
            keyboard.append([types.InlineKeyboardButton(
                text=f"📚 {lesson.title}",
                callback_data=f"lesson_attendance:{lesson.id}"
            )])
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.answer(f"🏫 {class_obj.name} sinfi darslari:", reply_markup=markup)
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error in process_class_attendance: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")
        await callback.answer()

@router.message(F.text == "✅ Davomat")
async def show_classes_for_attendance(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user or not user.is_teacher:
        await message.answer("⚠️ Bu funksiya faqat o'qituvchilar uchun!")
        return
    
    # Get all classes
    classes = await Class.filter(teacher=user)
    
    if not classes:
        await message.answer("🚫 Sizda hali sinflar mavjud emas!")
        return
    
    # Create inline keyboard with classes
    keyboard = []
    for class_obj in classes:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"🏫 {class_obj.name}",
                callback_data=f"attendance_class:{class_obj.id}"
            )
        ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("📋 Davomat olish uchun sinfni tanlang:", reply_markup=markup)
    await state.set_state(AttendanceState.selecting_class)

@router.callback_query(lambda c: c.data.startswith("attendance_class:"))
async def show_students_for_attendance(callback: types.CallbackQuery, state: FSMContext):
    class_id = int(callback.data.split(":")[1])
    
    # Get class and its students
    class_obj = await Class.get(id=class_id).prefetch_related('students')
    students = await class_obj.students.all()
    
    if not students:
        await callback.message.edit_text("🚫 Bu sinfda o'quvchilar mavjud emas!")
        return
    
    # Create keyboard with students
    keyboard = []
    for student in students:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"✅ {student.full_name}",
                callback_data=f"mark_present:{student.id}:{class_id}"
            ),
            types.InlineKeyboardButton(
                text=f"❌ {student.full_name}",
                callback_data=f"mark_absent:{student.id}:{class_id}"
            )
        ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"📋 {class_obj.name} sinfi davomati:\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
        "Har bir o'quvchi uchun ✅ yoki ❌ ni bosing:",
        reply_markup=markup
    )
    await state.set_state(AttendanceState.marking_attendance)

@router.callback_query(lambda c: c.data.startswith(("mark_present:", "mark_absent:")))
async def mark_student_attendance(callback: types.CallbackQuery, state: FSMContext):
    action, student_id, class_id = callback.data.split(":")
    student_id, class_id = int(student_id), int(class_id)
    
    # Get student and class
    student = await User.get(id=student_id)
    class_obj = await Class.get(id=class_id)
    
    # Mark attendance
    is_present = action == "mark_present"
    await Attendance.create(
        student=student,
        class_id=class_obj,
        date=datetime.now().date(),
        is_present=is_present
    )
    
    # Update button to show marked status
    keyboard = []
    students = await class_obj.students.all()
    for s in students:
        attendance = await Attendance.get_or_none(
            student=s,
            class_id=class_obj,
            date=datetime.now().date()
        )
        
        if s.id == student_id:
            # This is the student we just marked
            status = "✅ Keldi" if is_present else "❌ Kelmadi"
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{s.full_name}: {status}",
                    callback_data="already_marked"
                )
            ])
        else:
            # Other students
            if attendance:
                status = "✅ Keldi" if attendance.is_present else "❌ Kelmadi"
                keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{s.full_name}: {status}",
                        callback_data="already_marked"
                    )
                ])
            else:
                keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"✅ {s.full_name}",
                        callback_data=f"mark_present:{s.id}:{class_id}"
                    ),
                    types.InlineKeyboardButton(
                        text=f"❌ {s.full_name}",
                        callback_data=f"mark_absent:{s.id}:{class_id}"
                    )
                ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"📋 {class_obj.name} sinfi davomati:\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
        "Har bir o'quvchi uchun ✅ yoki ❌ ni bosing:",
        reply_markup=markup
    )

@router.callback_query(lambda c: c.data == "already_marked")
async def already_marked(callback: types.CallbackQuery):
    await callback.answer("Bu o'quvchi uchun davomat allaqachon belgilangan!")

@router.message(F.text == "✅ Davomat belgilash")
async def mark_attendance(message: types.Message, state: FSMContext):
    user = await User.get_or_none(user_id=message.from_user.id)
    
    if not user or not user.is_teacher:
        await message.answer("⚠️ Faqat o'qituvchilar davomat belglay oladi!")
        return
    
    # O'qituvchining darslarini olish
    lessons = await Lesson.filter(teacher=user.id)
    
    keyboard = []
    for lesson in lessons:
        keyboard.append([types.InlineKeyboardButton(
            text=f"📚 {lesson.title}",
            callback_data=f"mark_lesson_attendance:{lesson.id}"
        )])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("📚 Qaysi dars uchun davomat belgilaysiz?", reply_markup=markup)

@router.callback_query(F.data.startswith("mark_lesson_attendance:"))
async def process_mark_lesson_attendance(callback: types.CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split(":")[1])
    lesson = await Lesson.get(id=lesson_id)
    
    # Shu darsga tegishli o'quvchilar
    class_obj = await lesson.class_id
    students = await class_obj.students.all()
    
    keyboard = []
    for student in students:
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"✅ {student.full_name}",
                callback_data=f"student_present:{student.id}:{lesson_id}"
            ),
            types.InlineKeyboardButton(
                text=f"❌ {student.full_name}",
                callback_data=f"student_absent:{student.id}:{lesson_id}"
            )
        ])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"📊 {lesson.title} darsining davomati:", 
        reply_markup=markup
    )

@router.callback_query(F.data.startswith("student_present:") or F.data.startswith("student_absent:"))
async def process_student_attendance(callback: types.CallbackQuery):
    action, student_id, lesson_id = callback.data.split(":")
    student_id, lesson_id = int(student_id), int(lesson_id)
    
    student = await User.get(id=student_id)
    lesson = await Lesson.get(id=lesson_id)
    
    is_present = action == "student_present"
    
    # Davomat yaratish
    await Attendance.create(
        student=student,
        lesson=lesson,
        is_present=is_present
    )
    
    await callback.message.edit_text(
        f"📊 {student.full_name} {lesson.title} darsida "
        f"{'ishtirok etdi' if is_present else 'ishtirok etmadi'}"
    )

@router.callback_query(F.data.startswith("mark_attendance:"))
async def mark_student_attendance(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info(f"Marking attendance for callback data: {callback.data}")
        _, student_id, class_id, status = callback.data.split(":")
        student = await User.get(id=int(student_id))
        class_obj = await Class.get(id=int(class_id))
        
        # Check if attendance already exists for today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        attendance = await Attendance.get_or_none(
            student=student,
            class_id=class_obj,
            date__gte=today,
            date__lt=tomorrow
        )
        
        is_present = status == "present"
        
        if attendance:
            attendance.is_present = is_present
            await attendance.save()
        else:
            await Attendance.create(
                student=student,
                class_id=class_obj,
                is_present=is_present
            )
        
        # Update the message with new attendance status
        students = await User.filter(role="student", class_id=class_obj.id)
        message_text = "Davomat:\n\n"
        
        for student in students:
            att = await Attendance.get_or_none(
                student=student,
                class_id=class_obj,
                date__gte=today,
                date__lt=tomorrow
            )
            status = "✅ Keldi" if att and att.is_present else "❌ Kelmadi" if att else "❓ Belgilanmagan"
            message_text += f"{student.full_name}: {status}\n"
        
        markup = await get_attendance_markup(class_obj.id)
        await callback.message.edit_text(message_text, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error in mark_student_attendance: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

async def get_attendance_markup(class_id: int):
    markup = InlineKeyboardMarkup(row_width=2)
    students = await User.filter(role="student", class_id=class_id)
    
    for student in students:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        attendance = await Attendance.get_or_none(
            student=student,
            class_id=class_id,
            date__gte=today,
            date__lt=tomorrow
        )
        
        if not attendance:
            markup.add(
                InlineKeyboardButton(
                    text=f"✅ {student.full_name}",
                    callback_data=f"mark_attendance:{student.id}:{class_id}:present"
                ),
                InlineKeyboardButton(
                    text=f"❌ {student.full_name}",
                    callback_data=f"mark_attendance:{student.id}:{class_id}:absent"
                )
            )
    
    return markup

@router.message(F.text == "✅ Davomat")
async def show_attendance_classes(message: Message):
    try:
        logger.info(f"Showing attendance classes for user {message.from_user.id}")
        user = await User.get(telegram_id=message.from_user.id)
        if user.role != "teacher":
            await message.answer("Sizda bu amalni bajarish uchun huquq yo'q!")
            return
            
        classes = await Class.all()
        markup = InlineKeyboardMarkup(row_width=2)
        
        for class_obj in classes:
            markup.add(InlineKeyboardButton(
                text=f"🏫 {class_obj.name}",
                callback_data=f"show_attendance:{class_obj.id}"
            ))
            
        await message.answer("Qaysi sinf uchun davomat olmoqchisiz?", reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error in show_attendance_classes: {e}")
        await message.answer("Xatolik yuz berdi")

@router.callback_query(F.data.startswith("show_attendance:"))
async def show_class_attendance(callback: CallbackQuery):
    try:
        class_id = int(callback.data.split(":")[1])
        class_obj = await Class.get(id=class_id)
        
        students = await User.filter(role="student", class_id=class_id)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        message_text = f"{class_obj.name} sinfi davomati ({today.strftime('%d.%m.%Y')}):\n\n"
        
        for student in students:
            att = await Attendance.get_or_none(
                student=student,
                class_id=class_obj,
                date__gte=today,
                date__lt=tomorrow
            )
            status = "✅ Keldi" if att and att.is_present else "❌ Kelmadi" if att else "❓ Belgilanmagan"
            message_text += f"{student.full_name}: {status}\n"
        
        markup = await get_attendance_markup(class_id)
        await callback.message.edit_text(message_text, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error in show_class_attendance: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)
