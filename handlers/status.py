import logging
import os
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# ==========================================
# 0. CORE UI RENDERER: STATUS
# ==========================================
async def render_status_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    # Kunci state navigasi
    await db.push_nav(user_id, "status")

    # --- 1. LOGIKA KASTA & STATUS ---
    status_akun = "🎭 PREMIUM VERIFIED" if user.is_premium else "👤 FREE USER"
    
    if user.is_vip_plus:
        status_sub = "💎 VIP+"
        masa_aktif = "Aktif (Sultan Eksklusif)"
    elif user.is_vip:
        status_sub = "🌟 VIP"
        masa_aktif = "Aktif (Sultan)"
    else:
        status_sub = "FREE"
        masa_aktif = "Seumur Hidup"

    # --- 2. LOGIKA TIKET BOOST ---
    free_boost = getattr(user, 'weekly_free_boost', 0)
    paid_boost = getattr(user, 'paid_boost_balance', 0)
    total_boost = free_boost + paid_boost

    # --- 3. TAMPILAN PESAN ---
    text = (
        f"📊 <b>STATUS AKUN & POTENSI CUAN</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"💎 <b>Status Akun:</b> {status_akun}\n"
        f"👑 <b>Status Langganan:</b> {status_sub}\n"
        f"📅 <b>Masa Aktif:</b> {masa_aktif}\n\n"
        
        f"📑 <b>Sisa Kuota Harian</b>\n"
        f"📝 Post Teks: <b>{user.daily_feed_text_quota}</b>\n"
        f"📸 Post Foto: <b>{user.daily_feed_photo_quota}</b>\n"
        f"💬 Kirim Pesan: <b>{user.daily_message_quota}</b>\n"
        f"🔍 Buka Profil: <b>{user.daily_open_profile_quota}</b>\n"
        f"🎭 Bongkar Anonim: <b>{'✅ AKTIF' if user.is_vip_plus else '❌ TERKUNCI'}</b>\n"
        f"<i>(Reset otomatis setiap pukul 00:00 WIB)</i>\n\n"
        
        f"💰 <b>POTENSI POIN (TALENT)</b>\n"
        f"👀 Profil Diintip: <b>+100 Poin</b>\n"
        f"📩 Pesan Masuk: <b>+100 Poin</b>\n"
        f"🎁 <b>Bonus Balas Chat:</b> <b>+200 Poin</b>\n"
        f"💖 Dibongkar VIP+ (Unmask): <b>+500 Poin</b>\n"
        f"🎁 <b>Bonus Balas Unmask:</b> <b>+500 Poin</b>\n"
        f"<i>(Konversi: 10 Poin = Rp 1)</i>\n\n"
        
        f"🚀 <b>Tiket Boost (Prioritas Feed)</b>\n"
        f"🎁 Boost Mingguan: <b>{free_boost}</b>\n"
        f"🎫 Boost Berbayar: <b>{paid_boost}</b>\n\n"
        
        f"📦 <b>Sisa Kuota Extra (Permanen)</b>\n"
        f"💬 Extra Pesan: <b>{getattr(user, 'extra_message_quota', 0)}</b>\n"
        f"🔍 Extra Buka Profil: <b>{getattr(user, 'extra_open_profile_quota', 0)}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Semakin rajin balas pesan, semakin cepat cuan cair!</i>"
    )

    # --- 4. TOMBOL NAVIGASI ---
    # ❌ TOMBOL BACK/DASHBOARD DIHAPUS
    kb = [
        [InlineKeyboardButton(text="💎 UPGRADE KASTA & VIP", callback_data="menu_pricing")],
        [
            InlineKeyboardButton(text="🚀 BELI BOOST", callback_data="buy_boost"),
            InlineKeyboardButton(text="🛒 BELI KUOTA", callback_data="buy_quota")
        ]
    ]
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    anchor_id = user.anchor_msg_id

    try:
        await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=markup)
    except Exception:
        pass

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

# --- HANDLER UTAMA ---
@router.callback_query(F.data == "menu_status")
async def show_status(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_status_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

# --- HANDLER ETALASE (DENGAN RESPON ALERT) ---
@router.callback_query(F.data == "menu_pricing")
async def menu_pricing_dummy(callback: types.CallbackQuery):
    await callback.answer("💎 Menu Upgrade VIP & Kasta sedang disiapkan oleh Developer...", show_alert=True)

@router.callback_query(F.data == "buy_quota")
async def buy_quota_menu(callback: types.CallbackQuery):
    await callback.answer("🛒 Etalase Kuota Extra sedang disiapkan oleh Developer...", show_alert=True)

@router.callback_query(F.data == "buy_boost")
async def buy_boost_menu(callback: types.CallbackQuery):
    await callback.answer("🚀 Etalase Tiket Boost sedang disiapkan oleh Developer...", show_alert=True)
