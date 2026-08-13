from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import async_session, Country, CountryBuilding
from sqlalchemy import select
from engine import get_config

router = Router()

@router.message(Command("generator"))
async def cmd_generator(message: Message):
    cfg = get_config()
    if not getattr(cfg.game_settings, 'frostpunk_event', False):
        await message.answer("❌ Событие Frostpunk сейчас не активно.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return

        generators_built = getattr(country, 'generators_built', 0)
        gen_progress = getattr(country, 'generator_progress', 0.0)
        assigned = getattr(country, 'factories_assigned_to_generator', 0)

        heat_level = getattr(country, 'generator_heat_level', 0)
        radius_level = getattr(country, 'generator_radius_level', 0)

        capacity_per_gen = 2000000 + (radius_level * 500000)
        total_capacity = generators_built * capacity_per_gen

        heat_cost = 5.0 + (heat_level * 5.0)
        radius_cost = 5.0 + (radius_level * 5.0)
        
        # 0.2 bonus per generator (20% for 1 generator? No, 0.2 is 0.2% or 20%? The user said "даёт бонус 0.2 к рождаемости", 
        # let's assume it means +0.2% per generator just like standard percentages, or literally +0.2 base.
        # But wait, we calculate growth_bonus to show to the user, let's just say "0.2" literally in the multiplier).
        # We will use 0.002 in math, so it's 0.2%.
        growth_bonus = (generators_built * 0.2) + (heat_level * 1.0)

        heated_people = min(country.taxpayers, total_capacity)
        freezing_people = max(0, country.taxpayers - heated_people)

        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == 5
        ))
        total_factories = cb.total_count if cb else 0

        text = (
            "❄️ **Управление Генераторами (Событие Frostpunk)**\n"
            "------------------------------------\n"
            f"🏭 **Построено генераторов:** {generators_built}\n"
            f"📊 **Прогресс следующего:** {gen_progress * 100:.1f}%\n"
            f"👷 **Назначено фабрик:** {assigned} из {total_factories}\n"
            "   *(10 фабрик строят 1 генератор за ход)*\n"
            "   Управление: `/gen_assign [кол-во]`, `/gen_remove [кол-во]`\n\n"
            "♨️ **Улучшения (действуют на все генераторы):**\n"
            f"🔥 **Уровень отопления:** {heat_level}\n"
            f"   *(Общий бонус к рождаемости: +{growth_bonus:.1f}% для обогретых)*\n"
            f"   🔼 Улучшить: `/upgrade_generator heat` (Цена: {heat_cost} B$)\n\n"
            f"📡 **Уровень радиуса:** {radius_level}\n"
            f"   *(Вместимость одного генератора: {capacity_per_gen:,})*\n"
            f"   🔼 Улучшить: `/upgrade_generator radius` (Цена: {radius_cost} B$)\n\n"
            f"👥 **Ваше население:** {country.taxpayers:,}\n"
            f"♨️ **В тепле:** {heated_people:,} / {total_capacity:,}\n"
            f"🥶 **Мерзнут (штраф стабы):** {freezing_people:,}\n"
            f"   *(Каждый 1 млн мерзнущих дает -1% к стабильности за ход)*"
        )
        await message.answer(text, parse_mode="Markdown")

@router.message(Command("gen_assign"))
async def cmd_gen_assign(message: Message):
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

        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == 5
        ))
        total_factories = cb.total_count if cb else 0
        assigned = getattr(country, 'factories_assigned_to_generator', 0)
        free_factories = total_factories - assigned

        if free_factories < count:
            await message.answer(f"❌ Ошибка: У вас недостаточно свободных фабрик. Свободно: {free_factories}.")
            return

        country.factories_assigned_to_generator = assigned + count
        await session.commit()
        await message.answer(f"✅ Назначено {count} фабрик на постройку Генераторов.")

@router.message(Command("gen_remove"))
async def cmd_gen_remove(message: Message):
    cfg = get_config()
    if not getattr(cfg.game_settings, 'frostpunk_event', False):
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Использование: `/gen_remove [кол-во]`", parse_mode="Markdown")
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

        assigned = getattr(country, 'factories_assigned_to_generator', 0)

        if assigned < count:
            await message.answer(f"❌ Ошибка: Вы пытаетесь снять больше фабрик, чем назначено ({assigned}).")
            return

        country.factories_assigned_to_generator = assigned - count
        await session.commit()
        await message.answer(f"✅ Снято {count} фабрик с постройки Генераторов.")

@router.message(Command("upgrade_generator"))
async def cmd_upgrade_generator(message: Message):
    cfg = get_config()
    if not getattr(cfg.game_settings, 'frostpunk_event', False):
        return

    args = message.text.split()
    if len(args) != 2 or args[1] not in ["heat", "radius"]:
        await message.answer("⚠️ Использование: `/upgrade_generator [heat|radius]`", parse_mode="Markdown")
        return
        
    type_ = args[1]
    
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        if type_ == "heat":
            current_level = getattr(country, 'generator_heat_level', 0)
            cost = 5.0 + (current_level * 5.0)
            
            if country.treasury < cost:
                await message.answer(f"❌ Недостаточно средств. Нужно {cost} B$.")
                return
                
            country.treasury -= cost
            country.generator_heat_level = current_level + 1
            await session.commit()
            await message.answer(f"✅ Общий уровень отопления повышен до {current_level + 1}! (-{cost} B$)")
            
        elif type_ == "radius":
            current_level = getattr(country, 'generator_radius_level', 0)
            cost = 5.0 + (current_level * 5.0)
            
            if country.treasury < cost:
                await message.answer(f"❌ Недостаточно средств. Нужно {cost} B$.")
                return
                
            country.treasury -= cost
            country.generator_radius_level = current_level + 1
            await session.commit()
            await message.answer(f"✅ Общий радиус обогрева повышен до {current_level + 1}! (-{cost} B$)")
