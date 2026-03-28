import asyncio
import datetime
import os
import html
import logging
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService, User

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# --- HELPER: BACKGROUND TASK AUTO-SUNDUL ---
async def execute_repost_logic(bot: Bot, user_id: int, count: int, interval_hours: int, label: str, db: DatabaseService):
    """ SISTEM AUTO-SUNDUL (Berjalan di Background) """
    channel_id = os.getenv("FEED_CHANNEL_ID")
    bot_info = await bot.get_me()
    
    for i in range(count):
        try:
            user = await db.get_user(user_id)
            if not user:
                break
                
            display_name = user.full_name
            link_profile = f"https://t.me/{bot_info.username}?start=view_{user.id}"
            
            header = f"🚀 <b>[{label}]</b>\n👤 <b>{display_name.upper()}</b> | <a href=\"{link_profile}\">VIEW PROFILE</a>"
            isi_feed = f"<blockquote>{html.escape(user.bio or 'Cek profilku yuk! Mari berkenalan.')}</blockquote>"
            full_text = f"{header}\n<code>{'—' * 20}</code>\n{isi_feed}\n\n📍 {user.city_hashtag} #{user.gender.upper()} #PickMeBoost"

            if user.photo_id:
                await bot.send_photo(channel_id, photo=user.photo_id, caption=full_text, parse_mode="HTML")
            else:
                await bot.send_message(channel_id, full_text, parse_mode="HTML")
            
            if i < count - 1:
                await asyncio.sleep(interval_hours * 3600) 
                
        except Exception as e:
            logging.error(f"Error pada siklus Boost Loop ke-{i+1} untuk User {user_id}: {e}")
            break

# ==========================================
# 1. CORE UI RENDERER: BOOST
# ==========================================
async def render_boost_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "boost")

    total_boost = user.paid_boost_balance + user.weekly_free_boost
    
    text = (
        "🚀 <b>PUSAT KENDALI BOOST</b>\n"
        f"<code>{'—' * 20}</code>\n"
        "Boost adalah fitur untuk <b>menyundul profilmu</b> secara otomatis agar selalu berada di puncak Channel Feed.\n\n"
        "<b>📊 PILIHAN PAKET:</b>\n"
        "• <b>1 Tiket:</b> Tampil 3x (Jeda 3 jam)\n"
        "• <b>3 Tiket:</b> Tampil 6x (Jeda 2 jam)\n"
        "• <b>5 Tiket:</b> Tampil 12x (Jeda 1 jam)\n\n"
        "⚠️ <i>Aturan: Demi kenyamanan bersama, Boost hanya bisa diaktifkan <b>1x Sehari</b>.</i>\n\n"
        f"💳 Saldo Tiket Anda: <b>{total_boost} Tiket</b>"
    )

    # ❌ TOMBOL BACK/KEMBALI DIHAPUS DARI SINI
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Pakai 1 Tiket (3x Post)", callback_data="boost_plan_1")],
        [InlineKeyboardButton(text="🚀 Pakai 3 Tiket (6x Post)", callback_data="boost_plan_3")],
        [InlineKeyboardButton(text="🔥 Pakai 5 Tiket (12x Post)", callback_data="boost_plan_5")],
        [InlineKeyboardButton(text="🛒 BELI TIKET BOOST", callback_data="menu_pricing")]
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
            logging.error(f"Gagal mengirim ulang Boost UI: {e}")

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass

    return True

# --- 2. MENU BOOST HANDLER ---
@router.callback_query(F.data == "menu_boost")
async def show_boost_menu(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_boost_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

# --- 3. EKSEKUSI BOOST ---
@router.callback_query(F.data.startswith("boost_plan_"))
async def process_boost_plan(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    plan = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        
        if user.last_boost_date == today:
            return await callback.answer("⚠️ Anda sudah melakukan Boost hari ini. Gunakan kembali besok!", show_alert=True)

        total_boost = user.paid_boost_balance + user.weekly_free_boost
        if total_boost < plan:
            return await callback.answer(f"❌ Saldo tidak cukup! Anda butuh {plan} tiket.", show_alert=True)

        if plan == 1:
            repost_count, interval, label = 3, 3, "BOOST 1x"
        elif plan == 3:
            repost_count, interval, label = 6, 2, "BOOST 3x"
        else: 
            repost_count, interval, label = 12, 1, "BOOST 5x"

        remaining_to_deduct = plan
        if user.weekly_free_boost >= remaining_to_deduct:
            user.weekly_free_boost -= remaining_to_deduct
        else:
            remaining_to_deduct -= user.weekly_free_boost
            user.weekly_free_boost = 0
            user.paid_boost_balance -= remaining_to_deduct
        
        user.last_boost_date = today
        await session.commit()

    success_text = (
        f"✅ <b>BOOST BERHASIL DIAKTIFKAN!</b>\n"
        f"<code>{'—' * 20}</code>\n"
        f"Profil Anda akan disundul ke Channel sebanyak <b>{repost_count}x</b> secara otomatis.\n\n"
        f"<i>Bot akan menangani ini di latar belakang. Silakan gunakan navigasi di bawah untuk melanjutkan.</i>"
    )
    
    # ❌ TOMBOL BACK/KEMBALI DIHAPUS, reply_markup diset ke None
    try:
        await callback.message.edit_caption(caption=success_text, reply_markup=None, parse_mode="HTML")
    except Exception:
        pass
    
    asyncio.create_task(execute_repost_logic(bot, user_id, repost_count, interval, label, db))
    await callback.answer()
