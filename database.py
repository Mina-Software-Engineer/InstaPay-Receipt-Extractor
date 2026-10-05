import sqlite3
from datetime import datetime
import os

class Database:
    def __init__(self, db_path=None):
        if not db_path:
            app_data = os.path.join(os.path.expanduser("~"), ".instapay_receipts")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "instapay.db")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approved_accounts (
                    account_number TEXT PRIMARY KEY,
                    description TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_number TEXT UNIQUE NOT NULL,
                    account_number TEXT NOT NULL,
                    receipt_date TEXT NOT NULL,
                    money_value REAL NOT NULL,
                    note TEXT,
                    note_number TEXT,
                    image_path TEXT,
                    raw_ocr_text TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS email_recipients (
                    email TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approved_note_numbers (
                    note_number TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            # Migrate the previous single-recipient setting once.
            legacy = conn.execute("SELECT value FROM settings WHERE key = 'outlook_recipient'").fetchone()
            count = conn.execute("SELECT COUNT(*) AS count FROM email_recipients").fetchone()["count"]
            if legacy and legacy["value"] and count == 0:
                for email in legacy["value"].replace(",", ";").split(";"):
                    email = email.strip()
                    if email:
                        conn.execute(
                            "INSERT OR IGNORE INTO email_recipients (email, enabled, created_at) VALUES (?, 1, ?)",
                            (email.lower(), datetime.now().isoformat()),
                        )
            note_columns = {row["name"] for row in conn.execute("PRAGMA table_info(approved_note_numbers)").fetchall()}
            if "name" not in note_columns:
                conn.execute("ALTER TABLE approved_note_numbers ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            receipt_columns = {row["name"] for row in conn.execute("PRAGMA table_info(receipts)").fetchall()}
            if "note_number" not in receipt_columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN note_number TEXT")
            conn.commit()

    def get_setting(self, key, default=""):
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_email_recipients(self):
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT email, enabled FROM email_recipients ORDER BY email"
            ).fetchall()
            return [{"email": row["email"], "enabled": bool(row["enabled"])} for row in rows]

    def add_email_recipient(self, email, enabled=True):
        email = email.strip().lower()
        if not email:
            return
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO email_recipients (email, enabled, created_at) VALUES (?, ?, ?)",
                (email, 1 if enabled else 0, datetime.now().isoformat()),
            )
            conn.commit()

    def set_email_recipient_enabled(self, email, enabled):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE email_recipients SET enabled = ? WHERE email = ?",
                (1 if enabled else 0, email.strip().lower()),
            )
            conn.commit()

    def remove_email_recipient(self, email):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM email_recipients WHERE email = ?", (email.strip().lower(),))
            conn.commit()

    def get_enabled_email_recipients(self):
        return [item["email"] for item in self.get_email_recipients() if item["enabled"]]

    def get_approved_note_numbers(self):
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT note_number FROM approved_note_numbers ORDER BY note_number"
            ).fetchall()
            return [row["note_number"] for row in rows]

    def get_approved_note_pairs(self):
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT note_number, name FROM approved_note_numbers ORDER BY note_number"
            ).fetchall()
            return [{"note_number": row["note_number"], "name": row["name"] or ""} for row in rows]

    def get_approved_note_mapping(self):
        return {pair["note_number"]: pair["name"] for pair in self.get_approved_note_pairs()}

    def add_approved_note_number(self, note_number, name=""):
        note_number = str(note_number).strip()
        name = str(name).strip()
        if not note_number:
            return
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO approved_note_numbers (note_number, name, created_at) VALUES (?, ?, ?)",
                (note_number, name, datetime.now().isoformat()),
            )
            conn.commit()

    def remove_approved_note_number(self, note_number):
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM approved_note_numbers WHERE note_number = ?",
                (str(note_number).strip(),),
            )
            conn.commit()

    def get_note_number_for_name(self, name):
        name = str(name or "").strip().casefold()
        if not name:
            return ""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT note_number, name FROM approved_note_numbers WHERE name <> ''"
            ).fetchall()
        for row in rows:
            if str(row["name"]).strip().casefold() == name:
                return row["note_number"]
        return ""

    def get_name_for_note_number(self, note_number):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM approved_note_numbers WHERE note_number = ?",
                (str(note_number).strip(),),
            ).fetchone()
            return (row["name"] or "") if row else ""

    def is_note_number_approved(self, note_number):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM approved_note_numbers WHERE note_number = ?",
                (str(note_number).strip(),),
            ).fetchone()
            return row is not None

    def get_approved_accounts(self):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT account_number, description FROM approved_accounts ORDER BY account_number").fetchall()
            return [dict(row) for row in rows]

    def add_approved_account(self, account_number, description=""):
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO approved_accounts (account_number, description, created_at) VALUES (?, ?, ?)",
                         (account_number.strip(), description.strip(), datetime.now().isoformat()))
            conn.commit()

    def remove_approved_account(self, account_number):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM approved_accounts WHERE account_number = ?", (account_number,))
            conn.commit()

    def is_account_approved(self, account_number):
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM approved_accounts WHERE account_number = ?", (account_number.strip(),)).fetchone()
            return row is not None

    def receipt_exists(self, receipt_number):
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM receipts WHERE receipt_number = ?", (receipt_number.strip(),)).fetchone()
            return row is not None

    def save_receipt(self, receipt_number, account_number, receipt_date, money_value, note, image_path, raw_ocr_text, note_number=""):

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO receipts (receipt_number, account_number, receipt_date, money_value, note, note_number, image_path, raw_ocr_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                receipt_number.strip(),
                account_number.strip(),
                receipt_date.strip(),
                float(str(money_value).replace(",", "").strip()),
                note.strip() if note else "",
                str(note_number).replace(",", "").strip() if note_number else "",
                image_path or "",
                raw_ocr_text or "",
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid

    def get_all_receipts(self):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _parse_receipt_date(value):
        """Parse common Gemini/manual receipt date formats into a date object."""
        value = str(value or "").strip()
        if not value:
            return None
        formats = (
            "%d %b %Y %I:%M %p",
            "%d %b %Y %H:%M",
            "%d %b %Y %I:%M:%S %p",
            "%d %b %Y %H:%M:%S",
            "%d-%b-%Y %I:%M %p",
            "%d-%b-%Y %H:%M",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def get_receipts_by_receipt_date(self, target_date):
        """Return receipts matching the selected date across supported stored formats."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts ORDER BY created_at DESC").fetchall()
        return [
            dict(row)
            for row in rows
            if self._parse_receipt_date(row["receipt_date"]) == target_date
        ]

    def get_receipts_by_created_date(self, target_date):
        """Return all receipts scanned and saved on the selected export-folder date."""
        date_prefix = target_date.isoformat()
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM receipts WHERE created_at LIKE ? ORDER BY created_at DESC",
                (f"{date_prefix}%",),
            ).fetchall()
            return [dict(row) for row in rows]

    def clear_image_paths_by_ids(self, receipt_ids):
        """Remove stored image references while retaining receipt transaction data."""
        ids = [int(receipt_id) for receipt_id in receipt_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE receipts SET image_path = '' WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()
            return cursor.rowcount

    def delete_receipts_by_ids(self, receipt_ids):
        """Delete only the supplied receipt IDs and return the number removed."""
        ids = [int(receipt_id) for receipt_id in receipt_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM receipts WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()
            return cursor.rowcount
