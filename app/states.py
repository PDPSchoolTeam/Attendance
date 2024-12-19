from aiogram.dispatcher.filters.state import State, StatesGroup

class UserState(StatesGroup):
    role = State()
    full_name = State()
    select_class = State()

class LessonState(StatesGroup):
    title = State()
    description = State()

class ClassState(StatesGroup):
    name = State()

class AttendanceState(StatesGroup):
    select_class = State()
    mark_attendance = State()
    view_date = State()

class TeacherStates(StatesGroup):
    waiting_for_class_name = State()
    waiting_for_subject_name = State()
    waiting_for_student_selection = State()

class StudentStates(StatesGroup):
    waiting_for_class_selection = State()
    waiting_for_attendance_confirmation = State()
