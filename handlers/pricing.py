import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command 
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()

# --- 1. CONFIGURATION ---
FINANCE_GROUP_ID = os.getenv("FINANCE_GROUP_ID") 
CATALOG_PHOTO_ID = "AgACAgUAAxkBAAICm2m98Ci5YD2pZTbqYoJrShVgWSq9AAJvDGsbPyfwVfA9zs-0TS-oAQADAgADeQADOgQ" 

# ==========================================
# 2. CORE UI RENDERER: PRICING STORE
# ==========================================
async def render_pricing_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "pricing")

    text = (
        "🛒 <b>PICKME STORE - KATALOG RESMI</b>\n"
        f"<code>{'—' * 22}</code>\n"
        "Buka fitur sakti dan jadilah Sultan di PickMe!\n\n"
        "💡 <b>TRIAL GRATIS TERSEDIA:</b>\n"
        "Selama masa integrasi Midtrans, semua paket di bawah ini bisa kamu coba secara <b>GRATIS selama 7 Hari</b>!\n\n"
        "<i>Silakan pilih paket untuk melihat detail fitur.</i>"
    )

    # ❌ TOMBOL BACK DIHAPUS
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 PAKET VIP", callback_data="p_info_vip")],
        [InlineKeyboardButton(text="💎 PAKET VIP+ (Sultan Eksklusif)", callback_data="p_info_vipplus")],
        [
            InlineKeyboardButton(text="🎭 TALENT", callback_data="p_info_talent"),
            InlineKeyboardButton(text="🚀 BOOST", callback_data="p_info_boost")
        ]
    ])
    
    media = InputMediaPhoto(media=CATALOG_PHOTO_ID, caption=text, parse_mode="HTML")
    anchor_id = user.anchor_msg_id

    try: await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=kb)
    except Exception: pass
    
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

# ==========================================
# 3. HANDLER PERINTAH & MENU
# ==========================================
@router.message(Command("pricing"))
async def pricing_command_handler(message: types.Message, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass
    # Mengarah ke SPA render, memotong alur manual command.
    await render_pricing_ui(bot, message.chat.id, message.from_user.id, db)

@router.callback_query(F.data == "menu_pricing")
async def show_pricing_store(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_pricing_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

# ==========================================
# 4. POP-UP INFO JACKPOT TRIAL
# ==========================================
@router.callback_query(F.data.startswith("p_info_"))
async def show_trial_offer(callback: types.CallbackQuery, db: DatabaseService):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    # Kunci navigasi ini agar tombol kembali tahu bahwa kita sedang di menu penawaran
    await db.push_nav(user_id, "pricing_trial")

    text = (
        "💎 <b>PROGRAM VIP+ JACKPOT (TRIAL)</b>\n"
        f"<code>{'—' * 22}</code>\n"
        "Kabar gembira! Kami memberikan akses <b>VIP+ EKSKLUSIF</b> secara gratis untuk setiap pengajuan uji coba.\n\n"
        "🔥 <b>Fitur VIP+ yang akan kamu dapatkan:</b>\n"
        "• 🔓 <b>Unmask Aktif:</b> Bongkar semua identitas anonim.\n"
        "• 💬 <b>Chat Maksimal:</b> Kuota kirim pesan paling tinggi.\n"
        "• ⚡ <b>Prioritas:</b> Profilmu muncul paling depan di Discovery.\n\n"
        "🎁 <b>Ajukan akses VIP+ 7 Hari sekarang juga!</b>"
    )
    
    # ❌ TOMBOL BACK DIHAPUS (Bisa kembali menggunakan tombol bawah layar)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 AJUKAN TRIAL VIP+ (GRATIS)", callback_data="req_trial_vipplus_trial")]
    ])
    
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except: pass
    await callback.answer()

# ==========================================
# 5. KIRIM PENGAJUAN KE GRUP ADMIN FINANCE
# ==========================================
@router.callback_query(F.data.startswith("req_trial_"))
async def send_to_admin_group(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    username = f"@{callback.from_user.username}" if callback.from_user.username else "No Username"
    
    text_success = (
        "✅ <b>PENGAJUAN BERHASIL!</b>\n\n"
        "Permintaan akses <b>VIP+ Trial</b> kamu sudah masuk ke tim Finance.\n"
        "Mohon tunggu notifikasi selanjutnya. Akunmu akan aktif otomatis jika disetujui Admin.\n\n"
        "<i>Gunakan tombol navigasi di bawah untuk kembali.</i>"
    )
    
    try: await callback.message.edit_caption(caption=text_success, reply_markup=None, parse_mode="HTML")
    except: pass

    admin_text = (
        f"🎁 <b>REQUEST TRIAL VIP+ (BETA)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"User: <b>{callback.from_user.full_name}</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: {username}\n"
        f"Paket: <b>VIP+ (7 HARI TRIAL)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👇 Admin silakan berikan akses Sultan:"
    )

    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ SETUJUI VIP+ (7 HARI)", callback_data=f"trial_apv_{user_id}_vipplus")],
        [InlineKeyboardButton(text="❌ TOLAK", callback_data=f"trial_rej_{user_id}")]
    ])

    if FINANCE_GROUP_ID:
        try: await bot.send_message(FINANCE_GROUP_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except Exception as e: logging.error(f"Gagal kirim ke grup finance: {e}")
            
    await callback.answer("Pengajuan Terkirim!", show_alert=True)
