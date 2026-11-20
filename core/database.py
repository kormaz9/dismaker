"""
DisMaker - SQLite Veritabanı ve Sunucu Ayarları Yönetimi
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from config import DB_PATH


class Database:
    """Sunucu bazlı moderasyon, autorole ve log ayarlarını yöneten SQLite arayüzü"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Tabloları oluşturur"""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS guild_settings (
                        guild_id INTEGER PRIMARY KEY,
                        autorole_name TEXT,
                        autorole_id INTEGER,
                        moderation_enabled INTEGER DEFAULT 0,
                        filter_profanity INTEGER DEFAULT 1,
                        filter_invites INTEGER DEFAULT 1,
                        mute_duration_seconds INTEGER DEFAULT 600,
                        log_channel_id INTEGER,
                        log_channel_name TEXT,
                        rules_channel_id INTEGER,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS moderation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        user_tag TEXT,
                        action TEXT,
                        reason TEXT,
                        duration_seconds INTEGER,
                        channel_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
        finally:
            conn.close()

    def save_guild_settings(
        self,
        guild_id: int,
        autorole_name: Optional[str] = None,
        autorole_id: Optional[int] = None,
        moderation_enabled: Optional[bool] = None,
        filter_profanity: Optional[bool] = None,
        filter_invites: Optional[bool] = None,
        mute_duration_seconds: Optional[int] = None,
        log_channel_id: Optional[int] = None,
        log_channel_name: Optional[str] = None,
        rules_channel_id: Optional[int] = None
    ) -> None:
        """Sunucu ayarlarını günceller veya ekler"""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
                current = cursor.fetchone()

                now = datetime.datetime.now(datetime.timezone.utc).isoformat()

                if current is None:
                    cursor.execute("""
                        INSERT INTO guild_settings (
                            guild_id, autorole_name, autorole_id, moderation_enabled,
                            filter_profanity, filter_invites, mute_duration_seconds,
                            log_channel_id, log_channel_name, rules_channel_id, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        guild_id,
                        autorole_name or "Üye",
                        autorole_id,
                        1 if moderation_enabled else 0,
                        1 if (filter_profanity is None or filter_profanity) else 0,
                        1 if (filter_invites is None or filter_invites) else 0,
                        mute_duration_seconds or 600,
                        log_channel_id,
                        log_channel_name or "› mod-log",
                        rules_channel_id,
                        now
                    ))
                else:
                    cursor.execute("""
                        UPDATE guild_settings SET
                            autorole_name = COALESCE(?, autorole_name),
                            autorole_id = COALESCE(?, autorole_id),
                            moderation_enabled = COALESCE(?, moderation_enabled),
                            filter_profanity = COALESCE(?, filter_profanity),
                            filter_invites = COALESCE(?, filter_invites),
                            mute_duration_seconds = COALESCE(?, mute_duration_seconds),
                            log_channel_id = COALESCE(?, log_channel_id),
                            log_channel_name = COALESCE(?, log_channel_name),
                            rules_channel_id = COALESCE(?, rules_channel_id),
                            updated_at = ?
                        WHERE guild_id = ?
                    """, (
                        autorole_name,
                        autorole_id,
                        1 if moderation_enabled is True else (0 if moderation_enabled is False else None),
                        1 if filter_profanity is True else (0 if filter_profanity is False else None),
                        1 if filter_invites is True else (0 if filter_invites is False else None),
                        mute_duration_seconds,
                        log_channel_id,
                        log_channel_name,
                        rules_channel_id,
                        now,
                        guild_id
                    ))
        finally:
            conn.close()

    def get_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Sunucu ayarlarını sözlük olarak döndürür"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def log_moderation_event(
        self,
        guild_id: int,
        user_id: int,
        user_tag: str,
        action: str,
        reason: str,
        duration_seconds: int,
        channel_id: int
    ) -> None:
        """Moderasyon olayını kaydeder"""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO moderation_logs (
                        guild_id, user_id, user_tag, action, reason, duration_seconds, channel_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (guild_id, user_id, user_tag, action, reason, duration_seconds, channel_id))
        finally:
            conn.close()


# Singleton veritabanı örneği
db = Database()
