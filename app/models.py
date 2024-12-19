from tortoise import fields, models

class User(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField(unique=True, description="Telegram user ID")
    full_name = fields.CharField(max_length=255)
    is_student = fields.BooleanField(default=False)
    is_teacher = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return self.full_name

class Class(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    teacher = fields.ForeignKeyField('models.User', related_name='classes', on_delete=fields.CASCADE)
    students = fields.ManyToManyField('models.User', related_name='enrolled_classes')
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "classes"

    def __str__(self):
        return self.name

class Subject(models.Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    teacher = fields.ForeignKeyField('models.User', related_name='subjects')
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "subjects"

    def __str__(self):
        return self.title

class Attendance(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='attendances')
    class_id = fields.ForeignKeyField('models.Class', related_name='attendances')
    date = fields.DatetimeField(auto_now_add=True)
    is_present = fields.BooleanField(default=False)

    class Meta:
        table = "attendances"
        unique_together = (("user", "class_id", "date"),)

    def __str__(self):
        return f"{self.user.full_name} - {self.class_id.name} - {self.date.strftime('%d.%m.%Y')}"

class Grade(models.Model):
    id = fields.IntField(pk=True)
    student = fields.ForeignKeyField('models.User', related_name='grades')
    subject = fields.ForeignKeyField('models.Subject', related_name='grades')
    value = fields.IntField()  # 1-5 oraliqda baho
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "grades"

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.title}: {self.value}"
