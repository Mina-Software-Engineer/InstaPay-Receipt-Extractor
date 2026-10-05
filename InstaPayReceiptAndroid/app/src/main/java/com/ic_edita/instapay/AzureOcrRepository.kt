package com.ic_edita.instapay

import android.content.Context
import android.net.Uri
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class AzureOcrRepository(private val context: Context, private val settings: AzureSettingsStore) {
    suspend fun extract(uri: Uri): Result<OcrField> = withContext(Dispatchers.IO) {
        try {
            val endpoint = settings.endpoint(); val key = settings.apiKey()
            require(endpoint.isNotBlank() && key.isNotBlank()) { "Azure Vision API key and endpoint are not configured. Add them in Settings." }
            require(endpoint.startsWith("https://")) { "Azure Vision endpoint must start with https://" }
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: error("Receipt image could not be opened.")
            val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"
            val api = Retrofit.Builder().baseUrl("$endpoint/").addConverterFactory(GsonConverterFactory.create()).build().create(OcrApi::class.java)
            val response = try { api.analyze(key = key, image = bytes.toRequestBody(mime.toMediaType())) } catch (http: HttpException) {
                throw RuntimeException("Azure Vision request failed with HTTP ${http.code()}: ${azureError(http)}")
            }
            val serviceError = response.error?.message ?: response.error?.code
            require(serviceError.isNullOrBlank()) { "Azure Vision request failed: $serviceError" }
            Result.success(ReceiptOcrParser.parse(response))
        } catch (e: Exception) {
            Result.failure(RuntimeException("Azure Vision OCR extraction failed: ${e.message ?: "unknown error"}", e))
        }
    }

    private fun azureError(http: HttpException): String {
        val body = http.response()?.errorBody()?.string().orEmpty()
        if (body.isBlank()) return http.message()
        return try {
            val error = Gson().fromJson(body, AzureAnalyzeResponse::class.java).error
            error?.message ?: error?.code ?: body.take(1000)
        } catch (_: Exception) { body.take(1000) }
    }
}
