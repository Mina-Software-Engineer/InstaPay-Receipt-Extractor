package com.ic_edita.instapay

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class AzureSettingsStore(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(context, "azure_settings", MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(), EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV, EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
    fun endpoint(): String = prefs.getString(KEY_ENDPOINT, "")?.trim().orEmpty()
    fun apiKey(): String = prefs.getString(KEY_KEY, "").orEmpty()
    fun save(endpoint: String, apiKey: String) { prefs.edit().putString(KEY_ENDPOINT, endpoint.trim().trimEnd('/')).putString(KEY_KEY, apiKey.trim()).apply() }
    fun isConfigured(): Boolean = endpoint().isNotBlank() && apiKey().isNotBlank()
    fun isApprovedAccountsPasswordValid(candidate: String): Boolean = candidate == prefs.getString(KEY_ACCOUNTS_PASSWORD, INITIAL_ACCOUNTS_PASSWORD)
    fun saveApprovedAccountsPassword(password: String) { prefs.edit().putString(KEY_ACCOUNTS_PASSWORD, password).apply() }
    private companion object { const val KEY_ENDPOINT="azure_endpoint"; const val KEY_KEY="azure_api_key"; const val KEY_ACCOUNTS_PASSWORD="approved_accounts_password"; const val INITIAL_ACCOUNTS_PASSWORD="123456" }
}
