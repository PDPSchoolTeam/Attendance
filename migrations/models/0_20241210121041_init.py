from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL UNIQUE,
    "full_name" VARCHAR(255) NOT NULL,
    "is_student" BOOL NOT NULL  DEFAULT False,
    "is_teacher" BOOL NOT NULL  DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "users"."user_id" IS 'Telegram user ID';
CREATE TABLE IF NOT EXISTS "classes" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "teacher_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "attendances" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "date" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "is_present" BOOL NOT NULL  DEFAULT False,
    "class_id_id" INT NOT NULL REFERENCES "classes" ("id") ON DELETE CASCADE,
    "student_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_attendances_student_12d3dc" UNIQUE ("student_id", "class_id_id", "date")
);
CREATE TABLE IF NOT EXISTS "subjects" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "teacher_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "exams" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "subject_id" INT NOT NULL REFERENCES "subjects" ("id") ON DELETE CASCADE,
    "teacher_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "grades" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "value" INT NOT NULL,
    "month" INT NOT NULL,
    "year" INT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "student_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    "subject_id" INT NOT NULL REFERENCES "subjects" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "lessons" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "days" VARCHAR(20),
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "class_id_id" INT NOT NULL REFERENCES "classes" ("id") ON DELETE CASCADE,
    "subject_id" INT NOT NULL REFERENCES "subjects" ("id") ON DELETE CASCADE,
    "teacher_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "classes_users" (
    "classes_id" INT NOT NULL REFERENCES "classes" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
