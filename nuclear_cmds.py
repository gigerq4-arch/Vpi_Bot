from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import async_session, Country, CountryBuilding, CountryProduction
from sqlalchemy import select
from engine import get_config, save_config

router = Router()

@router.message(Command("nuclear_toggle", "nuclear_off", "nuclear_on", ignore_case=True))
async def cmd_nuclear_toggle(message: Message):
    cfg = get_config()
    is_admin = message.from_user.id == cfg.game_settings.root_admin_id
    if not is_admin:
        await message.answer("❌ Эта команда доступна только администратору.")
        return

    lab_building = next((b for b in cfg.buildings if b.building_id == 6), None)
    if not lab_building:
        await message.answer("❌ Здание Ядерной лаборатории не найдено в конфигурации.")
        return

    lab_building.enabled = not lab_building.enabled
    save_config(cfg)
    
    status = "ВКЛЮЧЕНА ✅" if lab_building.enabled else "ОТКЛЮЧЕНА ❌"
    await message.answer(f"☢️ Ядерная программа теперь **{status}**.", parse_mode="Markdown")

@router.message(Command("nuclear", "nuke", ignore_case=True))
@router.message(Command("nuke", ignore_case=True))
@router.message(Command("nuclear", ignore_case=True))
async def cmd_nuclear(message: Message):
    cfg = get_config()
    lab_building = next((b for b in cfg.buildings if b.building_id == 6), None)
    if not lab_building or not lab_building.enabled:
        await message.answer("❌ Ядерная программа в данный момент отключена.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
        
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == 6
        ))
        total_labs = cb.total_count if cb else 0
        
        used_in_prod = 0
        prods = await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id))
        for p in prods:
            if p.item_id == 21:
                used_in_prod += p.assigned_factories
                
        used_in_research = (country.lab_assigned_phase_1 + country.lab_assigned_phase_2 +
                            country.lab_assigned_phase_3 + country.lab_assigned_phase_4 +
                            country.lab_assigned_phase_5)
                            
        free_labs = total_labs - used_in_prod - used_in_research
        
        completed = all([
            country.nuclear_phase_1 >= 100,
            country.nuclear_phase_2 >= 100,
            country.nuclear_phase_3 >= 100,
            country.nuclear_phase_4 >= 100,
            country.nuclear_phase_5 >= 100
        ])
        
        status = "✅ ИЗУЧЕНО (Доступно производство)" if completed else "⏳ В разработке"
        
        text = (
            "☢️ **Ядерная программа**\n"
            "------------------------------------\n"
            f"Статус: {status}\n\n"
            f"🔬 Всего лабораторий: {total_labs}\n"
            f"🛠 Свободно для исследований: {free_labs}\n"
            f"🏭 Занято в производстве бомб: {used_in_prod}\n\n"
            f"**Этапы исследования:**\n"
            f"1. Ядерный заряд: {country.nuclear_phase_1:.1f}% (Лаб: {country.lab_assigned_phase_1})\n"
            f"2. Источник нейтронов: {country.nuclear_phase_2:.1f}% (Лаб: {country.lab_assigned_phase_2})\n"
            f"3. Взрывчатое вещество: {country.nuclear_phase_3:.1f}% (Лаб: {country.lab_assigned_phase_3})\n"
            f"4. Автоматика: {country.nuclear_phase_4:.1f}% (Лаб: {country.lab_assigned_phase_4})\n"
            f"5. Корпус: {country.nuclear_phase_5:.1f}% (Лаб: {country.lab_assigned_phase_5})\n\n"
            "Управление лабораториями:\n"
            "`/lab_assign [этап 1-5] [кол-во]` - назначить лаб.\n"
            "`/lab_remove [этап 1-5] [кол-во]` - снять лаб.\n\n"
            "⚠️ *Для производства 1 ядерной бомбы требуется 1 лаборатория и 5 военных заводов.*"
        )
        await message.answer(text, parse_mode="Markdown")

@router.message(Command("lab_assign"))
async def cmd_lab_assign(message: Message):
    cfg = get_config()
    lab_building = next((b for b in cfg.buildings if b.building_id == 6), None)
    if not lab_building or not lab_building.enabled:
        await message.answer("❌ Ядерная программа в данный момент отключена.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Использование: `/lab_assign [этап 1-5] [кол-во]`", parse_mode="Markdown")
        return
        
    try:
        phase = int(args[1])
        count = int(args[2])
        if count <= 0 or phase < 1 or phase > 5:
            raise ValueError
    except ValueError:
        await message.answer("❌ Ошибка: Неверные аргументы.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == 6
        ))
        total_labs = cb.total_count if cb else 0
        used_in_prod = sum([p.assigned_factories for p in await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id, CountryProduction.item_id == 21))])
        used_in_research = (country.lab_assigned_phase_1 + country.lab_assigned_phase_2 +
                            country.lab_assigned_phase_3 + country.lab_assigned_phase_4 +
                            country.lab_assigned_phase_5)
        free_labs = total_labs - used_in_prod - used_in_research
        
        if free_labs < count:
            await message.answer(f"❌ Ошибка: Недостаточно свободных лабораторий (доступно: {free_labs}).")
            return
            
        phase_col = f"nuclear_phase_{phase}"
        if getattr(country, phase_col) >= 100:
            await message.answer("❌ Этот этап уже полностью изучен!")
            return
            
        lab_col = f"lab_assigned_phase_{phase}"
        setattr(country, lab_col, getattr(country, lab_col) + count)
        await session.commit()
        await message.answer(f"✅ Назначено {count} лабораторий на этап {phase}.")

@router.message(Command("lab_remove"))
async def cmd_lab_remove(message: Message):
    cfg = get_config()
    lab_building = next((b for b in cfg.buildings if b.building_id == 6), None)
    if not lab_building or not lab_building.enabled:
        await message.answer("❌ Ядерная программа в данный момент отключена.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Использование: `/lab_remove [этап 1-5] [кол-во]`", parse_mode="Markdown")
        return
        
    try:
        phase = int(args[1])
        count = int(args[2])
        if count <= 0 or phase < 1 or phase > 5:
            raise ValueError
    except ValueError:
        await message.answer("❌ Ошибка: Неверные аргументы.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        lab_col = f"lab_assigned_phase_{phase}"
        current_assigned = getattr(country, lab_col)
        
        if current_assigned < count:
            await message.answer(f"❌ Ошибка: На этом этапе назначено только {current_assigned} лабораторий.")
            return
            
        setattr(country, lab_col, current_assigned - count)
        await session.commit()
        await message.answer(f"✅ Снято {count} лабораторий с этапа {phase}.")

@router.message(Command("nuclear_cancel", "stop_nuclear"))
async def cmd_nuclear_cancel(message: Message):
    cfg = get_config()
    lab_building = next((b for b in cfg.buildings if b.building_id == 6), None)
    if not lab_building or not lab_building.enabled:
        await message.answer("❌ Ядерная программа в данный момент отключена.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: 
            return
            
        country.nuclear_phase_1 = 0.0
        country.nuclear_phase_2 = 0.0
        country.nuclear_phase_3 = 0.0
        country.nuclear_phase_4 = 0.0
        country.nuclear_phase_5 = 0.0
        
        country.lab_assigned_phase_1 = 0
        country.lab_assigned_phase_2 = 0
        country.lab_assigned_phase_3 = 0
        country.lab_assigned_phase_4 = 0
        country.lab_assigned_phase_5 = 0
        
        await session.commit()
        await message.answer("🛑 Вы полностью **отменили** и сбросили свою ядерную программу. Все назначенные лаборатории освобождены, прогресс потерян.", parse_mode="Markdown")
