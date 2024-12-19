from aiogram import types
from aiogram.dispatcher import FSMContext
from app.models import Class, Subject, User
from app.states import TeacherStates
from app.keyboards import get_teacher_keyboard

async def add_class_start(message: types.Message, state: FSMContext):
    await message.reply("Sinf nomini kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await TeacherStates.waiting_for_class_name.set()

async def add_class_finish(message: types.Message, state: FSMContext):
    class_name = message.text
    teacher = await User.get(user_id=message.from_user.id)
    
    # Create new class
    await Class.create(name=class_name, teacher=teacher)
    
    await message.reply(f"Sinf '{class_name}' muvaffaqiyatli qo'shildi!", 
                       reply_markup=get_teacher_keyboard())
    await state.finish()

async def add_subject_start(message: types.Message, state: FSMContext):
    await message.reply("Fan nomini kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await TeacherStates.waiting_for_subject_name.set()

async def add_subject_finish(message: types.Message, state: FSMContext):
    subject_name = message.text
    teacher = await User.get(user_id=message.from_user.id)
    
    # Create new subject
    await Subject.create(title=subject_name, teacher=teacher)
    
    await message.reply(f"Fan '{subject_name}' muvaffaqiyatli qo'shildi!", 
                       reply_markup=get_teacher_keyboard())
    await state.finish()

def register_teacher_handlers(dp):
    dp.register_message_handler(add_class_start, lambda m: m.text == "Sinf qo'shish" and m.from_user.id)
    dp.register_message_handler(add_class_finish, state=TeacherStates.waiting_for_class_name)
    dp.register_message_handler(add_subject_start, lambda m: m.text == "Fan qo'shish" and m.from_user.id)
    dp.register_message_handler(add_subject_finish, state=TeacherStates.waiting_for_subject_name)
