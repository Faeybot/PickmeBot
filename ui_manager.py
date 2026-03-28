from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

class UIManager:
    @staticmethod
    def get_global_nav_keyboard() -> ReplyKeyboardMarkup:
        """
        Keyboard statis di bawah layar (ReplyKeyboard) yang selalu ada.
        Ini memberikan nuansa aplikasi (SPA).
        """
        kb = [
            [KeyboardButton(text="⬅️ Kembali"), KeyboardButton(text="🏠 Dashboard")]
        ]
        # resize_keyboard=True sangat penting agar tombol tidak memakan separuh layar
        return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, persistent=True)

    @staticmethod
    def get_dashboard_inline_kb(inbox_count: int = 0, notif_count: int = 0) -> InlineKeyboardMarkup:
        """
        Inline keyboard utama untuk menu Dashboard.
        """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌎 DISCOVERY", callback_data="menu_discovery"),
             InlineKeyboardButton(text="🎭 FEED ANONIM", callback_data="menu_feed")],
             
            [InlineKeyboardButton(text=f"📥 PESAN ({inbox_count})", callback_data="menu_inbox"), 
             InlineKeyboardButton(text=f"🔔 NOTIFIKASI ({notif_count})", callback_data="menu_notifications")],
             
            [InlineKeyboardButton(text="⚙️ PROFIL SAYA", callback_data="menu_profile"),
             InlineKeyboardButton(text="🛒 TOP UP & UPGRADE", callback_data="menu_pricing")],
             
            [InlineKeyboardButton(text="🎁 UNDANG TEMAN", callback_data="menu_referral"),
             InlineKeyboardButton(text="📊 STATUS & KUOTA", callback_data="menu_status")],
             
            [InlineKeyboardButton(text="💰 WITHDRAW", callback_data="menu_withdraw")]
        ])

    @staticmethod
    def get_join_gate_kb(channel_link: str, group_link: str) -> InlineKeyboardMarkup:
        """ Keyboard untuk layar Wajib Join """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel Feed PickMe", url=f"https://t.me/{channel_link}")],
            [InlineKeyboardButton(text="👥 Join Grup PickMe", url=f"https://t.me/{group_link}")],
            [InlineKeyboardButton(text="✅ SAYA SUDAH JOIN", callback_data="check_join_start")]
        ])
