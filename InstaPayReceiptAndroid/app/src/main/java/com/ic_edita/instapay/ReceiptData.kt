package com.ic_edita.instapay

import androidx.room.*

@Entity(tableName = "receipts", indices = [Index(value = ["receiptNumber"], unique = true)])
data class ReceiptEntity(@PrimaryKey(autoGenerate = true) val id: Long = 0, val receiptNumber: String, val accountNumber: String, val receiptDate: String, val moneyValue: Double, val note: String, val noteNumber: String, val imageUri: String, val rawOcrText: String, val createdAt: String)
@Entity(tableName = "approved_accounts") data class ApprovedAccount(@PrimaryKey val accountNumber: String, val description: String = "")
@Entity(tableName = "approved_notes") data class ApprovedNote(@PrimaryKey val noteNumber: String, val name: String = "")
@Entity(tableName = "recipients") data class Recipient(@PrimaryKey val email: String, val enabled: Boolean = true)
@Entity(tableName = "settings") data class Setting(@PrimaryKey val key: String, val value: String)

@Dao interface ReceiptDao { @Insert fun insertReceipt(receipt: ReceiptEntity): Long; @Query("SELECT EXISTS(SELECT 1 FROM receipts WHERE receiptNumber=:number)") fun exists(number: String): Boolean; @Query("SELECT * FROM receipts ORDER BY createdAt DESC") fun all(): List<ReceiptEntity> }
@Dao interface AdminDao { @Query("SELECT * FROM approved_accounts ORDER BY accountNumber") fun accounts(): List<ApprovedAccount>; @Insert(onConflict=OnConflictStrategy.REPLACE) fun addAccount(item: ApprovedAccount); @Delete fun removeAccount(item: ApprovedAccount); @Query("SELECT EXISTS(SELECT 1 FROM approved_accounts WHERE accountNumber=:value)") fun accountApproved(value: String): Boolean; @Query("SELECT * FROM approved_notes ORDER BY noteNumber") fun notes(): List<ApprovedNote>; @Insert(onConflict=OnConflictStrategy.IGNORE) fun addNotes(items: List<ApprovedNote>); @Insert(onConflict=OnConflictStrategy.REPLACE) fun addNote(item: ApprovedNote); @Delete fun removeNote(item: ApprovedNote); @Query("SELECT EXISTS(SELECT 1 FROM approved_notes WHERE noteNumber=:value)") fun noteApproved(value: String): Boolean; @Query("SELECT * FROM recipients ORDER BY email") fun recipients(): List<Recipient>; @Insert(onConflict=OnConflictStrategy.REPLACE) fun addRecipient(item: Recipient); @Delete fun removeRecipient(item: Recipient); @Query("UPDATE recipients SET enabled=:enabled WHERE email=:email") fun setRecipient(email: String, enabled: Boolean); @Query("SELECT email FROM recipients WHERE enabled=1") fun enabledRecipients(): List<String> }
@Database(entities=[ReceiptEntity::class, ApprovedAccount::class, ApprovedNote::class, Recipient::class, Setting::class], version=1, exportSchema=false) abstract class AppDatabase: RoomDatabase() { abstract fun receipts(): ReceiptDao; abstract fun admin(): AdminDao }
