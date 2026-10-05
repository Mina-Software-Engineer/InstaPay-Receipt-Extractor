package com.ic_edita.instapay

import android.content.ClipData
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.GravityCompat
import androidx.lifecycle.lifecycleScope
import coil.load
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.ic_edita.instapay.databinding.ActivityMainBinding
import kotlinx.coroutines.launch
import android.text.Editable
import android.text.TextWatcher

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val vm: MainViewModel by viewModels()
    private val pickReceipts=registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()){ uris -> if(uris.isNotEmpty()){ vm.select(uris); if(uris.size>1) toast("${uris.size} receipt images selected.") } }
    override fun onCreate(savedInstanceState:Bundle?){ super.onCreate(savedInstanceState); binding=ActivityMainBinding.inflate(layoutInflater); setContentView(binding.root); setSupportActionBar(binding.toolbar); bindActions(); lifecycleScope.launch { vm.state.collect { render(it) } } }
    private fun bindActions(){ binding.toolbar.setNavigationOnClickListener { binding.drawerLayout.openDrawer(GravityCompat.START) }; binding.selectButton.setOnClickListener { pickReceipts.launch(arrayOf("image/png","image/jpeg","image/bmp","image/webp")) }; binding.extractButton.setOnClickListener { vm.extract() }; binding.saveButton.setOnClickListener { vm.verifyAndSave() }; binding.sendButton.setOnClickListener { shareReport() }; listOf(binding.accountInput,binding.receiptNumberInput,binding.dateInput,binding.moneyInput,binding.noteInput).forEach { input -> input.addTextChangedListener(object:TextWatcher{ override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int)=Unit; override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int){ val f=vm.state.value.fields; vm.update(f.copy(accountNumber=binding.accountInput.text.toString(),receiptNumber=binding.receiptNumberInput.text.toString(),receiptDate=binding.dateInput.text.toString(),moneyValue=binding.moneyInput.text.toString(),note=binding.noteInput.text.toString())) }; override fun afterTextChanged(s:Editable?)=Unit }) }; binding.navigationView.setNavigationItemSelectedListener { item -> binding.drawerLayout.closeDrawer(GravityCompat.START); when(item.itemId){ R.id.nav_settings -> startActivity(Intent(this,SettingsActivity::class.java)); R.id.nav_contact -> MaterialAlertDialogBuilder(this).setTitle("Contact Developer").setMessage("Use the company-maintained WhatsApp, Facebook, or LinkedIn contact links here.\n\nVerified reports can be sent with the Android email share action.").setPositiveButton("OK",null).show(); R.id.nav_data_folder -> toast("Reports are stored privately and can be exported using Send Excel report."); R.id.nav_accounts,R.id.nav_notes,R.id.nav_recipients -> startActivity(Intent(this,SettingsActivity::class.java)) }; true } }
    private fun render(s:ReviewState){ binding.statusText.text=s.message; binding.extractButton.isEnabled=s.uri!=null&&!s.ocrRunning&&!s.verifying; binding.saveButton.isEnabled=s.canSave&&!s.ocrRunning&&!s.verifying; binding.sendButton.isEnabled=s.canSend&&!s.verifying; s.uri?.let { binding.receiptPreview.load(it) }; binding.accountInput.setTextIfChanged(s.fields.accountNumber); binding.receiptNumberInput.setTextIfChanged(s.fields.receiptNumber); binding.dateInput.setTextIfChanged(s.fields.receiptDate); binding.moneyInput.setTextIfChanged(s.fields.moneyValue); binding.noteInput.setTextIfChanged(s.fields.note); binding.rawOcrText.text=s.fields.rawText; binding.rawOcrText.visibility=if(s.fields.rawText.isBlank()) android.view.View.GONE else android.view.View.VISIBLE }
    private fun shareReport(){ val files=vm.generatedReport(); if(files==null){ toast("Verify and save a receipt before sending the report."); return }; val excelUri=FileProvider.getUriForFile(this, "${BuildConfig.APPLICATION_ID}.fileprovider", files.excelFile); val zipUri=FileProvider.getUriForFile(this, "${BuildConfig.APPLICATION_ID}.fileprovider", files.imagesZip); val attachments= arrayListOf(excelUri,zipUri); val send=Intent(Intent.ACTION_SEND_MULTIPLE).apply { type="*/*"; putParcelableArrayListExtra(Intent.EXTRA_STREAM,attachments); clipData=ClipData.newRawUri("InstaPay report",excelUri).apply { addItem(ClipData.Item(zipUri)) }; addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION); putExtra(Intent.EXTRA_SUBJECT,"InstaPay Receipts Report"); putExtra(Intent.EXTRA_TEXT,"Verified InstaPay receipt report and scanned receipt images are attached.") }; startActivity(Intent.createChooser(send,"Send report and receipt images")) }
    private fun toast(text:String)=Toast.makeText(this,text,Toast.LENGTH_LONG).show()
    private fun com.google.android.material.textfield.TextInputEditText.setTextIfChanged(value:String){ if(text?.toString()!=value) setText(value) }
}
