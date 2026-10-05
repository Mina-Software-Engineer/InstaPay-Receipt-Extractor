package com.ic_edita.instapay

import android.content.Context
import androidx.room.Room
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.LocalDateTime

class ReceiptRepository(context: Context) {
    private val db = Room.databaseBuilder(context, AppDatabase::class.java, "instapay.db").build()
    suspend fun validateAndSave(data: OcrField, imageUri: String): Result<Long> = withContext(Dispatchers.IO) {
        val admin = db.admin(); val receipts = db.receipts(); val errors = mutableListOf<String>()
        val money = data.moneyValue.replace(",", "").trim().toDoubleOrNull()
        if (data.receiptNumber.isBlank()) errors += "Receipt number is required."
        else if (receipts.exists(data.receiptNumber.trim())) errors += "Receipt number already exists."
        if (data.accountNumber.isBlank()) errors += "Account number or label is required."
        else if (!admin.accountApproved(data.accountNumber.trim())) errors += "Account is not in the approved accounts list."
        if (data.receiptDate.isBlank()) errors += "Receipt date and time is required."
        if (data.noteNumber.isBlank() || !data.noteNumber.all(Char::isDigit)) errors += "Note must contain a numeric approved number."
        else if (!admin.noteApproved(data.noteNumber.trim())) errors += "Note number is not approved."
        if (money == null || money <= 0) errors += "Money value must be greater than zero."
        if (errors.isNotEmpty()) return@withContext Result.failure(IllegalArgumentException(errors.joinToString("\n")))
        Result.success(receipts.insertReceipt(ReceiptEntity(receiptNumber=data.receiptNumber.trim(), accountNumber=data.accountNumber.trim(), receiptDate=data.receiptDate.trim(), moneyValue=money!!, note=data.note.trim(), noteNumber=data.noteNumber.trim(), imageUri=imageUri, rawOcrText=data.rawText, createdAt=LocalDateTime.now().toString())))
    }
}
