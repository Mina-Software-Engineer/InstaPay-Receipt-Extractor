package com.ic_edita.instapay

import android.content.Context
import android.net.Uri
import org.apache.poi.ss.usermodel.Workbook
import org.apache.poi.xssf.usermodel.XSSFWorkbook
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

data class ReportFiles(val excelFile: File, val imagesZip: File)

class ReportExporter(private val context: Context) {
    fun createVerifiedReport(data: OcrField, selectedUris: List<Uri>): ReportFiles {
        require(selectedUris.isNotEmpty()) { "No scanned receipt images are available for the report." }
        val directory = File(context.filesDir, "reports").apply { mkdirs() }
        val stamp = System.currentTimeMillis()
        val excel = File(directory, "instapay_receipts_$stamp.xlsx")
        val imagesZip = File(directory, "instapay_receipt_images_$stamp.zip")
        createWorkbook(excel, data)
        createImagesZip(imagesZip, selectedUris)
        return ReportFiles(excel, imagesZip)
    }

    private fun createWorkbook(file: File, data: OcrField) {
        val workbook: Workbook = XSSFWorkbook()
        workbook.use { book ->
            val sheet = book.createSheet("InstaPay Receipts")
            val headers = listOf("Date", "Value", "Client Code", "Receipt No")
            val headerRow = sheet.createRow(0)
            headers.forEachIndexed { index, value -> headerRow.createCell(index).setCellValue(value) }
            val row = sheet.createRow(1)
            listOf(formatReportDate(data.receiptDate), formatMoney(data.moneyValue), data.noteNumber, data.receiptNumber).forEachIndexed { index, value -> row.createCell(index).setCellValue(value) }
            headers.indices.forEach { sheet.autoSizeColumn(it) }
            FileOutputStream(file).use { output -> book.write(output) }
        }
    }

    private fun formatReportDate(value: String): String = try {
        val parsed = java.text.SimpleDateFormat("dd MMM yyyy hh:mm a", java.util.Locale.ENGLISH).parse(value)
        if (parsed == null) value else java.text.SimpleDateFormat("d-M-yyyy", java.util.Locale.ENGLISH).format(parsed)
    } catch (_: Exception) { value }

    private fun formatMoney(value: String): String = value.replace(",", "").toDoubleOrNull()?.let { amount ->
        if (amount % 1.0 == 0.0) "%,.0f".format(amount) else "%,.2f".format(amount).trimEnd('0').trimEnd('.')
    } ?: value

    private fun createImagesZip(file: File, uris: List<Uri>) {
        ZipOutputStream(FileOutputStream(file)).use { zip ->
            uris.distinct().forEachIndexed { index, uri ->
                val extension = when (context.contentResolver.getType(uri)?.lowercase()) {
                    "image/png" -> ".png"
                    "image/jpeg", "image/jpg" -> ".jpg"
                    "image/bmp" -> ".bmp"
                    "image/webp" -> ".webp"
                    else -> ".jpg"
                }
                zip.putNextEntry(ZipEntry("receipt_${index + 1}$extension"))
                context.contentResolver.openInputStream(uri)?.use { input -> input.copyTo(zip) }
                zip.closeEntry()
            }
        }
    }
}
