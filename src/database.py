import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
from rich.console import Console

console = Console()


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: datetime
    model: str


@dataclass
class ChatSession:
    id: int
    start_time: datetime
    current_model: str
    messages: List[ChatMessage]


class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.initialize_database()

    def get_connection(self) -> sqlite3.Connection:
        def adapt_datetime(val):
            return val.isoformat()

        def convert_datetime(val):
            try:
                return datetime.fromisoformat(val.decode())
            except AttributeError:
                return datetime.fromisoformat(val)

        sqlite3.register_adapter(datetime, adapt_datetime)
        sqlite3.register_converter("DATETIME", convert_datetime)

        return sqlite3.connect(
            self.db_file, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )

    def initialize_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME NOT NULL,
                    current_model TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    FOREIGN KEY (current_model) REFERENCES models(name)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
                    FOREIGN KEY (model) REFERENCES models(name)
                )
            """)

    def insert_model(self, name: str, description: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO models (name, description) VALUES (?, ?)",
                    (name, description),
                )
            except sqlite3.IntegrityError:
                console.print(f"[yellow]Model '{name}' already exists[/]")

    def get_all_models(self) -> List[Tuple[str, str]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, description FROM models")
            return cursor.fetchall()

    def create_session(self, model: str, title: str = "", description: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO chat_sessions
                   (start_time, current_model, title, description)
                   VALUES (?, ?, ?, ?)""",
                (datetime.now(), model, title, description),
            )
            return cursor.lastrowid

    def get_session(self, session_id: int) -> Optional[ChatSession]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, start_time as "start_time [DATETIME]",
                   current_model FROM chat_sessions WHERE id = ?""",
                (session_id,),
            )
            session_data = cursor.fetchone()
            if not session_data:
                return None
            cursor.execute(
                """SELECT timestamp as "timestamp [DATETIME]",
                   role, content, model
                   FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY timestamp""",
                (session_id,),
            )
            messages = [
                ChatMessage(role=row[1], content=row[2], timestamp=row[0], model=row[3])
                for row in cursor.fetchall()
            ]
            return ChatSession(
                id=session_data[0],
                start_time=session_data[1],
                current_model=session_data[2],
                messages=messages,
            )

    def get_all_sessions(self) -> List[Tuple[int, datetime, str, str]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, start_time as "start_time [DATETIME]",
                   current_model, title
                   FROM chat_sessions
                   ORDER BY start_time DESC"""
            )
            return cursor.fetchall()

    def add_message(self, session_id: int, message: ChatMessage):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO chat_messages
                   (session_id, timestamp, role, content, model)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    session_id,
                    message.timestamp,
                    message.role,
                    message.content,
                    message.model,
                ),
            )

    def update_session_model(self, session_id: int, model: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET current_model = ? WHERE id = ?",
                (model, session_id),
            )

    def update_session_title(self, session_id: int, new_title: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET title = ? WHERE id = ?",
                (new_title, session_id),
            )

    def delete_session(self, session_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
