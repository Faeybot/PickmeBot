import os
import html
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InputMediaPhoto

from services.database import DatabaseService, User
from utils.ui_manager import UIManager 

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# ==========================================
# 0. HELPER MINAT
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
# 1. CORE UI RENDERER (PENGGANTI DUMMY)
# ==========================================
async def render_dashboard_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    """
    Fungsi terpusat untuk me-render Dashboard SPA.
    Bisa dipanggil dari handler manapun (Message atau Callback) tanpa perlu dummy object.
    """
    await state.clear()
    user = await db.get_user(user_id)
    
    if not user:
        return False # User tidak ditemukan, perlu registrasi ulang

    # Set navigasi kembali ke 'dashboard'
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
    
    success_edit = False
    anchor_id = user.anchor_msg_id

    # Coba Edit Pesan Jangkar (Mode SPA)
    if anchor_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=inline_kb)
            success_edit = True
        except Exception as e:
            pass # Pesan mungkin terhapus user, lanjut kirim pesan baru

    # Fallback: Jika gagal edit atau belum ada Anchor, Kirim Pesan Baru
    if not success_edit:
        try:
            # Bersihkan chat (Opsional, agar tidak numpuk)
            if anchor_id:
                try: await bot.delete_message(chat_id=chat_id, message_id=anchor_id)
                except: pass
                
            # Kirim keyboard navigasi bawah statis & Foto Dashboard
            global_nav = UIManager.get_global_nav_keyboard()
            
            # Telegram tidak mengizinkan ReplyKeyboard dan InlineKeyboard di 1 pesan yg sama.
            # Jadi kita attach ReplyKeyboard ke pesan loading sejenak.
            nav_msg = await bot.send_message(chat_id, "⚙️ Memuat sistem...", reply_markup=global_nav)
            await bot.delete_message(chat_id, nav_msg.message_id)
            
            # Kirim Anchor Utama
            sent_message = await bot.send_photo(
                chat_id=chat_id, photo=BANNER_PHOTO_ID, 
                caption=dashboard_text, reply_markup=inline_kb, parse_mode="HTML"
            )
            await db.update_anchor_msg(user_id, sent_message.message_id)
        except Exception as e:
            logging.error(f"Gagal mengirim ulang Dashboard UI: {e}")

    # Selesaikan loading callback jika ini berasal dari tombol
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
        
    return True

# ==========================================
# 2. HANDLER UTAMA (/start)
# ==========================================
@router.message(CommandStart())
@router.message(F.text == "🏠 Dashboard")
@router.message(F.text == "📱 DASHBOARD UTAMA") 
async def command_start_handler(message: types.Message, command: CommandObject = None, db: DatabaseService = None, bot: Bot = None, state: FSMContext = None):
    args = command.args if command else None 
    user_id = message.from_user.id 
    chat_id = message.chat.id

    # --- A. GATEKEEPER (Pengecekan Channel & Grup - Harga Mati) ---
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
            photo=BANNER_PHOTO_ID, caption=text_stop, 
            reply_markup=UIManager.get_join_gate_kb(CHANNEL_LINK, GROUP_LINK), parse_mode="HTML"
        )

    user = await db.get_user(user_id)
    
    # --- B. USER BARU: Arahkan ke Registrasi ---
    if not user:
        if state: await state.clear()
        from handlers.registration import RegState
        text_new = (
            "👋 <b>Selamat Datang di PickMe Bot!</b>\n\n"
            "Mari buat profil singkatmu sekarang!\n"
            "Siapa <b>nama panggilanmu(username)</b>? (3-15 karakter)"
        )
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

    # --- D. TAMPILKAN DASHBOARD UTAMA (Panggil Fungsi Native) ---
    await render_dashboard_ui(bot, chat_id, user_id, db, state)


# ==========================================
# 3. HANDLER CALLBACK (Gatekeeper & Navigasi)
# ==========================================
@router.callback_query(F.data == "check_join_start")
async def verify_join_start(callback: types.CallbackQuery, bot: Bot, db: DatabaseService, state: FSMContext):
    from handlers.registration import check_membership
    if await check_membership(bot, callback.from_user.id):
        try: await callback.message.delete()
        except: pass
        
        # Panggil fungsi core secara langsung (TIDAK ADA DUMMY LAGI)
        await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)
    else:
        await callback.answer("❌ Kamu belum join Channel/Grup!", show_alert=True)

@router.callback_query(F.data == "back_to_dashboard")
async def back_to_dashboard_callback(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    # Panggil fungsi core secara langsung
    success = await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)
    if not success:
        await callback.answer("❌ Sesi berakhir. Ketik /start kembali.", show_alert=True)


# ==========================================
# 4. HANDLER NAVIGASI BAWAH (ReplyKeyboard)
# ==========================================
@router.message(F.text == "⬅️ Kembali")
async def handle_back_button(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # 1. Hapus teks "⬅️ Kembali"
    try: await message.delete()
    except: pass
    
    # 2. Ambil halaman sebelumnya dari stack di DB
    previous_menu = await db.pop_nav(user_id)
    
    # 3. Routing bersih tanpa simulasi callback
    if previous_menu == "dashboard":
        await render_dashboard_ui(bot, chat_id, user_id, db, state)
    elif previous_menu == "feed":
        from handlers.feed import render_feed_ui
        await render_feed_ui(bot, chat_id, user_id, db, state)
    elif previous_menu == "boost":
        from handlers.boost import render_boost_ui
        await render_boost_ui(bot, chat_id, user_id, db)    
    elif previous_menu == "discovery":
        from handlers.discovery import render_discovery_ui
        await render_discovery_ui(bot, chat_id, user_id, db, state)
    elif previous_menu == "match":
        from handlers.match import render_match_ui
        await render_match_ui(bot, chat_id, user_id, db)
    elif previous_menu == "who_like_me":
        from handlers.who_like_me import render_who_like_me_ui
        await render_who_like_me_ui(bot, chat_id, user_id, db)


    
    else:
        # Fallback safety jika menu asal tidak terbaca, kembali ke Dashboard
        await render_dashboard_ui(bot, chat_id, user_id, db, state)
