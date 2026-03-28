import os
import datetime
import html
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from services.database import DatabaseService
from services.notification import NotificationService 

router = Router()

def get_int_id(key: str):
    val = os.getenv(key)
    if val:
        val = str(val).strip().replace("'", "").replace('"', '')
        if val.startswith("-") or val.isdigit():
            try: return int(val)
            except: return val
    return val

CHAT_LOG_GROUP_ID = get_int_id("CHAT_LOG_GROUP_ID")

class ChatState(StatesGroup):
    in_chat_room = State() 

# ==========================================
# 1. MASUK KE RUANG OBROLAN (GERBANG UTAMA & LOAD HISTORY)
# ==========================================
@router.callback_query(F.data.startswith("chat_"))
async def enter_chat_room(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    target_id = int(parts[1])
    origin = parts[2] if len(parts) >= 3 else "public"
    user_id = callback.from_user.id
    
    user = await db.get_user(user_id)
    target = await db.get_user(target_id)
    if not target: 
        return await callback.answer("❌ Profil tidak ditemukan.", show_alert=True)

    # 1. Cek Database Sesi
    session_data = await db.get_active_chat_session(user_id, target_id)
    now_ts = int(datetime.datetime.now().timestamp())
    
    is_active = session_data and session_data.expires_at > now_ts
    should_deduct = False
    
    # 2. Logika Gerbang Kuota (1x Potong per Sesi)
    if not is_active:
        if origin in ["public", "extend", "feed", "discovery"]:
            if not (user.is_vip or user.is_vip_plus):
                return await callback.answer("🔒 AKSES DITOLAK! Hanya VIP/VIP+ yang bisa memulai/memperpanjang obrolan.", show_alert=True)
            should_deduct = True
        elif origin in ["inbox", "match"]:
            should_deduct = False 
        
        if should_deduct:
            if user.daily_message_quota <= 0 and user.extra_message_quota <= 0:
                return await callback.answer("❌ Kuota Pesan Anda habis! Silakan tunggu reset besok.", show_alert=True)
            
            sukses = await db.use_message_quota(user_id)
            if not sukses: 
                return await callback.answer("Gagal memotong kuota.", show_alert=True)
            
            duration_hrs = 48 if user.is_vip_plus else 24
            new_expiry_ts = int((datetime.datetime.now() + datetime.timedelta(hours=duration_hrs)).timestamp())
            
            # Simpan / Perpanjang Sesi (Tetap simpan origin baru jika bertemu di tempat lain)
            await db.upsert_chat_session(user_id, target_id, new_expiry_ts, origin=origin)
            session_data = await db.get_active_chat_session(user_id, target_id)
    else:
        # Sesi masih aktif, tapi jika originnya baru (misal dari Match), kita timpa originnya.
        if origin not in ["inbox", "extend"]:
            await db.upsert_chat_session(user_id, target_id, session_data.expires_at, origin=origin)

    # 3. Hilangkan counter Notifikasi
    await getattr(db, 'mark_notif_read', lambda u, s, t: None)(user_id, target_id, "CHAT")
    
    # Kunci Posisi Navigasi agar Notifikasi tahu user sedang di ruang ini (Silent Notif)
    await db.push_nav(user_id, f"chat_room_{target_id}")

    # 4. Inisialisasi State FSM (Menyiapkan kantong sampah untuk Auto-Sweep)
    await state.update_data(chat_target_id=target_id, sweep_list=[])
    await state.set_state(ChatState.in_chat_room)
    
    # 5. Kirim Banner Ruang Obrolan
    reply_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ TUTUP OBROLAN")]], resize_keyboard=True)
    banner_text = (
        f"💬 <b>RUANG OBROLAN BERSAMA {target.full_name.upper()}</b>\n"
        f"<code>================================</code>\n"
        f"<i>Pintu terbuka. Semua yang kamu ketik akan langsung terkirim.</i>\n"
        f"<i>Riwayat akan dibersihkan dari layar saat kamu keluar, namun aman di Inbox.</i>\n\n"
        f"⬇️ <b>Ketik pesanmu sekarang:</b>"
    )
    
    # Bersihkan layar SPA dengan struktur Try-Except multi-baris yang aman
    try: 
        await callback.message.delete()
    except Exception: 
        pass
    
    banner_msg = await callback.message.answer(banner_text, reply_markup=reply_kb, parse_mode="HTML")
    
    # Tambahkan ID Banner ke daftar sapu bersih
    current_data = await state.get_data()
    sweep = current_data.get('sweep_list', [])
    sweep.append(banner_msg.message_id)
    await state.update_data(sweep_list=sweep)

    # 6. LOAD HISTORY DARI CHANNEL/GROUP (Restoration - MAX 20 PESAN TERAKHIR)
    if session_data and getattr(session_data, 'channel_msg_ids', []):
        recent_msgs = session_data.channel_msg_ids[-20:] # Anti-FloodWait Telegram Limit
        for msg_id in recent_msgs:
            if CHAT_LOG_GROUP_ID:
                try:
                    # Menggunakan copy_message agar pesan tampil seperti asli dari bot
                    copied = await bot.copy_message(chat_id=user_id, from_chat_id=CHAT_LOG_GROUP_ID, message_id=msg_id)
                    sweep.append(copied.message_id)
                except Exception: 
                    pass
        await state.update_data(sweep_list=sweep)
    
    await callback.answer()

# ==========================================
# 2. MESIN RUANG OBROLAN (REAL-TIME CHAT & AUTO-SWEEP)
# ==========================================
@router.message(ChatState.in_chat_room)
async def process_chat_room_message(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])

    # A. LOGIKA KELUAR RUANGAN (AUTO-SWEEP SPA)
    if message.text == "❌ TUTUP OBROLAN" or message.text == "/exit":
        await state.clear()
        
        # Bersihkan pesan input user
        try: 
            await message.delete()
        except Exception: 
            pass
        
        # Sapu bersih semua chat bubble di layar
        for msg_id in sweep_list:
            try: 
                await bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception: 
                pass
        
        # Arahkan kembali ke UI Inbox yang bersih
        from handlers.inbox import render_inbox_ui
        await render_inbox_ui(bot, message.chat.id, user_id, db)
        return

    # B. LOGIKA MENGIRIM PESAN
    if not message.text:
        msg = await message.answer("⚠️ Maaf, sistem ini hanya mendukung pesan teks.")
        sweep_list.append(msg.message_id)
        await state.update_data(sweep_list=sweep_list)
        try: 
            await message.delete() 
        except Exception: 
            pass
        return

    target_id = data.get('chat_target_id')
    sender = await db.get_user(user_id)
    
    # 1. Hapus input asli user agar rapi
    try: 
        await message.delete()
    except Exception: 
        pass

    # 2. Render ulang input user sebagai "Bubble Bot" agar seragam
    bubble_msg = await message.answer(f"👤 <b>Anda:</b>\n{html.escape(message.text)}", parse_mode="HTML")
    sweep_list.append(bubble_msg.message_id)
    await state.update_data(sweep_list=sweep_list)

    # 3. Validasi Expiry (Jaga-jaga jika sesi habis saat asyik mengetik)
    session_data = await db.get_active_chat_session(user_id, target_id)
    now_ts = int(datetime.datetime.now().timestamp())
    if not session_data or session_data.expires_at < now_ts:
        warn_msg = await message.answer("⏳ Waktu obrolan telah berakhir. Silakan keluar dan perpanjang sesi dari Inbox.")
        sweep_list.append(warn_msg.message_id)
        await state.update_data(sweep_list=sweep_list)
        return

    # 4. LOGGING KE GRUP (SEBAGAI DATABASE)
    saved_msg_id = None
    if CHAT_LOG_GROUP_ID:
        try:
            log_text = f"🗄 <b>[{session_data.origin.upper()}]</b>\nDari: <code>{user_id}</code> ➡️ <code>{target_id}</code>\nIsi:\n<i>{html.escape(message.text)}</i>"
            saved_log = await bot.send_message(CHAT_LOG_GROUP_ID, log_text, parse_mode="HTML")
            saved_msg_id = saved_log.message_id
        except Exception as e:
            logging.error(f"Gagal Simpan History ke Grup: {e}")

    # 5. UPDATE DATABASE SQL (Simpan ID Pesan Grup & Cuplikan Terakhir)
    await db.upsert_chat_session(user_id, target_id, session_data.expires_at, last_message=message.text, new_channel_msg_id=saved_msg_id)

    # 6. LOGIKA DISTRIBUSI POIN & NOTIF (Didasarkan pada Origin)
    target_session = await db.get_active_chat_session(target_id, user_id)
    origin_type = target_session.origin if target_session else session_data.origin
    
    # Target membalas (Penerima awal membalas inisiator)
    if origin_type == "unmask":
        log_key = f"UnmaskReplyBonus_{user_id}_{target_id}"
        if not await db.check_bonus_exists(log_key):
            await db.add_points_with_log(user_id, 500, log_key)
            bonus_msg = await message.answer("🎉 <b>BONGKAR ANONIM!</b> Anda mendapat <b>+500 Poin</b> karena membalas.")
            sweep_list.append(bonus_msg.message_id)
            await state.update_data(sweep_list=sweep_list)
            
    elif origin_type in ["public", "feed", "discovery"]:
        log_key = f"ChatReplyBonus_{user_id}_{target_id}"
        if not await db.check_bonus_exists(log_key):
            await db.add_points_with_log(user_id, 200, log_key)
            bonus_msg = await message.answer("🎉 <b>INTERAKSI BARU!</b> Anda mendapat <b>+200 Poin</b>.")
            sweep_list.append(bonus_msg.message_id)
            await state.update_data(sweep_list=sweep_list)

    # 7. KIRIM PESAN KE TARGET
    target_user = await db.get_user(target_id)
    kasta = "💎 VIP+" if sender.is_vip_plus else "🌟 VIP" if sender.is_vip else "👤 FREE"
    
    # Cek apakah target sedang ada di ruang obrolan dengan user ini (Silent Receive)
    if target_user.nav_stack and target_user.nav_stack[-1] == f"chat_room_{user_id}":
        try:
            # Kirim langsung sebagai bubble chat tanpa tombol
            await bot.send_message(target_id, f"👤 <b>{sender.full_name.upper()}:</b>\n{html.escape(message.text)}", parse_mode="HTML")
        except Exception: 
            pass
    else:
        # Target tidak di ruang chat, kirim pesan notifikasi biasa
        target_text = (
            f"💬 <b>PESAN BARU ({kasta})</b>\n"
            f"Dari: <b>{sender.full_name.upper()}</b>\n"
            f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
            f"<i>{html.escape(message.text)}</i>\n"
            f"<code>━━━━━━━━━━━━━━━━━━</code>"
        )
        try:
            await bot.send_message(target_id, target_text, parse_mode="HTML")
            notif_service = NotificationService(bot, db)
            await notif_service.trigger_new_message(target_id, user_id, sender.full_name, True)
        except Exception:
            pass
