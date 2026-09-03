import os
import sys
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRectF, QUrl, QPropertyAnimation, QEasingCurve, QDate, QStringListModel
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QFont, QBrush, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QDateEdit,
    QInputDialog, QCompleter
)

from database import Database
from reporting import Validator, generate_daily_reports, generate_approved_note_numbers_report
from services import OcrService, OutlookService


@dataclass
class PendingReceipt:
    image_path: str
    data: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    status: str = "Pending"
    error: Any = ""
    saved: bool = False


class ReceiptThumbnail(QWidget):
    """Thumbnail card containing only the receipt image and its internal status."""

    clicked = pyqtSignal()

    def __init__(self, image_path, status, parent=None):
        super().__init__(parent)
        self.setFixedSize(145, 135)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.image_button = QPushButton()
        self.image_button.setFixedSize(139, 107)
        self.image_button.setIconSize(QSize(135, 103))
        self.image_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_button.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; }")
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_button.setIcon(QIcon(pixmap))
        self.image_button.clicked.connect(self._emit_clicked)
        layout.addWidget(self.image_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel(status)
        self.status_label.setFixedHeight(22)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #3F3F3F; background: transparent; border: none; font-size: 9px;")
        layout.addWidget(self.status_label)

    def _emit_clicked(self, checked=False):
        self.clicked.emit()

    def set_status(self, status):
        self.status_label.setText(status)

    def set_selected(self, selected, background):
        border = "3px solid #1565c0" if selected else "1px solid #999"
        self.setStyleSheet(f"ReceiptThumbnail {{ background: {background}; border: {border}; border-radius: 5px; }}")


class PreviewLabel(QLabel):
    """A bounded image preview that never uses the source image size as its layout size."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

    def set_preview_pixmap(self, pixmap):
        self._source_pixmap = pixmap
        self._refresh_pixmap()

    def clear_preview(self, text=""):
        self._source_pixmap = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self):
        if self._source_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        scaled = self._source_pixmap.scaled(
            self.contentsRect().size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class CircularProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setFixedSize(72, 72)

    def setValue(self, value):
        self._value = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(7, 7, 58, 58)
        painter.setPen(QPen(QColor("#eeeeee"), 3))
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(QPen(QColor("#3F3F3F"), 3))
        painter.drawArc(rect, 90 * 16, -int(self._value * 360 * 16 / 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#3F3F3F")))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 0, float(self.width()), float(self.height())), Qt.AlignmentFlag.AlignCenter, f"{self._value}%")
        painter.end()


class ExtractionProgressDialog(QDialog):
    cancelled = pyqtSignal()

    def __init__(self, total, parent=None):
        super().__init__(parent)
        self.total = max(1, total)
        self.setWindowTitle("Extracting InstaPay Receipts")
        self.setModal(True)
        self.setFixedSize(360, 245)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("progressCard")
        card.setStyleSheet("""
            QFrame#progressCard { background: #FBF5E5; border: 1px solid #d8d0c0; border-radius: 12px; }
            QLabel#progressTitle { color: #3F3F3F; font-size: 14px; font-weight: 600; }
            QLabel#progressMessage { color: #3F3F3F; font-size: 9px; }
            QPushButton#cancelButton { background: #121212; color: #3F3F3F; border: none; border-radius: 14px; padding: 7px 22px; font-size: 14px; }
            QPushButton#cancelButton:hover { background: #242424; }
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 45))
        card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(card)
        self.circular = CircularProgress(card)
        card_layout.addWidget(self.circular, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.title = QLabel("Extracting your data...")
        self.title.setObjectName("progressTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.title)
        self.message = QLabel(f"Extracted 0 of {self.total} photos.\nThis may take a few minutes. You can cancel at any time.")
        self.message.setObjectName("progressMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        card_layout.addWidget(self.message)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.cancelled.emit)
        self.cancel_button.clicked.connect(self.close)
        card_layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(card)

    def update_progress(self, extracted, current_name=""):
        self.circular.setValue(int(extracted * 100 / self.total))
        if extracted < self.total and current_name:
            self.message.setText(f"Extracted {extracted} of {self.total} photos.\nCurrently processing: {current_name}")
        else:
            self.message.setText(f"Extracted {extracted} of {self.total} photos.")


class OcrBatchWorker(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(int, dict)
    failed = pyqtSignal(int, str)
    finished_all = pyqtSignal()

    def __init__(self, image_paths, api_key):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.stop_requested = False

    def cancel(self):
        self.stop_requested = True

    def run(self):
        total = len(self.image_paths)
        for index, image_path in enumerate(self.image_paths):
            if self.stop_requested:
                break
            self.progress.emit(index + 1, total, image_path)
            try:
                self.completed.emit(index, OcrService.process_receipt(image_path, self.api_key))
            except Exception as exc:
                self.failed.emit(index, str(exc))
        self.finished_all.emit()


class SettingsWindow(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("InstaPay Settings")
        self.resize(550, 560)
        self.setStyleSheet("""
            QScrollBar:vertical { background: #FBF5E5; width: 10px; margin: 3px 2px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #3F3F3F; min-height: 30px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #121212; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar:horizontal { background: #FBF5E5; height: 10px; margin: 2px 3px; border-radius: 5px; }
            QScrollBar::handle:horizontal { background: #3F3F3F; min-width: 30px; border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: #121212; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        """)
        self.init_ui()

    def init_ui(self):
        root_layout = QHBoxLayout(self)
        navigation = QVBoxLayout()
        navigation.setSpacing(6)
        navigation_label = QLabel("<b>Settings</b>")
        navigation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation.addWidget(navigation_label)
        self.settings_general_button = QPushButton("General")
        self.settings_admin_button = QPushButton("Admin")
        navigation.addWidget(self.settings_general_button)
        navigation.addWidget(self.settings_admin_button)
        navigation.addStretch()
        navigation_widget = QWidget()
        navigation_widget.setLayout(navigation)
        navigation_widget.setFixedWidth(120)
        root_layout.addWidget(navigation_widget)

        self.settings_stack = QStackedWidget()
        root_layout.addWidget(self.settings_stack, 1)
        self.settings_general_button.clicked.connect(lambda: self.settings_stack.setCurrentIndex(0))
        self.settings_admin_button.clicked.connect(self.open_admin_page)

        general_page = QWidget()
        layout = QVBoxLayout(general_page)
        outlook_group = QGroupBox("Outlook Report Recipients")
        outlook_layout = QVBoxLayout()
        outlook_layout.addWidget(QLabel("Check the email addresses that should receive the Excel report and images ZIP."))
        self.recipient_table = QTableWidget()
        self.recipient_table.setColumnCount(2)
        self.recipient_table.setHorizontalHeaderLabels(["Send", "Email Address"])
        self.recipient_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.recipient_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.recipient_table.setMinimumHeight(130)
        self.recipient_table.cellChanged.connect(self.recipient_checkbox_changed)
        outlook_layout.addWidget(self.recipient_table)
        recipient_add_layout = QHBoxLayout()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("recipient@example.com")
        btn_add_email = QPushButton("Add Email")
        btn_add_email.clicked.connect(self.add_email)
        btn_remove_email = QPushButton("Remove Checked")
        btn_remove_email.clicked.connect(self.remove_checked_emails)
        recipient_add_layout.addWidget(self.email_input)
        recipient_add_layout.addWidget(btn_add_email)
        recipient_add_layout.addWidget(btn_remove_email)
        outlook_layout.addLayout(recipient_add_layout)
        outlook_group.setLayout(outlook_layout)
        layout.addWidget(outlook_group)
        self.load_recipients()

        note_numbers_group = QGroupBox("Approved Note Numbers and Names")
        note_numbers_layout = QVBoxLayout()
        note_numbers_layout.addWidget(QLabel("Add the approved number and its corresponding name. The name is used for matching receipts."))
        self.note_numbers_list = QTableWidget()
        self.note_numbers_list.setColumnCount(2)
        self.note_numbers_list.setHorizontalHeaderLabels(["Approved Number", "Corresponding Name"])
        self.note_numbers_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.note_numbers_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.note_numbers_list.setMinimumHeight(110)
        note_numbers_layout.addWidget(self.note_numbers_list)
        note_number_controls = QHBoxLayout()
        self.note_number_input = QLineEdit()
        self.note_number_input.setPlaceholderText("Enter digits only")
        self.note_name_input = QLineEdit()
        self.note_name_input.setPlaceholderText("Enter corresponding name")
        add_note_number_button = QPushButton("Add Number and Name")
        add_note_number_button.clicked.connect(self.add_note_number)
        remove_note_number_button = QPushButton("Remove Selected")
        remove_note_number_button.clicked.connect(self.remove_note_number)
        note_number_controls.addWidget(self.note_number_input)
        note_number_controls.addWidget(self.note_name_input)
        note_number_controls.addWidget(add_note_number_button)
        note_number_controls.addWidget(remove_note_number_button)
        note_numbers_layout.addLayout(note_number_controls)
        note_numbers_group.setLayout(note_numbers_layout)
        layout.addWidget(note_numbers_group)
        self.load_note_numbers()

        accounts_group = QGroupBox("Approved Account Numbers / Labels")
        accounts_layout = QVBoxLayout()
        self.accounts_text = QTextEdit()
        self.accounts_text.setPlaceholderText("Enter one approved account number or label per line")
        self.accounts_text.setPlainText("\n".join(a["account_number"] for a in self.db.get_approved_accounts()))
        accounts_layout.addWidget(self.accounts_text)
        accounts_group.setLayout(accounts_layout)
        layout.addWidget(accounts_group)
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        self.settings_stack.addWidget(general_page)

        self.admin_page = self.build_admin_page()
        self.settings_stack.addWidget(self.admin_page)

    def build_admin_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("<b>Admin Data Management</b>")
        layout.addWidget(title)
        ai_group = QGroupBox("AI Extraction (Perplexity Agent API)")
        ai_layout = QFormLayout()
        self.gemini_key_input = QLineEdit(self.db.get_setting("perplexity_api_key", self.db.get_setting("gemini_api_key", self.db.get_setting("mistral_api_key", ""))))
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_row = QWidget()
        api_key_layout = QHBoxLayout(api_key_row)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.addWidget(self.gemini_key_input, 1)
        save_api_key_button = QPushButton("Save API Key")
        save_api_key_button.clicked.connect(self.save_api_key)
        api_key_layout.addWidget(save_api_key_button)
        ai_layout.addRow("Perplexity API Key:", api_key_row)
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)
        warning = QLabel("These actions are permanent. Select the receipt date, then confirm before deleting.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b71c1c;")
        layout.addWidget(warning)
        date_group = QGroupBox("Receipt Date")
        date_layout = QFormLayout(date_group)
        self.admin_date = QDateEdit(QDate.currentDate())
        self.admin_date.setCalendarPopup(True)
        self.admin_date.setDisplayFormat("dd-MMM-yyyy")
        date_layout.addRow("Select date:", self.admin_date)
        layout.addWidget(date_group)

        self.admin_receipt_data_button = QPushButton("Delete Receipt Data")
        self.admin_receipt_data_button.setToolTip("Delete database records and date-specific report files for the selected receipt date")
        self.admin_receipt_data_button.clicked.connect(self.delete_receipt_data)
        layout.addWidget(self.admin_receipt_data_button)
        self.admin_photo_button = QPushButton("Delete Receipt Photos")
        self.admin_photo_button.setToolTip("Delete receipt image files for the selected receipt date without deleting database records")
        self.admin_photo_button.clicked.connect(self.delete_receipt_photos)
        layout.addWidget(self.admin_photo_button)
        layout.addStretch()
        return page

    def open_admin_page(self):
        password, accepted = QInputDialog.getText(self, "Admin Access", "Enter admin password:", QLineEdit.EchoMode.Password)
        if not accepted:
            return
        if password != "123456":
            QMessageBox.warning(self, "Access Denied", "Incorrect admin password.")
            return
        self.settings_stack.setCurrentWidget(self.admin_page)

    def selected_admin_date(self):
        return self.admin_date.date().toPyDate()

    def admin_confirmation(self, title, message):
        result = QMessageBox.warning(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _cleanup_empty_export_folders(self):
        """Remove only empty date-named export folders under the application data folder."""
        app_data = os.path.join(os.path.expanduser("~"), ".instapay_receipts")
        if not os.path.isdir(app_data):
            return 0
        removed = 0
        for name in os.listdir(app_data):
            folder = os.path.join(app_data, name)
            if not os.path.isdir(folder):
                continue
            try:
                if not os.listdir(folder):
                    os.rmdir(folder)
                    removed += 1
            except OSError:
                # Ignore folders that contain files or are temporarily locked.
                continue
        return removed

    def _remove_export_files_for_date(self, date_str, include_zip=False):
        """Remove date-specific exports from every scan-date folder."""
        app_data = os.path.join(os.path.expanduser("~"), ".instapay_receipts")
        if not os.path.isdir(app_data):
            return 0
        removed = 0
        filenames = [f"Instapay_Receipts_{date_str}.xlsx"]
        if include_zip:
            filenames.append(f"Instapay_Receipts_Images_{date_str}.zip")
        for name in os.listdir(app_data):
            folder = os.path.join(app_data, name)
            if not os.path.isdir(folder):
                continue
            folder_has_selected_report = os.path.exists(
                os.path.join(folder, f"Instapay_Receipts_{date_str}.xlsx")
            )
            for filename in filenames:
                path = os.path.join(folder, filename)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        removed += 1
                    except OSError:
                        continue
            # A current-day ZIP can contain older receipt dates. If the selected
            # date report is in that scan folder, remove its batch image archive.
            if include_zip and (name == date_str or folder_has_selected_report):
                for filename in os.listdir(folder):
                    if filename.startswith("Instapay_Receipts_Images_") and filename.endswith(".zip"):
                        path = os.path.join(folder, filename)
                        try:
                            os.remove(path)
                            removed += 1
                        except OSError:
                            continue
        return removed

    def _selected_export_folder(self, target_date):
        app_data = os.path.join(os.path.expanduser("~"), ".instapay_receipts")
        return os.path.join(app_data, target_date.strftime("%d-%b-%Y"))

    @staticmethod
    def _remove_files(paths):
        removed = 0
        for path in paths:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    continue
        return removed

    def delete_receipt_data(self):
        target_date = self.selected_admin_date()
        date_str = target_date.strftime("%d-%b-%Y")
        export_folder = self._selected_export_folder(target_date)
        excel_files = []
        if os.path.isdir(export_folder):
            excel_files = [
                os.path.join(export_folder, name)
                for name in os.listdir(export_folder)
                if name.startswith("Instapay_Receipts_") and name.endswith(".xlsx")
            ]
        receipts = self.db.get_receipts_by_created_date(target_date)
        if not receipts and not excel_files:
            QMessageBox.information(self, "Nothing to Delete", f"No receipt data or Excel files were found in the {date_str} export folder.")
            return
        if not self.admin_confirmation("Confirm Excel and Receipt Data Deletion", f"Are you sure you want to delete all Excel report file(s) in the {date_str} folder and remove {len(receipts)} matching receipt record(s) from the database?"):
            return
        deleted = self.db.delete_receipts_by_ids([receipt["id"] for receipt in receipts])
        removed_reports = self._remove_files(excel_files)
        removed_folders = self._cleanup_empty_export_folders()
        QMessageBox.information(self, "Deletion Complete", f"Deleted {deleted} receipt record(s) from the database and {removed_reports} Excel file(s) from the {date_str} folder. Removed {removed_folders} empty folder(s). Receipt photos and ZIP archives were retained.")

    def delete_receipt_photos(self):
        target_date = self.selected_admin_date()
        date_str = target_date.strftime("%d-%b-%Y")
        export_folder = self._selected_export_folder(target_date)
        zip_files = []
        if os.path.isdir(export_folder):
            zip_files = [
                os.path.join(export_folder, name)
                for name in os.listdir(export_folder)
                if name.startswith("Instapay_Receipts_Images_") and name.endswith(".zip")
            ]
        receipts = self.db.get_receipts_by_created_date(target_date)
        if not receipts and not zip_files:
            QMessageBox.information(self, "Nothing to Delete", f"No receipt photos or ZIP archive was found in the {date_str} export folder.")
            return
        if not self.admin_confirmation("Confirm ZIP and Receipt Photo Deletion", f"Are you sure you want to delete the receipt-photo ZIP archive(s) in the {date_str} folder and remove the image references for {len(receipts)} receipt record(s) from the database?"):
            return
        removed_photos = 0
        for receipt in receipts:
            image_path = receipt.get("image_path")
            if image_path and os.path.isfile(image_path):
                removed_photos += self._remove_files([image_path])
        cleared_references = self.db.clear_image_paths_by_ids([receipt["id"] for receipt in receipts])
        removed_zips = self._remove_files(zip_files)
        removed_folders = self._cleanup_empty_export_folders()
        QMessageBox.information(self, "Photo Deletion Complete", f"Deleted {removed_photos} receipt photo file(s), removed {removed_zips} ZIP archive(s), and cleared image references for {cleared_references} database record(s) in the {date_str} folder. Removed {removed_folders} empty folder(s). Receipt transaction data was retained.")


    def load_recipients(self):
        self.recipient_table.blockSignals(True)
        recipients = self.db.get_email_recipients()
        self.recipient_table.setRowCount(len(recipients))
        for row, recipient in enumerate(recipients):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox.setCheckState(Qt.CheckState.Checked if recipient["enabled"] else Qt.CheckState.Unchecked)
            email_item = QTableWidgetItem(recipient["email"])
            email_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.recipient_table.setItem(row, 0, checkbox)
            self.recipient_table.setItem(row, 1, email_item)
        self.recipient_table.blockSignals(False)

    def recipient_checkbox_changed(self, row, column):
        if column == 0 and self.recipient_table.item(row, 1):
            item = self.recipient_table.item(row, 0)
            self.db.set_email_recipient_enabled(self.recipient_table.item(row, 1).text(), item.checkState() == Qt.CheckState.Checked)

    def add_email(self):
        import re
        email = self.email_input.text().strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return
        if any(item["email"] == email for item in self.db.get_email_recipients()):
            QMessageBox.information(self, "Already Added", "This email address is already in the recipient list.")
            return
        self.db.add_email_recipient(email, enabled=True)
        self.email_input.clear()
        self.load_recipients()

    def remove_checked_emails(self):
        emails = [self.recipient_table.item(row, 1).text() for row in range(self.recipient_table.rowCount()) if self.recipient_table.item(row, 0) and self.recipient_table.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not emails:
            QMessageBox.information(self, "No Selection", "Check the email addresses you want to remove.")
            return
        for email in emails:
            self.db.remove_email_recipient(email)
        self.load_recipients()

    def load_note_numbers(self):
        pairs = self.db.get_approved_note_pairs()
        self.note_numbers_list.setRowCount(len(pairs))
        for row, pair in enumerate(pairs):
            self.note_numbers_list.setItem(row, 0, QTableWidgetItem(pair["note_number"]))
            self.note_numbers_list.setItem(row, 1, QTableWidgetItem(pair["name"]))

    def add_note_number(self):
        import re
        number = self.note_number_input.text().strip()
        name = self.note_name_input.text().strip()
        if not re.fullmatch(r"\d+", number):
            QMessageBox.warning(self, "Invalid Note Number", "Please enter digits only.")
            return
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter the name corresponding to this Note Number.")
            return
        if number in self.db.get_approved_note_numbers():
            QMessageBox.information(self, "Already Added", "This Note Number is already approved.")
            return
        self.db.add_approved_note_number(number, name)
        generate_approved_note_numbers_report(self.db)
        self.note_number_input.clear()
        self.note_name_input.clear()
        self.load_note_numbers()

    def remove_note_number(self):
        row = self.note_numbers_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a Note Number to remove.")
            return
        item = self.note_numbers_list.item(row, 0)
        if item:
            self.db.remove_approved_note_number(item.text())
            generate_approved_note_numbers_report(self.db)
            self.load_note_numbers()

    def save_api_key(self):
        api_key = self.gemini_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Required", "Enter a Perplexity API key before saving.")
            self.gemini_key_input.setFocus()
            return
        self.db.set_setting("perplexity_api_key", api_key)
        QMessageBox.information(self, "API Key Saved", "The Perplexity API key was saved successfully.")

    def save_settings(self):
        self.db.set_setting("perplexity_api_key", self.gemini_key_input.text().strip())
        self.db.set_setting("outlook_recipient", ";".join(self.db.get_enabled_email_recipients()))
        entered = [line.strip() for line in self.accounts_text.toPlainText().splitlines() if line.strip()]
        current = {a["account_number"] for a in self.db.get_approved_accounts()}
        for account in current - set(entered):
            self.db.remove_approved_account(account)
        for account in entered:
            self.db.add_approved_account(account)
        QMessageBox.information(self, "Success", "Settings saved successfully.")
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.pending = []
        self.current_index = -1
        self.worker = None
        self.progress_dialog = None
        self.form_loading = False
        self.setWindowTitle("InstaPay Receipt Register - Multi-Photo Review")
        self.app_icon = QIcon(os.path.join(os.path.dirname(__file__), "ic_edita_logo.png"))
        self.setWindowIcon(self.app_icon)
        self.resize(1250, 850)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("""
            QWidget { background: #FBF5E5; color: #3F3F3F; font-size: 14px; }
            QLineEdit, QTextEdit { background: #FBF5E5; color: #3F3F3F; border: 1px solid #d8d0c0; border-radius: 5px; padding: 6px; font-size: 14px; }
            QGroupBox { background: #FBF5E5; color: #3F3F3F; border: 1px solid #d8d0c0; border-radius: 8px; margin-top: 10px; padding-top: 10px; font-size: 14px; }
            QGroupBox::title { color: #3F3F3F; subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background: #FBF5E5; color: #3F3F3F; border: 1px solid #d8d0c0; border-radius: 6px; padding: 9px 12px; font-size: 14px; }
            QPushButton:hover { background: #eee7d8; }
            QScrollArea { background: #FBF5E5; border: 1px solid #d8d0c0; }
            QScrollBar:vertical { background: #FBF5E5; width: 10px; margin: 3px 2px 3px 2px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #3F3F3F; min-height: 30px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #121212; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar:horizontal { background: #FBF5E5; height: 10px; margin: 2px 3px 2px 3px; border-radius: 5px; }
            QScrollBar::handle:horizontal { background: #3F3F3F; min-width: 30px; border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: #121212; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        """)
        main_layout = QHBoxLayout(central)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("""
            QFrame#sidebar { background-color: #121212; border-radius: 8px; }
            QFrame#sidebar QLabel { color: #F2E8D5; }
            QFrame#sidebar QPushButton { color: #F2E8D5; background-color: #121212; border: none; border-radius: 6px; padding: 11px; text-align: left; }
            QFrame#sidebar QPushButton:hover { background-color: #242424; color: #FFF8EA; }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 18)
        self.btn_select = QPushButton("  Select Receipt Images")
        self.btn_select.clicked.connect(self.select_images)
        sidebar_layout.addWidget(self.btn_select)
        self.btn_extract = QPushButton("  Extract Data")
        self.btn_extract.setEnabled(False)
        self.btn_extract.clicked.connect(self.extract_all)
        sidebar_layout.addWidget(self.btn_extract)
        btn_settings = QPushButton("  Settings")
        btn_settings.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(btn_settings)
        btn_data_folder = QPushButton("  Open Data Folder")
        btn_data_folder.clicked.connect(self.open_data_folder)
        sidebar_layout.addWidget(btn_data_folder)
        sidebar_layout.addStretch()
        self.btn_contact_us = QPushButton("  Contact Us")
        self.btn_contact_us.clicked.connect(self.show_contact_dialog)
        sidebar_layout.addWidget(self.btn_contact_us)
        main_layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 0, 0, 0)

        review_columns = QHBoxLayout()
        review_columns.setSpacing(12)

        fields_widget = QWidget()
        fields_widget.setFixedWidth(420)
        fields_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        fields_layout = QVBoxLayout(fields_widget)
        self.review_label = QLabel("<b>Review Selected Receipt</b><br><small>Click a thumbnail, compare the image, and correct the fields.</small>")
        self.review_label.setStyleSheet("font-size: 14px; color: #3F3F3F;")
        fields_layout.addWidget(self.review_label)
        form_group = QGroupBox("Selected Receipt Fields (Editable)")
        form_layout = QFormLayout()
        self.input_receipt_no = QLineEdit()
        self.lbl_receipt_err = QLabel()
        self.lbl_receipt_err.setStyleSheet("color: red;")
        form_layout.addRow("Receipt Number (Reference) *:", self.input_receipt_no)
        form_layout.addRow("", self.lbl_receipt_err)
        self.input_account_no = QLineEdit()
        self.lbl_account_err = QLabel()
        self.lbl_account_err.setStyleSheet("color: red;")
        form_layout.addRow("Account Number/Label *:", self.input_account_no)
        form_layout.addRow("", self.lbl_account_err)
        self.input_date = QLineEdit()
        self.lbl_date_err = QLabel()
        self.lbl_date_err.setStyleSheet("color: red;")
        form_layout.addRow("Receipt Date/Time *:", self.input_date)
        form_layout.addRow("", self.lbl_date_err)
        self.input_money = QLineEdit()
        self.lbl_money_err = QLabel()
        self.lbl_money_err.setStyleSheet("color: red;")
        form_layout.addRow("Money Value (EGP) *:", self.input_money)
        form_layout.addRow("", self.lbl_money_err)
        self.input_note = QLineEdit()
        self.lbl_note_err = QLabel()
        self.lbl_note_err.setStyleSheet("color: red;")
        self.lbl_note_info = QLabel()
        self.lbl_note_info.setStyleSheet("color: #6b7280;")
        self.note_completer_model = QStringListModel(self)
        self.note_completer = QCompleter(self.note_completer_model, self)
        self.note_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.note_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.note_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.input_note.setCompleter(self.note_completer)
        self.refresh_note_completer()
        self.input_note.textChanged.connect(self.update_note_lookup)
        form_layout.addRow("Note:", self.input_note)
        form_layout.addRow("", self.lbl_note_err)
        form_layout.addRow("", self.lbl_note_info)
        form_group.setLayout(form_layout)
        form_group.setFixedWidth(404)
        form_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        fields_layout.addWidget(form_group)
        self.btn_save_send = QPushButton("Save and Send")
        self.btn_save_send.setEnabled(False)
        self.btn_save_send.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_save_send.setStyleSheet("font-weight: bold; background-color: #121212; color: #F2E8D5; padding: 11px; border: 1px solid #3F3F3F;")
        self.btn_save_send.clicked.connect(self.save_and_send)
        fields_layout.addWidget(self.btn_save_send)
        fields_layout.addStretch()
        fields_logo = QLabel()
        fields_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QPixmap(os.path.join(os.path.dirname(__file__), "ic_edita_logo.png"))
        if not logo_pixmap.isNull():
            fields_logo.setPixmap(logo_pixmap.scaled(170, 125, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        fields_layout.addWidget(fields_logo)
        fields_copyright = QLabel("InstaPay Receipt Register © 2026 EDITA. All rights reserved.")
        fields_copyright.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fields_copyright.setWordWrap(True)
        fields_copyright.setStyleSheet("color: #3F3F3F; font-size: 9px; padding: 2px;")
        fields_layout.addWidget(fields_copyright)
        review_columns.addWidget(fields_widget, 3)

        preview_widget = QWidget()
        preview_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("<b>Receipt Image Preview</b>"))
        self.image_label = PreviewLabel("No images selected.\nClick 'Select Receipt Images' to begin.")
        self.image_label.setStyleSheet("border: 2px dashed #d8d0c0; background: #FBF5E5; color: #3F3F3F;")
        self.image_label.setMinimumWidth(470)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.image_label, 1)
        review_columns.addWidget(preview_widget, 5)

        thumbnails_widget = QWidget()
        thumbnails_layout = QVBoxLayout(thumbnails_widget)
        thumbnails_layout.addWidget(QLabel("<b>Selected Images</b>"))
        self.photo_scroll = QScrollArea()
        self.photo_scroll.setWidgetResizable(True)
        self.photo_scroll.setFixedWidth(175)
        self.photo_strip = QWidget()
        self.photo_layout = QVBoxLayout(self.photo_strip)
        self.photo_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.photo_scroll.setWidget(self.photo_strip)
        thumbnails_layout.addWidget(self.photo_scroll)
        review_columns.addWidget(thumbnails_widget, 2)

        content_layout.addLayout(review_columns)
        self.status_label = QLabel("Ready. Select multiple receipt images to begin.")
        content_layout.addWidget(self.status_label)
        main_layout.addWidget(content, stretch=1)

    def show_contact_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Contact Developer")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        dialog.setWindowOpacity(0.0)

        layout = QVBoxLayout(dialog)
        title = QLabel("<b>Contact Developer</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        fade_in = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        fade_in.setDuration(220)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        app_dir = os.path.dirname(os.path.abspath(__file__))
        contacts = [
            ("Whatsapp +20 120 185 7748", "ic_whatsapp.png", "https://wa.me/201201857748"),
            ("Facebook", "ic_facebook.png", "https://www.facebook.com/asd1558asd"),
            ("LinkedIn", "ic_linkedin.png", "https://www.linkedin.com/in/mina-remon"),
        ]
        for label, icon_name, url in contacts:
            link = QPushButton(label)
            link.setIcon(QIcon(os.path.join(app_dir, icon_name)))
            link.setIconSize(QSize(24, 24))
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setToolTip(f"Open {label} in your web browser")
            link.setStyleSheet("""
                QPushButton {
                    color: #3F3F3F;
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    text-align: center;
                    padding: 8px;
                }
                QPushButton:hover {
                    color: #FBF5E5;
                    background: #242424;
                }
                QPushButton:pressed {
                    background: #121212;
                }
            """)
            link.clicked.connect(lambda checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
            layout.addWidget(link)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        fade_out = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        fade_out.setDuration(180)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        def close_with_fade():
            close_button.setEnabled(False)
            fade_out.finished.connect(dialog.accept)
            fade_out.start()

        close_button.clicked.disconnect()
        close_button.clicked.connect(close_with_fade)
        dialog.show()
        fade_in.start()
        dialog.exec()

    def select_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Receipt Images", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not paths:
            return
        self.pending = [PendingReceipt(path) for path in paths]
        self.current_index = 0
        self.build_photo_strip()
        self.load_current_record()
        self.btn_extract.setEnabled(True)
        self.btn_save_send.setEnabled(False)
        self.status_label.setText(f"{len(paths)} receipt photos selected. Click Extract Data.")

    def build_photo_strip(self):
        while self.photo_layout.count():
            item = self.photo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, record in enumerate(self.pending):
            thumbnail = ReceiptThumbnail(record.image_path, record.status)
            thumbnail.clicked.connect(lambda i=index: self.select_record(i))
            self.photo_layout.addWidget(thumbnail)
        self.highlight_current_thumbnail()

    def highlight_current_thumbnail(self):
        for index in range(self.photo_layout.count()):
            widget = self.photo_layout.itemAt(index).widget()
            if not widget:
                continue
            record = self.pending[index]
            color = "#b7dfb9" if record.saved else ("#ffcdd2" if record.error else "#ffffff")
            border = "3px solid #1565c0" if index == self.current_index else "1px solid #999"
            widget.set_selected(index == self.current_index, color)
            widget.set_status(record.status)

    def select_record(self, index):
        if not 0 <= index < len(self.pending):
            return
        self.save_form_to_current()
        self.current_index = index
        self.load_current_record()
        self.highlight_current_thumbnail()

    @staticmethod
    def extract_note_number(note_text):
        import re
        match = re.search(r"\d+", str(note_text or ""))
        return match.group(0) if match else ""

    def resolve_note_fields(self, note_text, extracted_name="", extracted_number=""):
        """Resolve an approved Note number from either the extracted number or name."""
        import re
        note_text = str(note_text or "").strip()
        extracted_name = str(extracted_name or "").strip()
        number = re.sub(r"\D", "", str(extracted_number or "")) or self.extract_note_number(note_text)
        mapping = self.db.get_approved_note_mapping()

        # Any extracted number takes precedence; its approval is checked later
        # by Validator, and its corresponding name is never required.
        if number:
            return number, extracted_name

        # If the number is absent, match an approved name inside the extracted
        # Note name or complete Note text and infer the linked number.
        search_text = f"{extracted_name} {note_text}".casefold()
        matches = [
            (approved_number, name)
            for approved_number, name in mapping.items()
            if name and str(name).strip().casefold() in search_text
        ]
        if len(matches) == 1:
            resolved_number, resolved_name = matches[0]
            return resolved_number, resolved_name

        return number, extracted_name

    def refresh_note_completer(self):
        """Refresh autocomplete entries from the approved number/name pairs."""
        suggestions = [
            f"{pair['note_number']} — {pair['name']}"
            for pair in self.db.get_approved_note_pairs()
            if pair["name"]
        ]
        self.note_completer_model.setStringList(suggestions)

    def update_note_lookup(self, note_text):
        """Refresh Note autocomplete without displaying informational messages."""
        self.refresh_note_completer()
        self.lbl_note_info.clear()
        if str(note_text or "").strip() and self.note_completer_model.rowCount():
            self.note_completer.setCompletionPrefix(str(note_text).strip())
            self.note_completer.complete()

    def save_form_to_current(self):
        if self.form_loading or not 0 <= self.current_index < len(self.pending):
            return
        record = self.pending[self.current_index]
        note_number, note_name = self.resolve_note_fields(
            self.input_note.text(),
            record.data.get("note_name", ""),
            "",
        )
        self.update_note_lookup(self.input_note.text())
        record.data = {
            "receipt_number": self.input_receipt_no.text(),
            "account_number": self.input_account_no.text(),
            "receipt_date": self.input_date.text(),
            "money_value": self.input_money.text(),
            "note": self.input_note.text(),
            "note_name": note_name,
            "note_number": note_number,
        }

    def load_current_record(self):
        if not 0 <= self.current_index < len(self.pending):
            return
        record = self.pending[self.current_index]
        self.form_loading = True
        pixmap = QPixmap(record.image_path)
        if not pixmap.isNull():
            self.image_label.set_preview_pixmap(pixmap)
        else:
            self.image_label.clear_preview("Unable to display selected image.")
        self.input_receipt_no.setText(record.data.get("receipt_number", ""))
        self.input_account_no.setText(record.data.get("account_number", ""))
        self.input_date.setText(record.data.get("receipt_date", ""))
        self.input_money.setText(record.data.get("money_value", ""))
        self.input_note.setText(record.data.get("note", ""))
        resolved_number, resolved_name = self.resolve_note_fields(
            record.data.get("note", ""),
            record.data.get("note_name", ""),
            record.data.get("note_number", ""),
        )
        record.data["note_number"] = resolved_number
        record.data["note_name"] = resolved_name
        self.update_note_lookup(record.data.get("note", ""))
        self.clear_errors()
        if record.error:
            self.show_record_errors(record.error)
        self.form_loading = False
        self.review_label.setText(f"<b>Review Receipt {self.current_index + 1} of {len(self.pending)}</b><br><small>{os.path.basename(record.image_path)}</small>")
        self.btn_save_send.setEnabled(bool(self.pending) and not self.worker)

    def extract_all(self):
        if not self.pending:
            return
        api_key = self.db.get_setting("perplexity_api_key", self.db.get_setting("gemini_api_key", self.db.get_setting("mistral_api_key", ""))).strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Missing", "Please configure your Perplexity API Key in Admin Settings.")
            self.open_settings()
            return
        self.save_form_to_current()
        for record in self.pending:
            record.status = "Queued"
            record.error = ""
            record.saved = False
        self.build_photo_strip()
        self.btn_extract.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_save_send.setEnabled(False)
        self.progress_dialog = ExtractionProgressDialog(len(self.pending), self)
        self.progress_dialog.cancelled.connect(self.cancel_extraction)
        self.progress_dialog.show()
        self.status_label.setText("Extracting selected receipts...")
        self.worker = OcrBatchWorker([r.image_path for r in self.pending], api_key)
        self.worker.progress.connect(self.on_batch_progress)
        self.worker.completed.connect(self.on_receipt_extracted)
        self.worker.failed.connect(self.on_receipt_failed)
        self.worker.finished_all.connect(self.on_batch_finished)
        self.worker.start()

    def on_batch_progress(self, current, total, path):
        if self.progress_dialog:
            self.progress_dialog.update_progress(current - 1, os.path.basename(path))
        self.status_label.setText(f"Processing {current} of {total}: {os.path.basename(path)}")
        self.pending[current - 1].status = "Processing"
        self.highlight_current_thumbnail()

    def on_receipt_extracted(self, index, result):
        record = self.pending[index]
        record.data = {key: result.get(key, "") for key in ("receipt_number", "account_number", "receipt_date", "money_value", "note", "note_name", "note_number")}
        record.data["note_number"], record.data["note_name"] = self.resolve_note_fields(
            record.data.get("note", ""), record.data.get("note_name", ""), record.data.get("note_number", "")
        )
        record.raw_text = result.get("raw_text", "")
        record.status = "Ready"
        record.error = ""
        if self.progress_dialog:
            self.progress_dialog.update_progress(index + 1)
        if index == self.current_index:
            self.load_current_record()
        self.highlight_current_thumbnail()

    def on_receipt_failed(self, index, message):
        record = self.pending[index]
        record.status = "Extraction failed"
        record.error = message
        if self.progress_dialog:
            self.progress_dialog.update_progress(index + 1)
        if not record.data:
            record.data = {key: "" for key in ("receipt_number", "account_number", "receipt_date", "money_value", "note", "note_name", "note_number")}
        self.highlight_current_thumbnail()

    def on_batch_finished(self):
        if self.progress_dialog:
            self.progress_dialog.update_progress(len(self.pending))
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        self.btn_select.setEnabled(True)
        self.btn_extract.setEnabled(True)
        self.worker = None
        self.load_current_record()
        failed = sum(1 for r in self.pending if r.error)
        self.btn_save_send.setEnabled(failed == 0 and bool(self.pending))
        self.status_label.setText("Extraction complete. Review each thumbnail and correct fields before Save and Send.")
        if failed:
            first = next(i for i, r in enumerate(self.pending) if r.error)
            self.select_record(first)
            QMessageBox.warning(self, "Extraction Issues", f"{failed} photo(s) could not be extracted. The first failed photo is selected for review.")

    def clear_errors(self):
        for label in (self.lbl_receipt_err, self.lbl_account_err, self.lbl_date_err, self.lbl_money_err, self.lbl_note_err, self.lbl_note_info):
            label.clear()

    def show_record_errors(self, errors):
        if isinstance(errors, dict):
            self.lbl_receipt_err.setText(errors.get("receipt_number", ""))
            self.lbl_account_err.setText(errors.get("account_number", ""))
            self.lbl_date_err.setText(errors.get("receipt_date", ""))
            self.lbl_money_err.setText(errors.get("money_value", ""))
            self.lbl_note_err.setText(errors.get("note_number", ""))
        else:
            self.lbl_receipt_err.setText(str(errors))

    def validate_batch(self):
        self.save_form_to_current()
        errors_by_index = {}
        seen = {}
        for index, record in enumerate(self.pending):
            if record.saved:
                continue
            errors = Validator.validate_receipt_data(record.data, self.db)
            receipt_number = str(record.data.get("receipt_number", "")).strip()
            if receipt_number in seen:
                errors["receipt_number"] = "Receipt number is duplicated within this batch."
            elif receipt_number:
                seen[receipt_number] = index
            if errors:
                errors_by_index[index] = errors
        return errors_by_index

    def save_and_send(self):
        if self.worker or not self.pending:
            return
        errors_by_index = self.validate_batch()
        if errors_by_index:
            first_index = next(iter(errors_by_index))
            self.pending[first_index].error = errors_by_index[first_index]
            self.select_record(first_index)
            self.show_record_errors(errors_by_index[first_index])
            self.highlight_current_thumbnail()
            QMessageBox.warning(self, "Validation Failed", "The first receipt with an error has been selected. Correct the highlighted fields and click Save and Send again.")
            return
        try:
            for record in self.pending:
                if record.saved:
                    continue
                self.db.save_receipt(record.data["receipt_number"], record.data["account_number"], record.data["receipt_date"], record.data["money_value"], record.data.get("note", ""), record.image_path, record.raw_text, record.data.get("note_number", ""))
                record.saved = True
                record.status = "Saved"
                record.error = ""
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to save receipt batch:\n{exc}")
            return
        try:
            excel_paths, zip_path, folder_path, date_str = generate_daily_reports(self.db)
        except Exception as exc:
            QMessageBox.warning(self, "Report Warning", f"Receipts saved, but daily reports could not be generated:\n{exc}")
            self.highlight_current_thumbnail()
            return
        recipients = self.db.get_enabled_email_recipients()
        outlook_message = ""
        if recipients:
            try:
                OutlookService.send_excel_report(excel_paths, zip_path, recipients)
                outlook_message = f"\nOutlook opened with {len(excel_paths)} date-based Excel report(s) and the image ZIP attached for {len(recipients)} recipient(s)."
            except Exception as exc:
                outlook_message = f"\nOutlook could not be opened: {exc}"
        else:
            outlook_message = "\nNo recipients are checked in Settings; the reports were saved locally only."
        self.highlight_current_thumbnail()
        self.btn_save_send.setEnabled(False)
        QMessageBox.information(self, "Batch Saved", f"{len(self.pending)} receipt(s) saved in {folder_path}.{outlook_message}")
        self.status_label.setText(f"Batch saved successfully in {date_str}.")

    def open_settings(self):
        SettingsWindow(self.db, self).exec()

    def open_data_folder(self):
        app_data = os.path.join(os.path.expanduser("~"), ".instapay_receipts")
        os.makedirs(app_data, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(app_data)
        elif sys.platform == "darwin":
            os.system(f'open "{app_data}"')
        else:
            os.system(f'xdg-open "{app_data}"')

    def cancel_extraction(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("Extraction cancelled.")
            self.btn_select.setEnabled(True)
            self.btn_extract.setEnabled(True)
            self.btn_save_send.setEnabled(False)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(3000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "ic_edita_logo.png")))
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
