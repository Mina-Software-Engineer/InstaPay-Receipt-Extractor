package com.ic_edita.instapay

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ReviewState(val uri: Uri?=null, val fields: OcrField=OcrField(), val ocrRunning:Boolean=false, val verifying:Boolean=false, val message:String="Choose receipt images to begin.", val canSave:Boolean=false, val canSend:Boolean=false)

class MainViewModel(app: Application): AndroidViewModel(app) {
    private val repo=ReceiptRepository(app); private val ocr=AzureOcrRepository(app, AzureSettingsStore(app)); private val exporter=ReportExporter(app)
    private val _state=MutableStateFlow(ReviewState()); val state:StateFlow<ReviewState> = _state
    private var selectedUris: List<Uri> = emptyList()
    private var reportFiles: ReportFiles? = null

    fun selectedImages(): List<Uri> = selectedUris
    fun generatedReport(): ReportFiles? = reportFiles
    fun select(uris: List<Uri>){ selectedUris=uris; reportFiles=null; _state.value=ReviewState(uri=uris.firstOrNull(), message="${uris.size} receipt image(s) selected. Extract data to prepare editable suggestions.") }
    fun select(uri:Uri){ select(listOf(uri)) }
    fun extract(){ val uri=_state.value.uri ?: return; _state.value=_state.value.copy(ocrRunning=true, message="Reading receipt with Azure Vision…"); viewModelScope.launch { val result=ocr.extract(uri); _state.value=result.fold({ ReviewState(uri=uri, fields=it, message="OCR complete. Review and correct the suggestions before saving.", canSave=true) }, { _state.value.copy(ocrRunning=false, message=it.message ?: "Azure OCR failed.") }) } }
    fun update(fields:OcrField){ _state.value=_state.value.copy(fields=fields, canSave=true, canSend=false); reportFiles=null }
    fun verifyAndSave(){ val current=_state.value; val uri=current.uri ?: return; if(current.verifying) return; _state.value=current.copy(verifying=true, message="Verifying receipt data…"); viewModelScope.launch { val result=repo.validateAndSave(current.fields, uri.toString()); _state.value=result.fold({ savedId -> try { reportFiles=exporter.createVerifiedReport(current.fields, selectedUris); ReviewState(uri=uri, fields=current.fields, message="Receipt verified and saved. Excel report and receipt-image ZIP are ready to send.", canSend=true) } catch(error:Exception) { ReviewState(uri=uri, fields=current.fields, message="Receipt saved, but report creation failed: ${error.message}") } }, { ReviewState(uri=uri, fields=current.fields, message=it.message ?: "Validation failed.", canSave=true) }) } }
}
