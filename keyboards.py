from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Подать анкету страны", callback_data="register_country")]
        ]
    )

def get_moderation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ]
    )

def get_army_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪖 Нанять военных", callback_data="army_hire")],
            [InlineKeyboardButton(text="🎖 Демобилизовать", callback_data="army_demob")],
            [InlineKeyboardButton(text="⚙️ Военное положение", callback_data="army_martial_law")]
        ]
    )

def get_spy_targets_keyboard(countries: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for country in countries:
        builder.button(text=f"🏳️ {country.name}", callback_data=f"spy_target_{country.id}")
    builder.adjust(2)
    return builder.as_markup()

def get_spy_operations_keyboard(target_id: int, inflation: float = 0.0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    mult = 1.0 + (inflation / 100.0)
    builder.button(text=f"💰 Баланс Казны ({10 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_1")
    builder.button(text=f"👥 Демография и Налоги ({15 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_2")
    builder.button(text=f"⚖️ Стабильность и Настроения ({15 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_3")
    builder.button(text=f"🪖 Состав Армии ({40 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_4")
    builder.button(text=f"📦 Склады ВПК ({50 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_5")
    builder.button(text=f"💥 Диверсия ВПК ({90 * mult:.1f} ОА)", callback_data=f"spy_op_{target_id}_6")
    builder.adjust(1)
    return builder.as_markup()
