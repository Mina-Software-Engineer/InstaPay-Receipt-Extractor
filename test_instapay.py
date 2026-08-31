import os
import tempfile
import pytest
from database import Database
from reporting import Validator, generate_daily_reports
from services import OcrService

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path=path)
    yield db
    if os.path.exists(path):
        os.remove(path)

def test_approved_accounts(temp_db):
    assert temp_db.is_account_approved("123456") is False
    temp_db.add_approved_account("123456", "Test Account")
    assert temp_db.is_account_approved("123456") is True
    
    accounts = temp_db.get_approved_accounts()
    assert len(accounts) == 1
    assert accounts[0]["account_number"] == "123456"

    temp_db.remove_approved_account("123456")
    assert temp_db.is_account_approved("123456") is False

def test_validation_rules(temp_db):
    # Setup approved account
    temp_db.add_approved_account("BASEL TAMER")
    temp_db.add_approved_note_number("12345")

    # Test missing fields
    invalid_data = {
        "receipt_number": "",
        "account_number": "",
        "receipt_date": "",
        "money_value": "-10"
    }
    errors = Validator.validate_receipt_data(invalid_data, temp_db)
    assert "receipt_number" in errors
    assert "account_number" in errors
    assert "receipt_date" in errors
    assert "money_value" in errors

    # Test unapproved account and duplicate receipt number
    temp_db.save_receipt("957116232041", "BASEL TAMER", "01 Aug 2026 08:06 PM", 70.0, "Living Expenses", "", "")

    duplicate_data = {
        "receipt_number": "957116232041",
        "account_number": "UNAPPROVED",
        "receipt_date": "01 Aug 2026 08:06 PM",
        "money_value": "70.00"
    }
    errors = Validator.validate_receipt_data(duplicate_data, temp_db)
    assert "receipt_number" in errors  # duplicate
    assert "account_number" in errors  # unapproved

    # Test valid submission
    valid_data = {
        "receipt_number": "957116232042",
        "account_number": "BASEL TAMER",
        "receipt_date": "01 Aug 2026 08:06 PM",
        "money_value": "70.00",
        "note_number": "12345"
    }
    errors = Validator.validate_receipt_data(valid_data, temp_db)
    assert len(errors) == 0

def test_multiple_email_recipients(temp_db):
    temp_db.add_email_recipient("First@Example.com")
    temp_db.add_email_recipient("second@example.com", enabled=False)
    temp_db.add_email_recipient("FIRST@example.com")  # duplicate, case-insensitive

    recipients = temp_db.get_email_recipients()
    assert len(recipients) == 2
    assert temp_db.get_enabled_email_recipients() == ["first@example.com"]

    temp_db.set_email_recipient_enabled("second@example.com", True)
    assert temp_db.get_enabled_email_recipients() == ["first@example.com", "second@example.com"]

    temp_db.remove_email_recipient("FIRST@example.com")
    assert temp_db.get_enabled_email_recipients() == ["second@example.com"]


def test_note_number_rules(temp_db):
    temp_db.add_approved_note_number("00123")
    assert temp_db.is_note_number_approved("00123") is True
    assert temp_db.is_note_number_approved("99999") is False
    assert "note_number" in Validator.validate_receipt_data({
        "receipt_number": "R1",
        "account_number": "A",
        "receipt_date": "01 Aug 2026 08:06 PM",
        "money_value": "70",
        "note_number": ""
    }, temp_db)
    assert "note_number" in Validator.validate_receipt_data({
        "receipt_number": "R2",
        "account_number": "A",
        "receipt_date": "01 Aug 2026 08:06 PM",
        "money_value": "70",
        "note_number": "99999"
    }, temp_db)


def test_daily_reports_generation(temp_db):
    temp_db.add_approved_account("BASEL TAMER")
    temp_db.save_receipt("957116232041", "BASEL TAMER", "01 Aug 2026 08:06 PM", 70.0, "Living Expenses", "", "")
    
    excel_path, zip_path, folder_path, date_str = generate_daily_reports(temp_db)
    assert os.path.exists(excel_path)
    assert os.path.exists(zip_path)
    assert os.path.exists(folder_path)
