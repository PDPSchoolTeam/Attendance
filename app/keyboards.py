from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("O'qituvchi"))
    keyboard.add(KeyboardButton("O'quvchi"))
    return keyboard

def get_teacher_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Fan qo'shish"), KeyboardButton(text="➕ Sinf qo'shish")],
            [KeyboardButton(text="✅ Davomat"), KeyboardButton(text="📝 Baho qo'yish")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_student_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏫 Sinfga a'zo bo'lish")],
            [KeyboardButton(text="📊 Natijalar")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_register_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨‍🎓 O'quvchi"), KeyboardButton(text="👨‍🏫 O'qituvchi")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_class_list_keyboard(classes):
    keyboard = InlineKeyboardMarkup()
    for class_group in classes:
        keyboard.add(InlineKeyboardButton(
            text=class_group.name,
            callback_data=f"class_{class_group.id}"
        ))
    return keyboard

def get_student_attendance_keyboard(student_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Keldi", callback_data=f"attend_yes_{student_id}"),
        InlineKeyboardButton("❌ Kelmadi", callback_data=f"attend_no_{student_id}")
    )
    return keyboard

def get_date_navigation_keyboard(current_date, class_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("◀️ Oldingi kun", callback_data=f"date_prev_{current_date}_{class_id}"),
        InlineKeyboardButton("Keyingi kun ▶️", callback_data=f"date_next_{current_date}_{class_id}")
    )
    return keyboard
