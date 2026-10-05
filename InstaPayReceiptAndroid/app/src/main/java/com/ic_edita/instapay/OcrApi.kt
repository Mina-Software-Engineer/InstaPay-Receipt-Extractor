package com.ic_edita.instapay

import okhttp3.RequestBody
import retrofit2.http.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Editable OCR candidates returned by the Azure Vision adapter. */
data class OcrField(
    val moneyValue: String = "",
    val accountNumber: String = "",
    val receiptNumber: String = "",
    val receiptDate: String = "",
    val note: String = "",
    val noteNumber: String = "",
    val noteName: String = "",
    val rawText: String = ""
)

interface OcrApi {
    @Headers("Content-Type: application/octet-stream")
    @POST("computervision/imageanalysis:analyze")
    suspend fun analyze(
        @Query("api-version") version: String = "2024-02-01",
        @Query("features") features: String = "read",
        @Header("Ocp-Apim-Subscription-Key") key: String,
        @Body image: RequestBody
    ): AzureAnalyzeResponse
}

data class AzureAnalyzeResponse(
    val readResult: AzureReadResult? = null,
    val read: AzureReadResult? = null,
    val content: String? = null,
    val error: AzureError? = null
)
data class AzureError(val code: String? = null, val message: String? = null)
data class AzureReadResult(val blocks: List<AzureBlock>? = null, val pages: List<AzurePage>? = null)
data class AzureBlock(val lines: List<AzureLine>? = null)
data class AzurePage(val lines: List<AzureLine>? = null)
data class AzureLine(val text: String? = null)

/** Kotlin port of services.py::OcrService._parse_instapay and helpers. */
object ReceiptOcrParser {
    private val arabicDigits = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹".zip("01234567890123456789").toMap()
    private val instapayHandle = Regex("(?:[A-Za-z0-9._-]+)?@instapay\\b", RegexOption.IGNORE_CASE)
    private val referenceLabel = Regex("(?:^|\\s)(?:reference|المرجع)\\s*[:：-]?", RegexOption.IGNORE_CASE)
    private val dateLabel = Regex("(?:^|\\s)(?:date|التاريخ)\\s*[:：-]?", RegexOption.IGNORE_CASE)
    private val noteLabel = Regex("(?:^|\\s)(?:note|ملاحظة)\\s*[:：-]?", RegexOption.IGNORE_CASE)
    private val toLabel = Regex("(?:^|\\s)(?:to|إلى|الى)\\s*[:：-]?", RegexOption.IGNORE_CASE)
    private val fromLabel = Regex("(?:^|\\s)(?:from|من)\\s*[:：-]?", RegexOption.IGNORE_CASE)
    private val anyFieldLabel = Regex("(?:reference|المرجع|date|التاريخ|note|ملاحظة)", RegexOption.IGNORE_CASE)

    fun parse(response: AzureAnalyzeResponse): OcrField {
        val lines = extractOcrLines(response)
        require(lines.isNotEmpty()) { "Azure Vision returned no readable text from the receipt image." }
        val data = parseInstapay(lines)
        val parsed = listOf(
            "money_value=${data.moneyValue}", "account_number=${data.accountNumber}",
            "receipt_number=${data.receiptNumber}", "receipt_date=${data.receiptDate}",
            "note=${data.note}", "note_number=${data.noteNumber}", "note_name=${data.noteName}"
        ).joinToString("; ")
        return data.copy(rawText = "Azure Vision OCR:\n${lines.joinToString("\n")}\n\nParsed fields:\n$parsed")
    }

    private fun extractOcrLines(payload: AzureAnalyzeResponse): List<String> {
        val readResult = payload.readResult ?: payload.read
        val blockLines = readResult?.blocks.orEmpty().flatMap { it.lines.orEmpty() }.mapNotNull { it.text.cleanOrNull() }
        if (blockLines.isNotEmpty()) return blockLines
        val pageLines = readResult?.pages.orEmpty().flatMap { it.lines.orEmpty() }.mapNotNull { it.text.cleanOrNull() }
        if (pageLines.isNotEmpty()) return pageLines
        return payload.content.orEmpty().lineSequence().mapNotNull { it.cleanOrNull() }.toList()
    }

    private fun parseInstapay(lines: List<String>): OcrField {
        val joinedDigits = lines.joinToString("\n").asciiDigits()
        val money = Regex("(\\d[\\d,]*(?:\\.\\d+)?)\\s*(?:EGP|جنيه|ج\\.م)", RegexOption.IGNORE_CASE)
            .find(joinedDigits)?.groupValues?.get(1)?.replace(",", "").orEmpty()
        val account = recipientAccount(lines)
        val receiptNumber = lineValue(lines, referenceLabel).first
        val receiptDate = lineValue(lines, dateLabel).first
        val note = stripEdges(lineValue(lines, noteLabel).first)
        val noteAscii = note.asciiDigits()
        val noteNumber = Regex("\\d[\\d\\s-]*").find(noteAscii)?.value?.filter(Char::isDigit).orEmpty()
        val noteName = note
            .filter { !it.isDigit() && it !in "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹" }
            .replace(Regex("[^\\w\\u0600-\\u06FF@ ._-]"), " ")
            .clean()
            .trim('-', '_', ':', ' ')
        return OcrField(money, account, stripEdges(receiptNumber), normalizeDate(receiptDate), note, noteNumber, noteName)
    }

    /** Same-line values support both normal and Arabic RTL OCR ordering. */
    private fun lineValue(lines: List<String>, label: Regex): Pair<String, Int> {
        lines.forEachIndexed { index, line ->
            val match = label.find(line) ?: return@forEachIndexed
            val before = stripEdges(line.substring(0, match.range.first))
            val after = stripEdges(line.substring(match.range.last + 1))
            val value = after.ifBlank { before }
            if (value.isNotBlank()) return value to index
            for (following in lines.drop(index + 1).take(2)) {
                if (following.isNotBlank() && !anyFieldLabel.containsMatchIn(following)) return stripEdges(following) to index
            }
            return "" to index
        }
        return "" to -1
    }

    private fun findLabelIndex(lines: List<String>, label: Regex): Int = lines.indexOfFirst { label.containsMatchIn(it) }

    /** Prefer the recipient To/إلى block and never select the sender From/من account. */
    private fun recipientAccount(lines: List<String>): String {
        val toIndex = findLabelIndex(lines, toLabel)
        if (toIndex >= 0) {
            var end = lines.size
            listOf(referenceLabel, dateLabel, noteLabel).forEach { marker ->
                val relative = findLabelIndex(lines.drop(toIndex + 1), marker)
                if (relative >= 0) end = minOf(end, toIndex + 1 + relative)
            }
            val candidates = lines.subList((toIndex + 1).coerceAtMost(lines.size), end.coerceAtLeast(toIndex + 1))
            val numeric = candidates.mapIndexed { position, candidate ->
                position to (candidate to candidate.asciiDigits().filter(Char::isDigit))
            }.filter { (_, pair) ->
                pair.second.length >= 8 && !Regex("(?:egp|جنيه|reference|date|note|التاريخ|المرجع|ملاحظة)", RegexOption.IGNORE_CASE).containsMatchIn(pair.first)
            }
            if (numeric.isNotEmpty()) return numeric.last().second.second
            candidates.firstOrNull { candidate ->
                instapayHandle.containsMatchIn(candidate)
            }?.let { handle ->
                instapayHandle.find(handle)?.value?.let { return it }
            }
            return ""
        }
        val instapayIndex = lines.indexOfFirst { instapayHandle.containsMatchIn(it) }
        if (instapayIndex >= 0) {
            instapayHandle.find(lines[instapayIndex])?.value?.let { return it }
        }
        return ""
    }

    private fun normalizeDate(raw: String): String {
        val value = stripEdges(raw).asciiDigits().replace(Regex("\\s+"), " ")
        if (value.isBlank()) return ""
        val formats = listOf(
            "dd MMM yyyy hh:mm a", "dd MMMM yyyy hh:mm a", "dd-MM-yyyy hh:mm a", "dd/MM/yyyy hh:mm a",
            "dd-MM-yyyy HH:mm", "dd/MM/yyyy HH:mm", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm"
        )
        formats.forEach { pattern -> parseDate(value, pattern)?.let { return formatDate(it) } }
        return value
    }

    private fun parseDate(value: String, pattern: String): Date? = try {
        SimpleDateFormat(pattern, Locale.ENGLISH).apply { isLenient = false }.parse(value)
    } catch (_: Exception) { null }

    private fun formatDate(value: Date): String = SimpleDateFormat("dd MMM yyyy hh:mm a", Locale.ENGLISH).format(value)
    private fun stripEdges(value: String): String = value.clean().trim(' ', ':', '：', '|', '-', '–', '—')
    private fun String.asciiDigits(): String = map { arabicDigits[it] ?: it }.joinToString("")
    private fun String?.cleanOrNull(): String? = this?.clean()?.takeIf { it.isNotBlank() }
    private fun String.clean(): String = replace(Regex("\\s+"), " ").trim()
}
