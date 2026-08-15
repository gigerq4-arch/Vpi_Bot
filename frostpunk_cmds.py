from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select

from database import async_session, User, Country, CountryBuilding, CountryProduction, CountryStockpile
from engine import get_config
from keyboards import get_frostpunk_keyboard

router = Router()

class FrostpunkFSM(StatesGroup):
    waiting_for_factories = State()

@router.message(Command("frostpunk", "generator"))
async def cmd_frostpunk(message: Message):
    cfg = get_config()
    if not getattr(cfg.game_settings, "frostpunk_event", False):
        await message.answer("❄️ Ивент «Фростпанк» сейчас отключен.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("Сначала зарегистрируйтесь и создайте страну.")
            return

        gen_stock = await session.scalar(
            select(CountryStockpile.amount)
            .where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == 45)
        )
        gen_count = gen_stock if gen_stock else 0

        productions = await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id, CountryProduction.item_id == 45))
        assigned_factories = sum(p.assigned_factories for p in productions)
        
        power_lvl = getattr(country, "gen_power_level", 1)
        radius_lvl = getattr(country, "gen_radius_level", 1)
        
        next_power_cost = get_power_upgrade_cost(power_lvl)
        next_radius_cost = get_radius_upgrade_cost(radius_lvl)
        
        text = (
            f"❄️ <b>Меню ивента «Фростпанк»</b>\n"
            f"------------------------------------\n"
            f"Генератор дает тепло и защищает население от морозов.\n\n"
            f"<b>Сборка Генератора (Детали):</b> {gen_count:.1f} шт.\n"
            f"<b>Назначено гражданских фабрик:</b> {assigned_factories}\n\n"
            f"⚡️ <b>Мощность:</b> Уровень {power_lvl} (Улучшение: {next_power_cost} B$)\n"
            f"<i>(Каждое улучшение дает +0.15% к рождаемости и +5 к стабильности)</i>\n\n"
            f"📡 <b>Радиус:</b> Уровень {radius_lvl} (Улучшение: {next_radius_cost} B$)\n"
            f"<i>(Каждое улучшение: +500 000 к вместимости и +2% к стабильности)</i>\n\n"
            f"Используйте кнопки ниже для управления проектом."
        )
        await message.answer(text, reply_markup=get_frostpunk_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "fp_assign_gen")
async def fp_assign_gen_cb(callback: CallbackQuery, state: FSMContext):
    cfg = get_config()
    if not getattr(cfg.game_settings, "frostpunk_event", False):
        await callback.answer("Ивент отключен", show_alert=True)
        return
        
    await callback.message.answer("Сколько гражданских фабрик выделить на постройку Генератора?\n\nВведите число (или 0 чтобы снять все):")
    await state.set_state(FrostpunkFSM.waiting_for_factories)
    await callback.answer()

@router.message(FrostpunkFSM.waiting_for_factories)
async def process_assign_factories(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Введите корректное положительное число или 0.")
        return
        
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        # Check total civil factories (building_id == 5)
        civ_factories = await session.scalar(
            select(CountryBuilding.total_count)
            .where(CountryBuilding.country_id == country.id, CountryBuilding.building_id == 5)
        )
        civ_factories = civ_factories if civ_factories else 0
        
        if amount > civ_factories:
            await message.answer(f"У вас нет столько гражданских фабрик. Доступно: {civ_factories}")
            return
            
        prod = await session.scalar(
            select(CountryProduction)
            .where(CountryProduction.country_id == country.id, CountryProduction.item_id == 45)
        )
        if not prod:
            prod = CountryProduction(country_id=country.id, item_id=45, assigned_factories=amount)
            session.add(prod)
        else:
            prod.assigned_factories = amount
            
        await session.commit()
        await message.answer(f"✅ На производство Генератора назначено {amount} гражданских фабрик.")
        await state.clear()

def get_power_upgrade_cost(level: int) -> float:
    return level * 5.0

def get_radius_upgrade_cost(level: int) -> float:
    return level * 7.5

@router.callback_query(F.data == "fp_upgrade_power")
async def fp_upgrade_power_cb(callback: CallbackQuery):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if not country: return
        
        lvl = getattr(country, "gen_power_level", 1)
        cost = get_power_upgrade_cost(lvl)
        
        if country.treasury < cost:
            await callback.answer(f"Недостаточно средств! Нужно {cost} B$.", show_alert=True)
            return
            
        country.treasury -= cost
        country.gen_power_level = lvl + 1
        
        country.growth_modifier += 0.15
        country.stability += 5.0
        if country.stability > 100: country.stability = 100
        
        await session.commit()
        await callback.message.edit_text(
            f"✅ <b>Мощность генератора улучшена до уровня {lvl + 1}!</b>\n\n"
            f"Потрачено: {cost} B$\n"
            f"Рождаемость увеличена на +0.15%, а стабильность на +5!",
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "fp_upgrade_radius")
async def fp_upgrade_radius_cb(callback: CallbackQuery):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if not country: return
        
        lvl = getattr(country, "gen_radius_level", 1)
        cost = get_radius_upgrade_cost(lvl)
        
        if country.treasury < cost:
            await callback.answer(f"Недостаточно средств! Нужно {cost} B$.", show_alert=True)
            return
            
        country.treasury -= cost
        country.gen_radius_level = lvl + 1
        
        country.stability += 2.0
        if country.stability > 100: country.stability = 100
        
        await session.commit()
        await callback.message.edit_text(
            f"✅ <b>Радиус генератора увеличен до уровня {lvl + 1}!</b>\n\n"
            f"Потрачено: {cost} B$\n"
            f"Теперь обогревается больше населения (Стабильность +2%).",
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(Command("gen_assign"))
async def cmd_gen_assign(message: Message):
    from engine import get_config
    cfg = get_config()
    if not getattr(cfg.game_settings, 'frostpunk_event', False):
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: `/gen_assign [кол-во]`", parse_mode="Markdown")
        return
        
    try:
        count = int(args[1])
        if count <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Ошибка: Введите корректное число.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        cb = await session.scalar(
            select(CountryBuilding.total_count)
            .where(CountryBuilding.country_id == country.id, CountryBuilding.building_id == 5)
        )
        total_factories = cb if cb else 0
        
        prod = await session.scalar(
            select(CountryProduction)
            .where(CountryProduction.country_id == country.id, CountryProduction.item_id == 45)
        )
        assigned = prod.assigned_factories if prod else 0
        free_factories = total_factories - assigned
        
        if free_factories < count:
            await message.answer(f"❌ Ошибка: У вас недостаточно свободных гражданских фабрик. Свободно: {free_factories}.")
            return
            
        if not prod:
            prod = CountryProduction(country_id=country.id, item_id=45, assigned_factories=count)
            session.add(prod)
        else:
            prod.assigned_factories += count
            
        await session.commit()
        await message.answer(f"✅ Добавлено {count} фабрик на постройку Генераторов. Всего назначено: {prod.assigned_factories}")

@router.message(Command("gen_remove"))
async def cmd_gen_remove(message: Message):
    from engine import get_config
    cfg = get_config()
    if not getattr(cfg.game_settings, 'frostpunk_event', False):
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: `/gen_remove [кол-во|all]`", parse_mode="Markdown")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        prod = await session.scalar(
            select(CountryProduction)
            .where(CountryProduction.country_id == country.id, CountryProduction.item_id == 45)
        )
        assigned = prod.assigned_factories if prod else 0
        
        if assigned == 0:
            await message.answer("❌ У вас не назначено ни одной фабрики на генератор.")
            return

        count_str = args[1].lower()
        if count_str == 'all':
            remove_count = assigned
        else:
            try:
                remove_count = int(count_str)
                if remove_count <= 0: raise ValueError
            except ValueError:
                await message.answer("❌ Ошибка: Введите корректное число или 'all'.")
                return

        if remove_count > assigned:
            remove_count = assigned
            
        prod.assigned_factories -= remove_count
        if prod.assigned_factories == 0:
            await session.delete(prod)
            
        await session.commit()
        await message.answer(f"✅ Снято {remove_count} фабрик с постройки Генераторов. Осталось назначено: {assigned - remove_count}")
