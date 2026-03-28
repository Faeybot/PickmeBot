import os
import html
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InputMediaPhoto

from services.database import DatabaseService, User

# IMPORT UI MANAGER BARU KITA
from utils.ui_manager import UIManager 

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# ==========================================
# 0. HELPER MINAT (DIKEMBALIKAN UNTUK PREVIEW.PY)
# ==========================================
INTEREST_LABELS = {
    "int_adult": "🔞 Adult Content", "int_flirt": "🔥 Flirt & Dirty Talk", "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking", "int_game": "🎮 Gaming", "int_travel": "✈️ Traveling", "int_coffee": "☕ Coffee & Chill"
}

def get_readable_interests(interests_str: str) -> str:
    """Mengubah kode minat menjadi teks yang cantik untuk ditampilkan"""
    if not interests_str: return "Belum memilih minat."
    return ", ".join([INTEREST_LABELS.get(code.strip(), code.strip()) for code in interests_str.split(",")])


# ==========================================
# 2. HANDLER UTAMA (/start & Tombol Dashboard)
# ==========================================
@router.message(CommandStart())
@router.message(F.text == "🏠 Dashboard") # Diubah menyesuaikan UIManager
@router.message(F.text == "📱 DASHBOARD UTAMA") # Tetap dipertahankan untuk kompatibilitas sementara
async def command_start_handler(message: types.Message, command: CommandObject = None, db: DatabaseService = None, bot: Bot = None, state: FSMContext = None):
    if state:
        await state.clear()
        
    args = command.args if command else None 
    user_id = message.from_user.id 

    # --- A. GATEKEEPER ASLI V5 (Pengecekan Channel & Grup) ---
    from handlers.registration import check_membership, CHANNEL_LINK, GROUP_LINK
    
    is_joined = await check_membership(bot, user_id)
    if not is_joined:
        text_stop = (
            "<b>STOP! Join Dulu ya Guys!!!</b> ✋\n\n"
            "Untuk menjaga kualitas komunitas, kamu wajib bergabung di Channel dan Grup kami "
            "sebelum bisa beraksi di PickMe.\n\n"
            "<i>Silakan bergabung kembali melalui tombol di bawah:</i>"
        )
        return await message.answer_photo(
            photo=BANNER_PHOTO_ID, 
            caption=text_stop, 
            reply_markup=UIManager.get_join_gate_kb(CHANNEL_LINK, GROUP_LINK), 
            parse_mode="HTML"
        )

    user = await db.get_user(user_id)
    
    # --- B. USER BARU: Arahkan ke Registrasi ---
    if not user:
        from handlers.registration import RegState
        text_new = (
            "👋 <b>Selamat Datang di PickMe Bot!</b>\n\n"
            "Mari buat profil singkatmu sekarang!\n"
            "Siapa <b>nama panggilanmu(username)</b>? (3-15 karakter)"
        )
        # Menghilangkan custom keyboard saat registrasi agar fokus
        await message.answer(text_new, parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
        return await state.set_state(RegState.waiting_nickname)

    # --- C. ROUTER DEEP LINK ---
    if args and args.startswith("view_"):
        parts = args.split("_")
        try: 
            target_id = int(parts[1])
            origin_type = parts[2] if len(parts) >= 3 else "public" 
            from handlers.preview import process_profile_preview
            return await process_profile_preview(message, bot, db, viewer_id=user_id, target_id=target_id, context_source=origin_type)
        except Exception as e:
            logging.error(f"Error Deep Link Routing: {e}")
            return await message.answer("⚠️ Gagal memuat profil. Format link tidak valid atau ada kendala sistem.")

    # --- D. TAMPILKAN DASHBOARD UTAMA (CORE SPA LOGIC) ---
    
    # 1. Reset Nav Stack karena kita berada di halaman utama
    await db.push_nav(user_id, "dashboard") 
    
    kasta = "💎 VIP+" if user.is_vip_plus else "🌟 VIP" if user.is_vip else "🎭 TALENT" if user.is_talent else "👤 FREE"
    
    dashboard_text = (
        f"👋 Halo, <b>{user.full_name.upper()}</b>!\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 Status: <b>{kasta}</b>\n"
        f"💰 Saldo: <b>{user.poin_balance:,} Poin</b>\n"
        f"📍 Lokasi: <b>{user.location_name}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )

    unreads = await db.get_all_unread_counts(user_id)
    count_inbox = unreads.get('inbox', 0)
    count_notif = unreads.get('unmask', 0) + unreads.get('view', 0)
    
    # 2. Persiapkan Inline Keyboard & Global Nav Keyboard
    inline_kb = UIManager.get_dashboard_inline_kb(count_inbox, count_notif)
    global_nav = UIManager.get_global_nav_keyboard()

    try:
        # 3. Kirim Pesan Utama (Pesan Jangkar)
        sent_message = await message.answer_photo(
            photo=BANNER_PHOTO_ID, 
            caption=dashboard_text, 
            reply_markup=inline_kb, 
            parse_mode="HTML"
        )
        # 4. Kirim Pesan Dummy untuk memunculkan ReplyKeyboard, lalu langsung dihapus
        dummy_msg = await message.answer("Memuat navigasi...", reply_markup=global_nav)
        await bot.delete_message(chat_id=message.chat.id, message_id=dummy_msg.message_id)
        
        # 5. Simpan ID Pesan Jangkar ke Database
        await db.update_anchor_msg(user_id, sent_message.message_id)
        
    except Exception as e:
        logging.error(f"Gagal kirim dashboard (SPA init): {e}")
        await message.answer(dashboard_text, reply_markup=inline_kb, parse_mode="HTML")


# ==========================================
# 3. HANDLER CALLBACK (Navigasi Mulus SPA)
# ==========================================
@router.callback_query(F.data == "check_join_start")
async def verify_join_start(callback: types.CallbackQuery, bot: Bot, db: DatabaseService, state: FSMContext):
    from handlers.registration import check_membership
    if await check_membership(bot, callback.from_user.id):
        try: await callback.message.delete()
        except: pass
        from collections import namedtuple
        DummyCommand = namedtuple('CommandObject', ['args'])
        return await command_start_handler(callback.message, DummyCommand(args=None), db, bot, state)
    else:
        await callback.answer("❌ Kamu belum join Channel/Grup!", show_alert=True)

@router.callback_query(F.data == "back_to_dashboard")
async def back_to_dashboard(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """
    Dipanggil ketika menekan tombol kembali ke dashboard dari inline menu.
    """
    await state.clear()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return await callback.answer("❌ Sesi berakhir. Ketik /start kembali.", show_alert=True)

    # Pastikan state Navigasi di reset
    await db.push_nav(user_id, "dashboard")

    kasta = "💎 VIP+" if user.is_vip_plus else "🌟 VIP" if user.is_vip else "🎭 TALENT" if user.is_talent else "👤 FREE"
    
    dashboard_text = (
        f"👋 Halo, <b>{user.full_name.upper()}</b>!\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 Status: <b>{kasta}</b>\n"
        f"💰 Saldo: <b>{user.poin_balance:,} Poin</b>\n"
        f"📍 Lokasi: <b>{user.location_name}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )

    unreads = await db.get_all_unread_counts(user_id)
    count_inbox = unreads.get('inbox', 0)
    count_notif = unreads.get('unmask', 0) + unreads.get('view', 0)
    
    inline_kb = UIManager.get_dashboard_inline_kb(count_inbox, count_notif)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=dashboard_text, parse_mode="HTML")
    
    try:
        # Edit Pesan Jangkar yang sudah ada
        await callback.message.edit_media(media=media, reply_markup=inline_kb)
    except Exception as e:
        # Fallback: Jika pesan lama terhapus/error, kirim baru dan perbarui Anchor
        try: await callback.message.delete()
        except: pass
        sent_message = await bot.send_photo(
            chat_id=user_id, 
            photo=BANNER_PHOTO_ID, 
            caption=dashboard_text, 
            reply_markup=inline_kb, 
            parse_mode="HTML"
        )
        await db.update_anchor_msg(user_id, sent_message.message_id)
    
    await callback.answer()

# ==========================================
# 4. HANDLER NAVIGASI BAWAH (ReplyKeyboard)
# ==========================================
@router.message(F.text == "⬅️ Kembali")
async def handle_back_button(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    """
    Menangani tombol '⬅️ Kembali' dari ReplyKeyboard bawah.
    """
    user_id = message.from_user.id
    
    # 1. Hapus teks "⬅️ Kembali" yang dikirim user agar chat bersih (Sudah di-handle oleh Middleware sebenarnya, tapi ini double check)
    try: await message.delete()
    except: pass
    
    # 2. Ambil halaman sebelumnya dari stack
    previous_menu = await db.pop_nav(user_id)
    
    # 3. Arahkan logika (Routing)
    # Jika sebelumnya dashboard, panggil fungsi start
    if previous_menu == "dashboard":
        # Simulasikan klik tombol back_to_dashboard
        from aiogram.types import CallbackQuery
        # Membuat dummy callback query untuk diarahkan ke fungsi back_to_dashboard
        dummy_callback = CallbackQuery(
            id="dummy", from_user=message.from_user, chat_instance="dummy",
            message=types.Message(message_id=(await db.get_user(user_id)).anchor_msg_id, date=message.date, chat=message.chat),
            data="back_to_dashboard"
        )
        await back_to_dashboard(dummy_callback, db, bot, state)
    
    # Nanti kita bisa tambahkan elif previous_menu == "feed": dst. ketika file lain sudah siap.
