package com.ic_edita.instapay

import android.content.Context
import android.net.Uri
import org.apache.poi.ss.usermodel.DataFormatter
import org.apache.poi.ss.usermodel.WorkbookFactory

 data class ApprovedNotesImportResult(val validNotes: List<ApprovedNote>, val rowsInspected: Int, val duplicateCount: Int, val invalidRowCount: Int, val warnings: List<String>)

class ApprovedNotesExcelImporter(private val context: Context) {
    private val arabicDigits = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹".zip("01234567890123456789").toMap()
    fun import(uri: Uri): ApprovedNotesImportResult {
        val formatter = DataFormatter(); val notes = linkedMapOf<String, ApprovedNote>(); val warnings=mutableListOf<String>(); var inspected=0; var duplicates=0; var invalid=0
        context.contentResolver.openInputStream(uri).use { stream -> requireNotNull(stream) { "Could not open the selected Excel file." }; WorkbookFactory.create(stream).use { workbook ->
            val sheet=workbook.getSheetAt(0) ?: error("The workbook contains no worksheet."); val firstRow=sheet.firstRowNum; val lastRow=sheet.lastRowNum
            for(rowIndex in firstRow..lastRow){ val row=sheet.getRow(rowIndex) ?: continue; val numberRaw=formatter.formatCellValue(row.getCell(0)).trim(); val name=formatter.formatCellValue(row.getCell(1)).trim(); if(rowIndex==firstRow && isHeader(numberRaw)) continue; inspected++; val number=normalize(numberRaw); if(number.isBlank()){ if(numberRaw.isNotBlank()){ invalid++; warnings += "Row ${rowIndex+1}: invalid Note number '$numberRaw'." }; continue }; if(notes.containsKey(number)){ duplicates++; continue }; notes[number]=ApprovedNote(number,name) }
        } }
        return ApprovedNotesImportResult(notes.values.toList(), inspected, duplicates, invalid, warnings)
    }
    private fun isHeader(value:String)=value.lowercase().replace(Regex("[^a-z]"),"") in setOf("notenumber","note","approvednotenumber","approvednote")
    private fun normalize(value:String):String=value.map { arabicDigits[it] ?: it }.joinToString("").replace(",","").trim().takeIf { it.isNotBlank() && it.all(Char::isDigit) }.orEmpty()
}
