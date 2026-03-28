import os
import html
import datetime
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# ==========================================
# CORE UI RENDERER: INBOX
# ==========================================
async def render_inbox_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    # Kunci state navigasi
    await db.push_nav(user_id, "inbox")

    # Ambil SEMUA sesi dari database (Sistem tidak pernah menghapus history)
    sessions = await db.get_inbox_sessions(user_id)

    text_content = "<b>📥 INBOX PESAN & HISTORI</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"

    kb_buttons = []

    if not sessions:
        text_content += "<i>Belum ada riwayat percakapan. Mulai sapa seseorang di Discovery atau Feed!</i>"
    else:
        now = int(datetime.datetime.now().timestamp())
        
        for i, sess in enumerate(sessions, 1):
            counterpart_id = sess.target_id if sess.user_id == user_id else sess.user_id
            counterpart = await db.get_user(counterpart_id)
            if not counterpart: continue
            
            name = counterpart.full_name
            is_active = sess.expires_at > now
            
            # Label Origin & Poin
            origin = getattr(sess, 'origin', 'public')
            if origin == "unmask":
                jalur_info = "[Jalur VIP+] 🎁 +500 Poin"
            elif origin == "match":
                jalur_info = "[Jalur Match] 🆓 Gratis"
            else:
                jalur_info = "[Jalur Publik] 🎁 +200 Poin"
            
            snippet = sess.last_message[:25] + "..." if sess.last_message else "Belum ada pesan."
            snippet = html.escape(snippet)
            
            if is_active:
                exp_date = datetime.datetime.fromtimestamp(sess.expires_at).strftime("%d/%m %H:%M")
                text_content += f"{i}. 🟢 <b>{name}</b> (Aktif s/d {exp_date})\n🏷 <i>{jalur_info}</i>\n💬 <i>\"{snippet}\"</i>\n\n"
                kb_buttons.append([InlineKeyboardButton(text=f"💬 Buka Obrolan dgn {name}", callback_data=f"chat_{counterpart_id}_inbox")])
            else:
                text_content += f"{i}. 🔴 <b>{name}</b> (Sesi Habis)\n🏷 <i>{jalur_info}</i>\n💬 <i>\"{snippet}\"</i>\n\n"
                kb_buttons.append([InlineKeyboardButton(text=f"🔒 Buka Kembali dgn {name}", callback_data=f"chat_{counterpart_id}_extend")])
                
        text_content += "<i>Pesan dengan tanda 🔴 membutuhkan 1 Kuota Pesan untuk dibuka kembali selama 24 Jam.</i>"

    # ❌ TOMBOL BACK/DASHBOARD DIHAPUS (Hanya daftar chat)
    kb_nav = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    anchor_id = user.anchor_msg_id

    try:
        await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=kb_nav)
    except Exception:
        pass

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

@router.callback_query(F.data == "menu_inbox")
async def show_inbox(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_inbox_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)
