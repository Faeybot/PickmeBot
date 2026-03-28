import asyncio
import logging
import os
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto
)
from services.database import DatabaseService

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID", "AgACAgUAAxkBAAIKUmm-3V96dh0wXlEwKgR9cZYxQJ7IAAJWEWsb5Sz5VRdAhJBTFWieAQADAgADeAADOgQ")

# ==========================================
# 1. DATA MASTER
# ==========================================
CITY_DATA = {
    "prof_city_medan": {"name": "Medan", "lat": 3.5952, "lng": 98.6722, "tag": "MEDAN"},
    "prof_city_plm": {"name": "Palembang", "lat": -2.9761, "lng": 104.7754, "tag": "PALEMBANG"},
    "prof_city_lamp": {"name": "Lampung", "lat": -5.3971, "lng": 105.2668, "tag": "LAMPUNG"},
    "prof_city_btm": {"name": "Batam", "lat": 1.1301, "lng": 104.0529, "tag": "BATAM"},
    "prof_city_jkt": {"name": "Jakarta", "lat": -6.2088, "lng": 106.8456, "tag": "JAKARTA"},
    "prof_city_bks": {"name": "Bekasi", "lat": -6.2383, "lng": 106.9756, "tag": "BEKASI"},
    "prof_city_bgr": {"name": "Bogor", "lat": -6.5971, "lng": 106.8060, "tag": "BOGOR"},
    "prof_city_bdg": {"name": "Bandung", "lat": -6.9175, "lng": 107.6191, "tag": "BANDUNG"},
    "prof_city_jgj": {"name": "Jogja", "lat": -7.7956, "lng": 110.3695, "tag": "JOGJA"},
    "prof_city_smr": {"name": "Semarang", "lat": -6.9667, "lng": 110.4167, "tag": "SEMARANG"},
    "prof_city_slo": {"name": "Solo", "lat": -7.5707, "lng": 110.8214, "tag": "SOLO"},
    "prof_city_sby": {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "tag": "SURABAYA"},
    "prof_city_mlg": {"name": "Malang", "lat": -7.9666, "lng": 112.6326, "tag": "MALANG"},
    "prof_city_dps": {"name": "Bali", "lat": -8.6705, "lng": 115.2126, "tag": "BALI"},
    "prof_city_lmbk": {"name": "Lombok", "lat": -8.5833, "lng": 116.1167, "tag": "LOMBOK"},
}

INTEREST_MAP = {
    "int_adult": "🔞 Adult Content",
    "int_flirt": "🔥 Flirt & Dirty Talk",
    "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking",
    "int_game": "🎮 Gaming",
    "int_travel": "✈️ Traveling",
    "int_coffee": "☕ Coffee & Chill"
}

class EditProfile(StatesGroup):
    waiting_for_bio = State()
    waiting_for_location = State()
    waiting_for_photo_main = State()
    waiting_for_photo_extra = State()
    waiting_for_interests = State()


# ==========================================
# 2. CORE UI RENDERER: PROFILE & MANAGE PHOTOS
# ==========================================
async def render_profile_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    await state.clear()
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "profile")
        
    extra_photos = user.extra_photos or []
    total_photos = 1 + len(extra_photos)

    interest_text = "Belum diatur"
    if hasattr(user, 'interests') and user.interests:
        interest_list = user.interests.split(",")
        interest_names = [INTEREST_MAP.get(i.strip(), i.strip()) for i in interest_list if i.strip()]
        if interest_names:
            interest_text = ", ".join(interest_names)

    text = (
        f"👤 <b>PREVIEW PROFIL</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Nama: <b>{user.full_name}</b>\n"
        f"Usia: <b>{user.age} Tahun</b>\n"
        f"Gender: <b>{user.gender.upper()}</b>\n"
        f"Kota: <b>{user.location_name}</b>\n"
        f"🔥 Minat: <b>{interest_text}</b>\n"
        f"Bio: <i>{user.bio or '-'}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"📸 Koleksi Foto: <b>{total_photos} / 3 Foto</b>\n"
        f"<i>(Foto ini adalah yang terlihat oleh user lain)</i>"
    )

    # ❌ TOMBOL BACK/DASHBOARD DIHAPUS
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 EDIT BIO", callback_data="update_bio"),
         InlineKeyboardButton(text="📍 UPDATE LOKASI", callback_data="update_loc")],
        [InlineKeyboardButton(text="🔥 UBAH MINAT", callback_data="update_interests")],
        [InlineKeyboardButton(text="📸 KELOLA GALERI FOTO", callback_data="manage_photos")]
    ])

    media = InputMediaPhoto(media=user.photo_id, caption=text, parse_mode="HTML")
    try: await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except Exception: pass
    
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

async def render_manage_photos_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService):
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "manage_photos")
    extra = user.extra_photos or []
    
    # ❌ TOMBOL KEMBALI DIHAPUS
    kb = [[InlineKeyboardButton(text="🖼️ GANTI FOTO UTAMA", callback_data="change_photo_main")]]
    if len(extra) < 2: kb.append([InlineKeyboardButton(text="➕ TAMBAH FOTO EXTRA", callback_data="add_photo_extra")])
    if extra: kb.append([InlineKeyboardButton(text="🗑️ HAPUS SEMUA FOTO EXTRA", callback_data="clear_photo_extra")])
    
    try: 
        await bot.edit_message_caption(
            chat_id=chat_id, message_id=user.anchor_msg_id, 
            caption="📸 <b>MANAJEMEN GALERI FOTO</b>\n\nPilih aksi yang ingin Anda lakukan:\n\n<i>(Gunakan navigasi bawah untuk kembali ke profil)</i>", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"
        )
    except: pass
    return True


@router.callback_query(F.data == "menu_profile")
async def show_my_profile(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 3. HANDLER UPDATE LOKASI
# ==========================================
@router.callback_query(F.data == "update_loc")
async def ask_location_profile(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    user = await db.get_user(callback.from_user.id)
    kb_list, temp_row = [], []
    for code, info in CITY_DATA.items():
        temp_row.append(InlineKeyboardButton(text=info["name"], callback_data=code))
        if len(temp_row) == 3:
            kb_list.append(temp_row)
            temp_row = []
    if temp_row: kb_list.append(temp_row)
    
    # ❌ TOMBOL BATAL DIHAPUS
    text = (
        "📍 <b>UPDATE LOKASI PROFIL</b>\n\n"
        "Pilih kota besarmu atau gunakan GPS otomatis agar teman di sekitarmu bisa menemukanmu."
    )

    try: await callback.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")
    except: pass

    # Jaga-jaga user ingin batal tanpa input lokasi
    gps_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 KIRIM KOORDINAT GPS", request_location=True)], [KeyboardButton(text="⬅️ Kembali")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    
    msg_gps = await callback.message.answer("Atau tekan tombol di bawah ini:", reply_markup=gps_kb)
    
    await state.update_data(gps_msg_id=msg_gps.message_id)
    await state.set_state(EditProfile.waiting_for_location)
    await callback.answer()

@router.callback_query(F.data.startswith("prof_city_"), EditProfile.waiting_for_location)
async def handle_manual_city_profile(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    city_info = CITY_DATA.get(callback.data)
    if city_info:
        async with db.session_factory() as session:
            from services.database import User as UserTable
            user = await session.get(UserTable, callback.from_user.id)
            if user:
                user.latitude, user.longitude = city_info["lat"], city_info["lng"]
                user.location_name = city_info["name"]
                user.city_hashtag = f"#{city_info['tag']}"
                await session.commit()
        
        data = await state.get_data()
        try: await bot.delete_message(chat_id=callback.message.chat.id, message_id=data.get('gps_msg_id'))
        except: pass
        
        await callback.answer(f"✅ Lokasi diperbarui ke {city_info['name']}!", show_alert=True)
        # NATIVE CALL (Bebas Mock Object)
        await render_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)

@router.message(F.location, EditProfile.waiting_for_location)
async def handle_gps_profile(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    lat, lon = message.location.latitude, message.location.longitude
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        if user:
            user.latitude, user.longitude = lat, lon
            user.location_name = "GPS Location"
            await session.commit()
            
    try: await message.delete()
    except: pass
    
    data = await state.get_data()
    try: await bot.delete_message(chat_id=message.chat.id, message_id=data.get('gps_msg_id'))
    except: pass
    
    hapus_kb = await message.answer("✅ Menyimpan lokasi GPS...", reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(1)
    try: await hapus_kb.delete()
    except: pass
    
    # NATIVE CALL
    await render_profile_ui(bot, message.chat.id, message.from_user.id, db, state)


# ==========================================
# 4. HANDLER MINAT 
# ==========================================
@router.callback_query(F.data == "update_interests")
async def ask_interests(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    selected = [i.strip() for i in (user.interests or "").split(",") if i.strip()]
    await state.update_data(selected_interests=selected)
    
    kb = []
    for code, name in INTEREST_MAP.items():
        prefix = "✅ " if code in selected else ""
        kb.append([InlineKeyboardButton(text=f"{prefix}{name}", callback_data=f"prof_int_{code}")])
    
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    # ❌ TOMBOL BATAL DIHAPUS
    
    try:
        await callback.message.edit_caption(
            caption="🔥 <b>UBAH MINAT</b>\nPilih maksimal 3 minat yang paling sesuai denganmu:\n\n<i>(Gunakan tombol navigasi bawah untuk membatalkan)</i>", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), 
            parse_mode="HTML"
        )
    except: pass
    await state.set_state(EditProfile.waiting_for_interests)

@router.callback_query(F.data.startswith("prof_int_"), EditProfile.waiting_for_interests)
async def toggle_interest(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    code = callback.data.replace("prof_int_", "")
    
    if code in selected: selected.remove(code)
    elif len(selected) < 3: selected.append(code)
    else: return await callback.answer("Maksimal 3 minat!", show_alert=True)
    
    await state.update_data(selected_interests=selected)
    kb = []
    for c, n in INTEREST_MAP.items():
        p = "✅ " if c in selected else ""
        kb.append([InlineKeyboardButton(text=f"{p}{n}", callback_data=f"prof_int_{c}")])
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "prof_save_int", EditProfile.waiting_for_interests)
async def save_interests(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    data = await state.get_data()
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, callback.from_user.id)
        if user:
            user.interests = ",".join(data.get("selected_interests", []))
            await session.commit()
    
    await callback.answer("✅ Minat disimpan!", show_alert=True)
    await render_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)


# ==========================================
# 5. HANDLER BIO
# ==========================================
@router.callback_query(F.data == "update_bio")
async def ask_bio(callback: types.CallbackQuery, state: FSMContext):
    text = "📝 <b>UPDATE BIO</b>\n\nMasukkan Bio baru Anda (Maks 150 Karakter):\n\n<i>(Ketik pesan lalu kirim, atau gunakan tombol navigasi bawah untuk membatalkan)</i>"
    try: await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_bio)

@router.message(EditProfile.waiting_for_bio)
async def save_bio(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if len(message.text) > 150: return await message.answer("⚠️ Terlalu panjang! Maks 150 Karakter.")
    
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        if user:
            user.bio = message.text
            await session.commit()
            
    try: await message.delete() 
    except: pass
    
    sukses = await message.answer("✅ <b>Bio berhasil diperbarui!</b>", parse_mode="HTML")
    await asyncio.sleep(1.5)
    try: await sukses.delete()
    except: pass
    
    await render_profile_ui(bot, message.chat.id, message.from_user.id, db, state)


# ==========================================
# 6. MANAJEMEN FOTO
# ==========================================
@router.callback_query(F.data == "manage_photos")
async def manage_photos_handler(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_manage_photos_ui(bot, callback.message.chat.id, callback.from_user.id, db)
    await callback.answer()

@router.callback_query(F.data == "change_photo_main")
async def start_change_main(callback: types.CallbackQuery, state: FSMContext):
    try: await callback.message.edit_caption(caption="📸 Kirimkan <b>1 Foto Utama</b> yang baru untuk profil Anda:\n\n<i>(Gunakan tombol navigasi bawah untuk membatalkan)</i>", reply_markup=None, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_photo_main)
    await callback.answer()

@router.message(EditProfile.waiting_for_photo_main, F.photo)
async def save_new_main(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    await db.update_main_photo(message.from_user.id, message.photo[-1].file_id)
    await state.clear()
    
    try: await message.delete()
    except: pass
    
    sukses = await message.answer("✅ <b>Foto Utama berhasil diganti!</b>", parse_mode="HTML")
    await asyncio.sleep(1.5)
    try: await sukses.delete()
    except: pass
    
    await render_manage_photos_ui(bot, message.chat.id, message.from_user.id, db)

@router.callback_query(F.data == "add_photo_extra")
async def start_add_extra(callback: types.CallbackQuery, state: FSMContext):
    try: await callback.message.edit_caption(caption="📸 Kirimkan <b>Foto Tambahan</b> Anda:\n\n<i>(Gunakan tombol navigasi bawah untuk membatalkan)</i>", reply_markup=None, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_photo_extra)
    await callback.answer()

@router.message(EditProfile.waiting_for_photo_extra, F.photo)
async def save_new_extra(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    await db.manage_extra_photo(message.from_user.id, message.photo[-1].file_id, action='add')
    await state.clear()
    
    try: await message.delete()
    except: pass
    
    sukses = await message.answer("✅ <b>Foto Tambahan berhasil disimpan!</b>", parse_mode="HTML")
    await asyncio.sleep(1.5)
    try: await sukses.delete()
    except: pass
    
    await render_manage_photos_ui(bot, message.chat.id, message.from_user.id, db)

@router.callback_query(F.data == "clear_photo_extra")
async def clear_photos(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, callback.from_user.id)
        if user: user.extra_photos = []; await session.commit()
        
    await callback.answer("🗑️ Foto Extra dihapus!", show_alert=True)
    await render_manage_photos_ui(bot, callback.message.chat.id, callback.from_user.id, db)
