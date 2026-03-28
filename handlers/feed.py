import os
import html
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService, User
from utils.filters import is_content_safe 

router = Router()

# ==========================================
# 1. KONFIGURASI ID & VARIABEL LINGKUNGAN
# ==========================================
def get_int_id(key: str):
    val = os.getenv(key)
    if val and (val.startswith("-") or val.isdigit()):
        try: return int(val)
        except: return val
    return val

FEED_CHANNEL_ID = get_int_id("FEED_CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "") 
ADMIN_FEED_GROUP_ID = get_int_id("ADMIN_FEED_GROUP_ID")
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

class FeedState(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
    waiting_anon_choice = State()

INTEREST_MAP = {
    "int_adult": "#Adult🔞", "int_flirt": "#FlirtAndTalk🔥", "int_rel": "#Relationship❤️",
    "int_net": "#Networking🤝", "int_game": "#Gaming🎮", "int_travel": "#Traveling✈️", "int_coffee": "#Coffee☕"
}

# ==========================================
# 2. FORMATTER POSTINGAN (Dengan Deep Link)
# ==========================================
def format_feed_post(user: User, caption: str, is_anon: bool, bot_username: str):
    name_header = "🎭 <b>ANONIM</b>" if is_anon else f"👤 <b>{user.full_name.upper()}</b>"
    origin_flag = "anon" if is_anon else "public"
    link_profile = f"https://t.me/{bot_username}?start=view_{user.id}_{origin_flag}"
    
    header = f"{name_header} | <a href=\"{link_profile}\">[Lihat Profil]</a>"
    content = f"<blockquote><code><i>{html.escape(caption)}</i></code></blockquote>"
    
    city_name = user.location_name.replace(' ', '').title() if user.location_name else "Unknown"
    gender_name = user.gender.title() if user.gender else "Rahasia"
    
    interest_hashtags = [INTEREST_MAP.get(item.strip()) for item in (user.interests or "").split(",") if INTEREST_MAP.get(item.strip())]
    
    return f"{header}\n<code>{'—' * 20}</code>\n{content}\n\n📍 #{city_name} #{gender_name}\n🔥 {' '.join(interest_hashtags) if interest_hashtags else ''}"


# ==========================================
# 3. CORE UI RENDERER: FEED
# ==========================================
async def render_feed_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    """ Fungsi terpusat untuk menampilkan UI Feed dengan mode SPA """
    await state.clear()
    user = await db.get_user(user_id)
    if not user: return False

    # Tambahkan ke history navigasi
    await db.push_nav(user_id, "feed")
        
    text = (
        "📸 <b>MENU FEED & POSTING</b>\n"
        f"<code>{'—' * 20}</code>\n"
        "<i>Postingan teks akan terbit <b>OTOMATIS</b>.\nPostingan foto akan ditinjau <b>MANUAL</b> oleh Admin.</i>\n\n"
        f"📑 <b>Sisa Kuota Harian:</b>\n"
        f"📝 Teks: <b>{user.daily_feed_text_quota}</b> | 📸 Foto: <b>{user.daily_feed_photo_quota}</b>\n\n"
        f"📦 <b>Sisa Kuota Extra:</b>\n"
        f"📝 Teks: <b>{user.extra_feed_text_quota}</b> | 📸 Foto: <b>{user.extra_feed_photo_quota}</b>\n"
        f"<code>{'—' * 20}</code>\n"
        f"<i>Tips: VIP memiliki jatah posting harian lebih banyak!</i>"
    )
    
    ch_user = CHANNEL_USERNAME.replace('@','').strip() if CHANNEL_USERNAME else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 TULIS TEKS", callback_data="feed_ask_text"), 
         InlineKeyboardButton(text="📸 POSTING FOTO", callback_data="feed_ask_photo")],
        [InlineKeyboardButton(text="🚀 BOOSTER POSTINGAN", callback_data="menu_boost")],
        [InlineKeyboardButton(text="📺 PREVIEW CHANNEL", url=f"https://t.me/{ch_user}")],
        [InlineKeyboardButton(text="🔙 DASHBOARD SAYA", callback_data="back_to_dashboard")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    anchor_id = user.anchor_msg_id
    success_edit = False

    if anchor_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=kb)
            success_edit = True
        except Exception:
            pass

    if not success_edit:
        try:
            if anchor_id:
                try: await bot.delete_message(chat_id=chat_id, message_id=anchor_id)
                except: pass
            sent_message = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent_message.message_id)
        except Exception as e:
            logging.error(f"Gagal mengirim ulang Feed UI: {e}")

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass

    return True

# ==========================================
# 4. HANDLER MENU UTAMA FEED
# ==========================================
@router.callback_query(F.data == "menu_feed")
async def show_feed_menu(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_feed_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 5. HANDLER INPUT TEKS & FOTO
# ==========================================
@router.callback_query(F.data == "feed_ask_text")
async def feed_ask_text(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    user = await db.get_user(callback.from_user.id)
    if user.daily_feed_text_quota <= 0 and user.extra_feed_text_quota <= 0:
        return await callback.answer("❌ Kuota Teks Anda habis! Tunggu reset besok.", show_alert=True)
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ BATAL", callback_data="menu_feed")]])
    await callback.message.edit_caption(caption="📝 <b>Silakan ketik pesan/status yang ingin kamu posting:</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(FeedState.waiting_text)
    await callback.answer()

@router.message(FeedState.waiting_text)
async def handle_text_input(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass
    
    if not message.text: 
        msg = await message.answer("⚠️ Harap kirimkan teks saja.")
        await asyncio.sleep(2)
        try: await msg.delete()
        except: pass
        return

    user = await db.get_user(message.from_user.id)
    if user.daily_feed_text_quota <= 0 and user.extra_feed_text_quota <= 0: 
        return await bot.send_message(message.chat.id, "❌ Kuota Teks Anda habis!")
        
    await state.update_data(f_type="text", f_caption=message.text)
    await ask_anon_choice(user, state, bot, message.chat.id)

@router.callback_query(F.data == "feed_ask_photo")
async def feed_ask_photo(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    user = await db.get_user(callback.from_user.id)
    if user.daily_feed_photo_quota <= 0 and user.extra_feed_photo_quota <= 0:
        return await callback.answer("❌ Kuota Foto Anda habis! Tunggu reset besok.", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ BATAL", callback_data="menu_feed")]])
    await callback.message.edit_caption(caption="📸 <b>Kirim Foto berserta caption/keterangannya:</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(FeedState.waiting_photo)
    await callback.answer()

@router.message(FeedState.waiting_photo)
async def handle_photo_input(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass

    if not message.photo: 
        msg = await message.answer("⚠️ Mohon kirim sebuah foto.")
        await asyncio.sleep(2)
        try: await msg.delete()
        except: pass
        return

    user = await db.get_user(message.from_user.id)
    if user.daily_feed_photo_quota <= 0 and user.extra_feed_photo_quota <= 0: 
        return await bot.send_message(message.chat.id, "❌ Kuota Foto Anda habis!")
        
    await state.update_data(f_type="photo", f_file_id=message.photo[-1].file_id, f_caption=message.caption or "")
    await ask_anon_choice(user, state, bot, message.chat.id)

# ==========================================
# 6. PEMILIHAN ANONIM & EKSEKUSI
# ==========================================
async def ask_anon_choice(user: User, state: FSMContext, bot: Bot, chat_id: int):
    # Menggunakan anchor_msg_id dari database, bukan state
    anchor_id = user.anchor_msg_id
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 PUBLIK", callback_data="anon_no"), 
         InlineKeyboardButton(text="🎭 ANONIM", callback_data="anon_yes")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data="menu_feed")]
    ])
    
    text = "Bagaimana postingan ini ingin ditampilkan di Channel?"
    
    if anchor_id:
        try:
            await bot.edit_message_caption(chat_id=chat_id, message_id=anchor_id, caption=text, reply_markup=kb)
        except:
            pass
    await state.set_state(FeedState.waiting_anon_choice)

@router.callback_query(F.data.in_(["anon_yes", "anon_no"]), FeedState.waiting_anon_choice)
async def process_publish(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    is_anon = (callback.data == "anon_yes")
    data = await state.get_data()
    user_id = callback.from_user.id
    caption = data.get('f_caption', "")
    post_type = data.get('f_type')
    bot_info = await bot.get_me()

    if not is_content_safe(caption): 
        return await callback.answer("❌ Caption mengandung kata yang dilarang/tidak pantas!", show_alert=True)

    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        used_quota_type = ""
        
        # PRE-DEDUCT QUOTA
        if post_type == "text":
            if user.daily_feed_text_quota > 0: 
                user.daily_feed_text_quota -= 1
                used_quota_type = "daily_text"
            else: 
                user.extra_feed_text_quota -= 1
                used_quota_type = "extra_text"
        else:
            if user.daily_feed_photo_quota > 0: 
                user.daily_feed_photo_quota -= 1
                used_quota_type = "daily_photo"
            else: 
                user.extra_feed_photo_quota -= 1
                used_quota_type = "extra_photo"
        await session.commit()

        kb_back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 KEMBALI KE FEED", callback_data="menu_feed")]])

        if post_type == "text":
            full_post = format_feed_post(user, caption, is_anon, bot_info.username)
            await bot.send_message(FEED_CHANNEL_ID, full_post, parse_mode="HTML", disable_web_page_preview=True)
            await callback.message.edit_caption(caption="✅ <b>Postingan teks berhasil diterbitkan!</b>", reply_markup=kb_back, parse_mode="HTML")
            await state.clear()
        else:
            anon_tag = "1" if is_anon else "0"
            kb_admin = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ TERBITKAN", callback_data=f"apv_f_{user_id}_{anon_tag}"),
                InlineKeyboardButton(text="❌ TOLAK", callback_data=f"rej_f_{user_id}_{used_quota_type}")
            ]])
            admin_text = f"📸 <b>REVIEW FOTO FEED</b>\n👤 Pembuat: {user.full_name}\n🎭 Tampil: <b>{'ANON' if is_anon else 'PUBLIK'}</b>\n📝 <b>Caption:</b>\n{html.escape(caption)}"
            
            await bot.send_photo(ADMIN_FEED_GROUP_ID, photo=data['f_file_id'], caption=admin_text, reply_markup=kb_admin, parse_mode="HTML")
            await callback.message.edit_caption(caption="⏳ <b>Postingan foto sedang dalam tinjauan Admin.</b>\nJika ditolak, kuota akan dikembalikan.", reply_markup=kb_back, parse_mode="HTML")
            await state.clear()
    await callback.answer()

# ==========================================
# 7. MODERASI ADMIN (Approve / Reject)
# ==========================================
@router.callback_query(F.data.startswith("apv_f_"))
async def handle_approve_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    user_id, is_anon = int(parts[2]), (parts[3] == "1")
    user = await db.get_user(user_id)
    if not user: return await callback.answer("❌ User Hilang.")

    try:
        original_caption = callback.message.caption.split("📝 <b>Caption:</b>\n")[1].strip() if "📝 <b>Caption:</b>\n" in callback.message.caption else ""
        bot_info = await bot.get_me()
        full_post = format_feed_post(user, original_caption, is_anon, bot_info.username)
        
        await bot.send_photo(FEED_CHANNEL_ID, photo=callback.message.photo[-1].file_id, caption=full_post, parse_mode="HTML")
        try: await bot.send_message(user_id, "🎉 <b>POSTINGAN FOTO TERBIT!</b> Foto kamu telah disetujui admin.", parse_mode="HTML")
        except: pass
        
        await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ <b>APPROVED</b>", reply_markup=None)
    except Exception as e: 
        await callback.answer(f"Error: {e}", show_alert=True)

@router.callback_query(F.data.startswith("rej_f_"))
async def handle_reject_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    user_id, quota_info = int(parts[2]), parts[3] 
    
    async with db.session_factory() as session:
        u = await session.get(User, user_id)
        if u:
            if quota_info == "daily_photo": u.daily_feed_photo_quota += 1
            elif quota_info == "extra_photo": u.extra_feed_photo_quota += 1
            await session.commit()
            
    try: await bot.send_message(user_id, "❌ <b>POSTINGAN DITOLAK.</b>\nFoto kamu tidak memenuhi panduan komunitas. Kuota foto telah dikembalikan ke akunmu.", parse_mode="HTML")
    except: pass
    
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🔴 <b>REJECTED & REFUNDED</b>", reply_markup=None)
    await callback.answer("Ditolak & Refund Sukses.")
