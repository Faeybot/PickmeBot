import os
import datetime
import html
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.database import DatabaseService
from services.notification import NotificationService

router = Router()

class UnmaskChatState(StatesGroup):
    typing_message = State()

def get_int_id(key: str):
    val = os.getenv(key)
    if val:
        val = str(val).strip().replace("'", "").replace('"', '')
        if val.startswith("-") or val.isdigit():
            try: return int(val)
            except: return val
    return val

CHAT_LOG_CHANNEL_ID = get_int_id("CHAT_LOG_CHANNEL_ID")
CHAT_LOG_GROUP_ID = get_int_id("CHAT_LOG_GROUP_ID")

# ==========================================
# 1. GERBANG MASUK UNMASK CHAT
# ==========================================
@router.callback_query(F.data.startswith("unmaskchat_"))
async def start_unmask_chat(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    parts = callback.data.split("_")
    target_id = int(parts[1])
    role = parts[2] 
    
    user_id = callback.from_user.id
    target = await db.get_user(target_id)
    viewer = await db.get_user(user_id)
    
    if not target: return await callback.answer("❌ Profil tidak ditemukan.", show_alert=True)

    if role == "target":
        await getattr(db, 'mark_notif_read', lambda u, s, t: None)(user_id, target_id, "UNMASK_CHAT")

    active_expiry = await getattr(db, 'get_active_chat_session', lambda u, t: None)(user_id, target_id)
    if not active_expiry or active_expiry < datetime.datetime.now().timestamp():
        return await callback.answer("⏳ Sesi Unmask 48 Jam telah berakhir!", show_alert=True)

    await state.update_data(chat_target_id=target_id, role=role, is_reply=False, thread_id=None)
    
    # ❌ TOMBOL BATALKAN DIHAPUS
    text_input = (
        f"🔓 <b>OBROLAN UNMASK (48 JAM)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Kirim pesan ke: <b>{target.full_name.upper()}</b>\n\n"
        f"<i>Ketik pesan Anda di bawah ini:</i>"
    )
    
    try: await callback.message.edit_caption(caption=text_input, reply_markup=None, parse_mode="HTML")
    except: pass
        
    await state.set_state(UnmaskChatState.typing_message)

@router.callback_query(F.data.startswith("unmaskreply_"))
async def reply_unmask_chat(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    parts = callback.data.split("_")
    target_id = int(parts[1])
    role = parts[2]
    thread_id = int(parts[3]) if parts[3] != "None" else None

    user_id = callback.from_user.id
    viewer = await db.get_user(user_id)
    
    if role == "target":
        await getattr(db, 'mark_notif_read', lambda u, s, t: None)(user_id, target_id, "UNMASK_CHAT")

    active_expiry = await getattr(db, 'get_active_chat_session', lambda u, t: None)(user_id, target_id)
    if not active_expiry or active_expiry < datetime.datetime.now().timestamp():
        return await callback.answer("⏳ Sesi Unmask 48 Jam telah berakhir!", show_alert=True)

    await state.update_data(chat_target_id=target_id, role=role, is_reply=True, thread_id=thread_id)
    
    # ❌ TOMBOL BATALKAN DIHAPUS. (Tetap menggunakan edit_caption agar UI tidak lompat)
    try: await callback.message.edit_caption(caption="🔓 <b>BALAS PESAN UNMASK</b>\n\nKetik balasan Anda:", reply_markup=None, parse_mode="HTML")
    except: pass
    await state.set_state(UnmaskChatState.typing_message)

# ==========================================
# 2. PROSES PENGIRIMAN PESAN
# ==========================================
@router.message(UnmaskChatState.typing_message)
async def process_unmask_message(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    # Auto Clean Chat
    try: await message.delete()
    except: pass

    if not message.text:
        msg = await message.answer("⚠️ Maaf, kirim teks saja.")
        await asyncio.sleep(2)
        try: await msg.delete()
        except: pass
        return

    data = await state.get_data()
    target_id = data.get('chat_target_id')
    role = data.get('role')
    is_reply = data.get('is_reply')
    thread_id = data.get('thread_id')
    
    sender_id = message.from_user.id
    sender = await db.get_user(sender_id)
    notif_service = NotificationService(bot, db)

    if role == "target":
        log_key = f"UnmaskReplyBonus_{sender_id}_{target_id}" 
        bonus_exists = await db.check_bonus_exists(log_key)
        if not bonus_exists:
            sukses_poin = await db.add_points_with_log(sender_id, 500, log_key)
            if sukses_poin:
                try: await message.answer("🎉 <b>BONGKAR ANONIM!</b>\nKamu mendapatkan <b>+500 Poin</b> karena membalas pesan Sultan.", parse_mode="HTML")
                except: pass

    try: 
        if role == "initiator": 
            await notif_service.trigger_new_message(target_id, sender_id, sender.full_name, False)
        else: 
            await notif_service.trigger_new_message(target_id, sender_id, sender.full_name, True)
    except: pass

    try:
        if not is_reply:
            log_text = f"🧵 <b>UNMASK CHAT</b>\nDari: <b>{sender.full_name}</b> ({role})\nKe: <code>{target_id}</code>\nIsi: <i>{html.escape(message.text)}</i>"
            if CHAT_LOG_CHANNEL_ID:
                msg_log = await bot.send_message(CHAT_LOG_CHANNEL_ID, log_text, parse_mode="HTML")
                thread_id = msg_log.message_id
        else:
            if CHAT_LOG_GROUP_ID and thread_id:
                log_reply = f"💬 <b>BALASAN UNMASK</b>\nDari: <code>{sender_id}</code> ➡️ <code>{target_id}</code>\nIsi: <i>{html.escape(message.text)}</i>"
                await bot.send_message(CHAT_LOG_GROUP_ID, log_reply, reply_to_message_id=thread_id, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Gagal Logging Admin Unmask: {e}")

    next_role = "target" if role == "initiator" else "initiator"
    
    if role == "initiator":
        header_msg = "🔓 SULTAN INGIN MENGOBROL"
        footer_msg = "🎁 <b>BONUS KLAIM:</b> Balas pesan ini untuk mendapatkan <b>+500 POIN</b>!"
    else:
        header_msg = f"💬 BALASAN DARI {sender.full_name.upper()}"
        footer_msg = "<i>Gunakan tombol di bawah untuk membalas. (Jalur Unmask 48 Jam)</i>"

    target_text_full = (
        f"<b>{header_msg}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>{html.escape(message.text)}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"{footer_msg}"
    )
    
    kb_target = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 BALAS PESAN", callback_data=f"unmaskreply_{sender_id}_{next_role}_{thread_id}")],
        [InlineKeyboardButton(text="👤 LIHAT PROFIL", callback_data=f"view_{sender_id}_public")]
    ])

    try:
        await bot.send_message(target_id, target_text_full, reply_markup=kb_target, parse_mode="HTML")
        
        # Edit pesan pengirim agar tahu pesan berhasil terkirim
        anchor_id = sender.anchor_msg_id
        await bot.edit_message_caption(
            chat_id=message.chat.id, 
            message_id=anchor_id, 
            caption=f"✅ <b>Pesan Unmask berhasil terkirim!</b>\n\n<i>{html.escape(message.text)}</i>\n\nSilakan gunakan navigasi di bawah untuk melanjutkan.",
            reply_markup=None, 
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer("❌ Gagal mengirim pesan. Target mungkin telah memblokir bot.")

    await state.clear()
