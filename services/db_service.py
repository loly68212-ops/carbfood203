"""
تخزين المحادثات وحدود الاستخدام في PostgreSQL قياسي (قابل للنقل لأي خادم).

كل الاستعلامات مُعامَلة (parameterized) لمنع أي حقن SQL. لا يُخزَّن أي محتوى صور
(فقط نص المحادثة + علامة أنّ الرسالة رافقتها صورة) للحفاظ على خفّة قاعدة البيانات
والخصوصية.

الجداول (تُنشأ خارجيًا مرة واحدة):
  ai_conversations(id, user_id, title, created_at, updated_at)
  ai_messages(id, conversation_id, role, content, has_image, created_at)
  ai_usage(user_id, usage_date, messages_count, images_count)
"""

import threading
from contextlib import contextmanager
from datetime import date

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from . import config

_pool = None
_lock = threading.Lock()

DEFAULT_TITLE = "محادثة جديدة"


def _get_pool():
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(1, 8, dsn=config.DATABASE_URL)
    return _pool


@contextmanager
def _conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def db_available() -> bool:
    """فحص سريع لتوفّر قاعدة البيانات دون رفع استثناء."""
    if not config.db_configured():
        return False
    try:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


# ── المحادثات ────────────────────────────────────────────────────────────────
def list_conversations(user_id: str) -> list:
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, title, updated_at FROM ai_conversations "
            "WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,),
        )
        return [
            {"id": str(r["id"]), "title": r["title"], "updated_at": r["updated_at"]}
            for r in cur.fetchall()
        ]


def create_conversation(user_id: str, title: str = DEFAULT_TITLE) -> str:
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO ai_conversations (user_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, title),
        )
        return str(cur.fetchone()["id"])


def delete_conversation(user_id: str, conversation_id: str) -> None:
    # حذف مقيّد بالمستخدم — لا يستطيع أحد حذف محادثة غيره (الرسائل تُحذف تلقائيًا cascade)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM ai_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )


def conversation_belongs_to(user_id: str, conversation_id: str) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM ai_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        return cur.fetchone() is not None


def set_title_if_default(conversation_id: str, title: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE ai_conversations SET title = %s "
            "WHERE id = %s AND title = %s",
            (title, conversation_id, DEFAULT_TITLE),
        )


# ── الرسائل ──────────────────────────────────────────────────────────────────
def get_messages(conversation_id: str) -> list:
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT role, content, has_image FROM ai_messages "
            "WHERE conversation_id = %s ORDER BY created_at ASC, id ASC",
            (conversation_id,),
        )
        return [
            {"role": r["role"], "content": r["content"], "has_image": r["has_image"]}
            for r in cur.fetchall()
        ]


def add_message(conversation_id: str, role: str, content: str, has_image: bool = False) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ai_messages (conversation_id, role, content, has_image) "
            "VALUES (%s, %s, %s, %s)",
            (conversation_id, role, content, has_image),
        )
        cur.execute(
            "UPDATE ai_conversations SET updated_at = NOW() WHERE id = %s",
            (conversation_id,),
        )


# ── حدود الاستخدام اليومية ───────────────────────────────────────────────────
def get_usage(user_id: str, day: date) -> tuple:
    """يُرجع (عدد الرسائل، عدد الصور) لهذا المستخدم في هذا اليوم."""
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT messages_count, images_count FROM ai_usage "
            "WHERE user_id = %s AND usage_date = %s",
            (user_id, day),
        )
        row = cur.fetchone()
        if not row:
            return (0, 0)
        return (row["messages_count"], row["images_count"])


def increment_usage(user_id: str, day: date, messages: int = 0, images: int = 0) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ai_usage (user_id, usage_date, messages_count, images_count) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (user_id, usage_date) DO UPDATE SET "
            "messages_count = ai_usage.messages_count + %s, "
            "images_count = ai_usage.images_count + %s",
            (user_id, day, messages, images, messages, images),
        )
