from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select

from database import async_session, User, Country, RoleEnum
from keyboards import get_start_keyboard, get_moderation_keyboard, get_army_keyboard
from engine import get_config

router = Router()

class Registration(StatesGroup):
    name = State()
    ideology = State()
    ruler = State()
    party = State()
    stats = State() # Ожидаем ввод формата: "Стабильность Поддержка" (напр. "80 20")
    area = State()
    flag = State()
    map = State()

class ArmyManage(StatesGroup):
    hire = State()
    demob = State()

@router.callback_query(F.data == "army_hire")
async def army_hire_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ArmyManage.hire)
    await callback.message.answer("◆ Введите количество человек для найма в армию:")
    await callback.answer()

@router.message(ArmyManage.hire)
async def process_army_hire(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Ошибка: Ожидается положительное целое число.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await state.clear()
            return
            
        cfg = get_config()
        cost = count * cfg.game_settings.military_hire_cost_billion
            
        if country.taxpayers < count:
            await message.answer(f"Ошибка: Недостаточно гражданских (доступно {country.taxpayers:,}).")
            return
            
        if country.treasury < cost:
            await message.answer(f"Ошибка: Недостаточно средств в казне. Нужно {cost:.2f} B$, а у вас {country.treasury:.2f} B$.")
            return
            
        country.taxpayers -= count
        country.military += count
        country.treasury -= cost
        await session.commit()
        
        await message.answer(f"✅ Успешно мобилизовано {count:,} чел. в армию за {cost:.2f} B$.")
        await state.clear()

@router.callback_query(F.data == "army_demob")
async def army_demob_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ArmyManage.demob)
    await callback.message.answer("◆ Введите количество военных для демобилизации:")
    await callback.answer()

@router.message(ArmyManage.demob)
async def process_army_demob(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Ошибка: Ожидается положительное целое число.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await state.clear()
            return
            
        if country.military < count:
            await message.answer(f"Ошибка: Недостаточно военных (доступно {country.military:,}).")
            return
            
        country.military -= count
        country.taxpayers += count
        await session.commit()
        
        await message.answer(f"✅ Успешно демобилизовано {count:,} чел. в запас.")
        await state.clear()


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user:
            cfg = get_config()
            role = RoleEnum.root if message.from_user.id == cfg.game_settings.root_admin_id else RoleEnum.player
            
            user = User(telegram_id=message.from_user.id, username=message.from_user.username, role=role)
            session.add(user)
            await session.commit()
            
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        
        if country:
            await message.answer(
                f"◆ Добро пожаловать, правитель страны <b>{country.name}</b>!\n"
                "------------------------------------\n"
                "• /profile - Экономика и статистика\n"
                "• /production - ВПК и склады\n"
                "• /army - Управление армией\n"
                "• /trade - Дипломатия и торговля\n"
                "• /spy - Разведка и диверсии\n"
                "• /guide - Гайд для новичков\n\n"
                "<i>Полный список команд: /help</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "◆ Привет! Я бот для управления страной в ВПИ.\n"
                "------------------------------------\n"
                "У вас еще нет страны. Вы можете зарегистрировать её прямо сейчас.",
                reply_markup=get_start_keyboard()
            )


@router.message(Command("help"))
async def cmd_help(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        is_admin = user and user.role == RoleEnum.root
        
    text = (
        "◆ Справка по командам\n"
        "------------------------------------\n"
        "• /start — Главное меню\n"
        "• /help — Список команд\n"
        "• /guide — Руководство для новичков\n"
        "• /profile — Статистика и экономика страны\n"
        "• /army — Управление армией (найм, демобилизация)\n"
        "• /buildings — Список доступных для постройки зданий\n"
        "• /build [ID здания] [Кол-во] — Построить здания\n"
        "• /production — Просмотр состояния ВПК и складов\n"
        "• /set_prod [ID техники] [ID завода] [Кол-во] — Назначить заводы\n"
        "• /unset_prod [ID техники] [Кол-во|all] — Снять заводы с производства\n"
        "• /util [ID техники] [Кол-во] — Утилизация техники\n"
        "• /spy [ID цели] [Тип операции] — Шпионаж и диверсии\n"
        "• /trade — Торговля\n"
    )
    
    if is_admin:
        text += (
            "------------------------------------\n"
            "◆ Админ-команды\n"
            "------------------------------------\n"
            "• /countries — Список всех стран\n"
            "• /delete_player [ID страны] — Удалить страну\n"
            "• /next_turn — Завершить ход (расчет экономики)\n"
            "• /set_stat [ID страны] [параметр] [значение] — Изменить статы\n"
            "• /add_stat [ID страны] [параметр] [значение] — Добавить статы (можно минус)\n"
            "  *Параметры: treasury (казна), taxpayers (население), military (армия),\n"
            "  stability, war_support, inflation, intel_points, area*\n"
        )
        
    await message.answer(text)

@router.message(Command("profile", "eco", "stats"))
async def cmd_profile(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны! Зарегистрируйтесь через /start.")
            return

        cfg = get_config()
        
        # Calculate stats
        total_population = country.taxpayers + country.military
        pop_str = f"{total_population / 1_000_000:.2f} млн"
        taxpayers_str = f"{country.taxpayers / 1_000_000:.2f} млн"
        
        pop_growth = cfg.game_settings.base_population_growth * 100
        
        tax_income = country.taxpayers * cfg.game_settings.tax_per_taxpayer_billion
        military_upkeep = country.military * cfg.game_settings.military_upkeep_per_soldier_billion
        
        from database import CountryBuilding
        buildings = await session.scalars(select(CountryBuilding).where(CountryBuilding.country_id == country.id))
        
        total_factories = 0
        factory_income = 0.0
        agencies = 0
        
        for b in buildings:
            b_cfg = next((x for x in cfg.buildings if x.building_id == b.building_id), None)
            if b_cfg:
                if getattr(b_cfg, 'income_billion', 0.0) > 0:
                    total_factories += b.total_count
                    factory_income += b.total_count * b_cfg.income_billion
                if getattr(b_cfg, 'name', '') == 'Агентура':
                    agencies += b.total_count
        
        total_income = tax_income + factory_income
        net_income = total_income - military_upkeep
        
        text = (
            f"💰 Экономика страны ({country.name})\n\n"
            f"👥 Население: {pop_str}\n"
            f"👥 Налогоплательщики: {taxpayers_str} (без учета армии)\n"
            f"🏦 Казна: {country.treasury:.2f} B$\n"
            f"📈 Рост населения: {pop_growth:.2f}%\n"
            f"💵 Доход с населения: {tax_income:.2f} B$\n"
        )
        
        if total_factories > 0:
            text += (
                f"🏭 Фабрики: {total_factories} шт\n"
                f"🏭 Доход с фабрик: {factory_income:.2f} B$\n"
                f"🏢 Доход предприятий (чисто): 0.00 B$\n"
            )
            
        text += (
            f"📈 Инфляция: {country.inflation:.1f}%\n"
            f"⚖️ Стабильность: {country.stability:.2f}%\n"
            f"🪖 Поддержка войны: {country.war_support:.1f}%\n"
            f"🪖 Регулярная: {country.military:,}, расход: {military_upkeep:.2f} B$\n"
            f"💰 Чистый доход: {net_income:.2f} B$\n\n"
            f"🕵️ Очки агентуры (ОА): {country.intel_points:.1f} (Агентур: {agencies})"
        )
        
        await message.answer(text)

@router.callback_query(F.data == "register_country")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if country:
            await callback.answer("У вас уже есть страна!", show_alert=True)
            return
            
    await state.set_state(Registration.name)
    await callback.message.edit_text(
        "◆ <b>Регистрация страны: Шаг 1/8</b>\n"
        "------------------------------------\n"
        "Введите название вашей страны.\n\n"
        "<i>Примеры: Германская Империя, СССР, Республика Фиджи...</i>",
        parse_mode="HTML"
    )

@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Registration.ideology)
    await message.answer(
        "◆ <b>Регистрация: Шаг 2/8</b>\n"
        "------------------------------------\n"
        "Введите государственную идеологию.\n\n"
        "<i>Примеры: Коммунизм, Демократия, Фашизм, Монархия...</i>",
        parse_mode="HTML"
    )

@router.message(Registration.ideology)
async def process_ideology(message: Message, state: FSMContext):
    await state.update_data(ideology=message.text)
    await state.set_state(Registration.ruler)
    await message.answer(
        "◆ <b>Регистрация: Шаг 3/8</b>\n"
        "------------------------------------\n"
        "Введите имя правителя (ваше игровое имя или исторического деятеля).\n\n"
        "<i>Примеры: Иосиф Сталин, Уинстон Черчилль, Император Хирохито...</i>",
        parse_mode="HTML"
    )

@router.message(Registration.ruler)
async def process_ruler(message: Message, state: FSMContext):
    await state.update_data(ruler=message.text)
    await state.set_state(Registration.party)
    await message.answer(
        "◆ <b>Регистрация: Шаг 4/8</b>\n"
        "------------------------------------\n"
        "Введите название правящей партии.\n\n"
        "<i>Примеры: КПСС, Консервативная партия, НСДАП...</i>",
        parse_mode="HTML"
    )

@router.message(Registration.party)
async def process_party(message: Message, state: FSMContext):
    await state.update_data(party=message.text)
    await state.set_state(Registration.stats)
    await message.answer(
        "◆ <b>Регистрация: Шаг 5/8</b>\n"
        "------------------------------------\n"
        "Введите два числа через пробел: <b>Стабильность</b> и <b>Поддержку войны</b> (в процентах).\n\n"
        "• Стабильность влияет на устойчивость государства.\n"
        "• Поддержка войны влияет на мобилизацию при военном положении.\n"
        "• <i>Сумма не должна превышать 150%.</i>\n\n"
        "<i>Пример: <code>80 20</code> (80% стаб, 20% война)</i>",
        parse_mode="HTML"
    )

@router.message(Registration.stats)
async def process_stats(message: Message, state: FSMContext):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        stab = float(parts[0])
        war = float(parts[1])
        if stab + war > 150.0:
            await message.answer("Ошибка: Сумма стабильности и поддержки войны не должна превышать 150. Попробуйте еще раз.")
            return
        await state.update_data(stability=stab, war_support=war)
        await state.set_state(Registration.area)
        await message.answer(
            "◆ <b>Регистрация: Шаг 6/8</b>\n"
            "------------------------------------\n"
            "Введите площадь вашей страны в кв. км (от 1 до 150000).\n\n"
            "<i>Пример: <code>120000</code></i>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("Ошибка ввода. Пожалуйста, введите два числа через пробел (например: <code>80 20</code>).", parse_mode="HTML")

@router.message(Registration.area)
async def process_area(message: Message, state: FSMContext):
    try:
        area = float(message.text)
        if area > 150000.0 or area <= 0:
            await message.answer("Ошибка: Площадь должна быть от 1 до 150000. Попробуйте еще раз.")
            return
        await state.update_data(area=area)
        await state.set_state(Registration.flag)
        await message.answer(
            "◆ <b>Регистрация: Шаг 7/8</b>\n"
            "------------------------------------\n"
            "Отправьте картинку (фото) флага вашей страны."
        )
    except ValueError:
        await message.answer("Ошибка ввода. Ожидается число.")

@router.message(Registration.flag, F.photo)
async def process_flag(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(flag=photo_id)
    await state.set_state(Registration.map)
    await message.answer(
        "◆ <b>Регистрация: Шаг 8/8</b>\n"
        "------------------------------------\n"
        "Отправьте картинку (фото) карты вашей страны."
    )

@router.message(Registration.map, F.photo)
async def process_map(message: Message, state: FSMContext, bot: Bot):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Формируем анкету
    anketa = (
        f"◆ Заявка на регистрацию страны\n"
        f"------------------------------------\n"
        f"• Игрок: @{message.from_user.username} (ID: {user_id})\n"
        f"• Название: {data['name']}\n"
        f"• Идеология: {data['ideology']}\n"
        f"• Правитель: {data['ruler']}\n"
        f"• Партия: {data['party']}\n"
        f"• Стабильность: {data['stability']}%\n"
        f"• Поддержка войны: {data['war_support']}%\n"
        f"• Площадь: {data['area']} кв. км"
    )
    
    cfg = get_config()
    
    if user_id == cfg.game_settings.root_admin_id:
        # Авто-апрув для админов
        country = Country(
            owner_id=user_id, name=data['name'], ideology=data['ideology'],
            ruler=data['ruler'], party=data['party'], stability=data['stability'],
            war_support=data['war_support'], area=data['area'],
            flag_photo_id=data['flag'], map_photo_id=photo_id,
            treasury=10.0, taxpayers=1000000, military=1000, martial_law=False,
            built_this_turn=0, inflation=0.0, intel_points=0.0, counter_intel_points=0.0
        )
        async with async_session() as session:
            session.add(country)
            await session.commit()
        await message.answer("✅ Ваша страна была автоматически одобрена!\nВведите /start для управления.")
    else:
        # В реальной задаче кэшируем данные. Сейчас создадим страну и прикрепим статус, если отклонят - удалим.
        country = Country(
            owner_id=user_id, name=data['name'], ideology=data['ideology'],
            ruler=data['ruler'], party=data['party'], stability=data['stability'],
            war_support=data['war_support'], area=data['area'],
            flag_photo_id=data['flag'], map_photo_id=photo_id,
            treasury=10.0, taxpayers=1000000, military=1000, martial_law=False,
            built_this_turn=0, inflation=0.0, intel_points=0.0, counter_intel_points=0.0
        )
        async with async_session() as session:
            session.add(country)
            await session.commit()
            
        try:
            from keyboards import get_moderation_keyboard
            from aiogram.types import InputMediaPhoto
            
            await bot.send_photo(
                chat_id=cfg.game_settings.admin_chat_id,
                photo=data['flag'],
                caption=anketa
            )
            await bot.send_photo(
                chat_id=cfg.game_settings.admin_chat_id,
                photo=photo_id,
                caption="Карта страны"
            )
            await bot.send_message(
                chat_id=cfg.game_settings.admin_chat_id,
                text=f"Действие для заявки от @{message.from_user.username} (ID: {user_id}):",
                reply_markup=get_moderation_keyboard(user_id)
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send to admin chat: {e}")
            pass
        await message.answer("◆ Ваша анкета отправлена на модерацию в закрытый админ чат.")
        
    await state.clear()

@router.callback_query(F.data.startswith("approve_"))
async def approve_country(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(text=callback.message.text + "\n\n✅ ОДОБРЕНО")
    try:
        await bot.send_message(user_id, "✅ Ваша страна одобрена администратором! Введите /start")
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_"))
async def reject_country(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == user_id))
        if country:
            await session.delete(country)
            await session.commit()
            
    await callback.message.edit_text(text=callback.message.text + "\n\n❌ ОТКЛОНЕНО")
    try:
        await bot.send_message(user_id, "❌ Ваша страна была отклонена администратором. Вы можете подать заявку заново через /start.")
    except Exception:
        pass

@router.message(Command("army"))
async def cmd_army(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("У вас нет страны!")
            return
            
        law_status = "Включено 🔴" if country.martial_law else "Выключено 🟢"
        
        await message.answer(
            f"◆ Управление Армией: {country.name}\n"
            f"------------------------------------\n"
            f"• Гражданские: {country.taxpayers:,} чел.\n"
            f"• Военные: {country.military:,} чел.\n"
            f"• Военное положение: {law_status}\n\n"
            f"Выберите действие:",
            reply_markup=get_army_keyboard()
        )

@router.callback_query(F.data == "army_martial_law")
async def toggle_martial_law(callback: CallbackQuery):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if not country:
            return
            
        country.martial_law = not country.martial_law
        await session.commit()
        
        law_status = "Включено 🔴" if country.martial_law else "Выключено 🟢"
        await callback.message.edit_text(
            f"◆ Управление Армией: {country.name}\n"
            f"------------------------------------\n"
            f"• Гражданские: {country.taxpayers:,} чел.\n"
            f"• Военные: {country.military:,} чел.\n"
            f"• Военное положение: {law_status}\n\n"
            f"Выберите действие:",
            reply_markup=get_army_keyboard()
        )
        await callback.answer(f"Военное положение: {'ВКЛ' if country.martial_law else 'ВЫКЛ'}")

@router.message(Command("production"))
async def cmd_production(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("У вас нет страны!")
            return
            
        # Подгружаем здания, продукцию и склады
        from sqlalchemy.orm import selectinload
        country_full = await session.scalar(
            select(Country)
            .options(
                selectinload(Country.buildings),
                selectinload(Country.productions),
                selectinload(Country.stockpiles)
            )
            .where(Country.id == country.id)
        )
        
        cfg = get_config()
        
        response = f"◆ ВПК Страны: {country_full.name}\n------------------------------------\n"
        
        response += "📊 **ЗАГРУЗКА ЗАВОДОВ:**\n"
        # Calculate used factories per building type
        used_factories = {}
        for cp in country_full.productions:
            i_cfg = next((i for i in cfg.items if i.item_id == cp.item_id), None)
            if i_cfg:
                used_factories[i_cfg.required_factory_id] = used_factories.get(i_cfg.required_factory_id, 0) + cp.assigned_factories
                
        for b_cfg in cfg.buildings:
            if b_cfg.building_id in [4, 5]: # Исключаем агентуру и фабрики
                continue
            cb = next((b for b in country_full.buildings if b.building_id == b_cfg.building_id), None)
            total = cb.total_count if cb else 0
            used = used_factories.get(b_cfg.building_id, 0)
            response += f"▫️ {b_cfg.building_id} {b_cfg.name}: {used} / {total}\n"
            
        response += "\n"
        
        # Group items by category
        items_by_category = {}
        for item in cfg.items:
            items_by_category.setdefault(item.category, []).append(item)
            
        for category, items in items_by_category.items():
            response += f"🔹 **{category}**\n"
            for item in items:
                # Find stockpile
                cs = next((s for s in country_full.stockpiles if s.item_id == item.item_id), None)
                amount = cs.amount if cs else 0
                
                # Find production
                cp = next((p for p in country_full.productions if p.item_id == item.item_id), None)
                factories = cp.assigned_factories if cp else 0
                production = factories * item.output_per_factory
                
                # Find building short name
                b_cfg = next((b for b in cfg.buildings if b.building_id == item.required_factory_id), None)
                b_short = b_cfg.short_name if b_cfg else ""
                
                response += f"{item.item_id}. {item.name}: {amount:,}шт / +{production:,}шт {factories}{b_short}\n"
            response += "\n"
                
        response += "\n💡 *Как управлять производством:*\n"
        response += "Назначить: `/set_prod [ID техники] [ID завода] [Количество]`\n"
        response += "Снять: `/unset_prod [ID техники] [Количество|all]`\n"
        
        await message.answer(response, parse_mode="Markdown")
@router.message(Command("spy"))
async def cmd_spy(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
        all_countries = await session.scalars(select(Country).where(Country.id != country.id))
        targets = list(all_countries)
        
        if not targets:
            await message.answer("⚠️ В мире больше нет других стран для шпионажа.")
            return
            
        from keyboards import get_spy_targets_keyboard
        await message.answer(
            f"🕵️ **Разведка (Доступно: {country.intel_points:.1f} ОА)**\n"
            f"------------------------------------\n"
            f"Выберите страну для проведения шпионской операции:",
            reply_markup=get_spy_targets_keyboard(targets),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("spy_target_"))
async def spy_target_selected(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    from keyboards import get_spy_operations_keyboard
    
    async with async_session() as session:
        target = await session.scalar(select(Country).where(Country.id == target_id))
        if not target:
            await callback.answer("❌ Страна не найдена.", show_alert=True)
            return
            
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if not country:
            return
            
        await callback.message.edit_text(
            f"🕵️ **Разведка: {target.name} (ОА: {country.intel_points:.1f})**\n"
            f"------------------------------------\n"
            f"Выберите тип операции:\n"
            f"*(Цены могут быть выше из-за инфляции вашей страны: {country.inflation}%)*",
            reply_markup=get_spy_operations_keyboard(target_id, country.inflation),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("spy_op_"))
async def spy_op_selected(callback: CallbackQuery):
    parts = callback.data.split("_")
    target_id = int(parts[2])
    op_type = int(parts[3])
    
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        target = await session.scalar(select(Country).where(Country.id == target_id))
        
        if not country or not target:
            await callback.answer("❌ Ошибка базы данных.", show_alert=True)
            return
            
        op_costs = {1: 10, 2: 15, 3: 15, 4: 40, 5: 50, 6: 90}
        base_cost = op_costs.get(op_type, 0)
        final_cost = base_cost * (1 + country.inflation / 100.0)
        
        if country.intel_points < final_cost:
            await callback.answer(f"❌ Недостаточно ОА! Нужно: {final_cost:.1f}", show_alert=True)
            return
            
        country.intel_points -= final_cost
        
        res = f"🕵️ Отчет разведки (Цель: {target.name})\n------------------------------------\n"
        if op_type == 1:
            res += f"💰 Казна: {target.treasury:.2f} B$"
        elif op_type == 2:
            res += f"👥 Население: {target.taxpayers:,} чел.\n📈 Рост: Базовый"
        elif op_type == 3:
            res += f"⚖️ Стабильность: {target.stability}%\n⚔️ Поддержка войны: {target.war_support}%"
        elif op_type == 4:
            res += f"🪖 Армия: {target.military:,} чел."
        elif op_type == 5:
            from database import CountryStockpile
            stockpiles = await session.scalars(select(CountryStockpile).where(CountryStockpile.country_id == target.id))
            res += "📦 Склады:\n"
            cfg = get_config()
            has_items = False
            for cs in stockpiles:
                i_cfg = next((i for i in cfg.items if i.item_id == cs.item_id), None)
                name = i_cfg.name if i_cfg else f"ID {cs.item_id}"
                res += f"▫️ {name}: {cs.amount:,} шт.\n"
                has_items = True
            if not has_items:
                res += "Пусто."
        elif op_type == 6:
            from database import CountryProduction
            await session.execute(CountryProduction.__table__.delete().where(CountryProduction.country_id == target.id))
            res += "💥 Диверсия успешно проведена.\nВсе заводы цели сняты с линий производства!"
            
        await session.commit()
        await callback.message.edit_text(res)
        await callback.answer()

@router.message(Command("countries"))
async def cmd_countries(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return

        countries = await session.scalars(select(Country))
        res = "🗺 <b>Список всех стран</b>\n------------------------------------\n"
        count = 0
        import html
        for c in countries:
            owner = await session.scalar(select(User).where(User.telegram_id == c.owner_id))
            username = f"@{html.escape(owner.username)}" if owner and owner.username else f"ID: {c.owner_id}"
            res += f"• <b>{html.escape(c.name)}</b> (ID: {c.id}) | Владелец: {username}\n"
            count += 1
            
        if count == 0:
            res += "Стран пока нет."
            
        await message.answer(res, parse_mode="HTML")

@router.message(Command("delete_player"))
async def cmd_delete_player(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
            
        args = message.text.split()
        if len(args) != 2:
            await message.answer("Использование: `/delete_player [ID_страны]`", parse_mode="Markdown")
            return
            
        try:
            target_country_id = int(args[1])
        except ValueError:
            await message.answer("ID страны должен быть числом.")
            return
            
        target_country = await session.scalar(select(Country).where(Country.id == target_country_id))
        if not target_country:
            await message.answer("❌ Страна с таким ID не найдена.")
            return
            
        owner_id = target_country.owner_id
        
        # We need to delete dependencies first if there are foreign key constraints that aren't cascading
        from database import CountryBuilding, CountryProduction, CountryStockpile, TradeSession
        await session.execute(CountryBuilding.__table__.delete().where(CountryBuilding.country_id == target_country.id))
        await session.execute(CountryProduction.__table__.delete().where(CountryProduction.country_id == target_country.id))
        await session.execute(CountryStockpile.__table__.delete().where(CountryStockpile.country_id == target_country.id))
        
        # We might also want to delete trades where this country is involved
        await session.execute(TradeSession.__table__.delete().where(
            (TradeSession.sender_country_id == target_country.id) | 
            (TradeSession.receiver_country_id == target_country.id)
        ))
        
        await session.delete(target_country)
        
        target_user = await session.scalar(select(User).where(User.telegram_id == owner_id))
        if target_user:
            await session.delete(target_user)
            
        await session.commit()
        await message.answer(f"✅ Страна **{target_country.name}** и её владелец были удалены из игры.", parse_mode="Markdown")

@router.message(Command("buildings"))
async def cmd_buildings(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны! Зарегистрируйтесь через /start.")
            return

        cfg = get_config()
        inflation_mult = 1.0 + (country.inflation / 100.0)
        res = f"◆ Доступные здания (Инфляция: {country.inflation}%)\n------------------------------------\n"
        for b in cfg.buildings:
            if b.enabled:
                desc = f" ({b.description})" if getattr(b, 'description', "") else ""
                actual_cost = b.base_cost_billion * inflation_mult
                res += f"• ID: {b.building_id} | {b.name} — {actual_cost:.2f} B$\n  <i>{desc.strip(' ()')}</i>\n\n"
        await message.answer(res, parse_mode="HTML")

@router.message(Command("build"))
async def cmd_build(message: Message):
    # Синтаксис: /build [building_id] [count]
    args = message.text.split()
    if len(args) != 3:
        await message.answer(
            "◆ Ошибка синтаксиса\n"
            "------------------------------------\n"
            "Использование: `/build [ID_здания] [Количество]`\n"
            "Пример: `/build 1 2`",
            parse_mode="Markdown"
        )
        return
        
    try:
        b_id = int(args[1])
        count = int(args[2])
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Ошибка: ID здания и Количество должны быть положительными числами.")
        return
        
    cfg = get_config()
    building = next((b for b in cfg.buildings if b.building_id == b_id), None)
    
    if not building:
        await message.answer(f"Ошибка: Здание с ID {b_id} не найдено в конфигурации.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("У вас нет страны!")
            return
            
        base_cost = building.base_cost_billion * count
        inflation_mult = 1.0 + (country.inflation / 100.0)
        total_cost = base_cost * inflation_mult
        
        if country.treasury < total_cost:
            await message.answer(
                f"◆ Недостаточно средств\n"
                f"------------------------------------\n"
                f"Требуется: {total_cost:.2f} B$\n"
                f"В казне: {country.treasury:.2f} B$"
            )
            return
            
        # Списываем средства
        country.treasury -= total_cost
        
        # Расчет перегрева экономики
        old_built = country.built_this_turn
        country.built_this_turn += count
        new_built = country.built_this_turn
        
        # За каждые полные 5 зданий сверх 5 добавляется 1%
        # Если было построено 2, а добавилось 4 (стало 6), превышение = 1.
        # Формула: ((new_built - 5) // 5) - (max(0, old_built - 5) // 5)
        if new_built > 5:
            old_penalty = max(0, old_built - 5) // 5
            new_penalty = (new_built - 5) // 5
            inflation_jump = new_penalty - old_penalty
            if inflation_jump > 0:
                country.inflation += float(inflation_jump)
                inf_msg = f"⚠️ Экономика перегрета! Инфляция выросла на {inflation_jump}%."
            else:
                inf_msg = "Инфляция стабильна."
        else:
            inf_msg = "Инфляция стабильна."
            
        # Добавляем здание
        from database import CountryBuilding
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == b_id
        ))
        if not cb:
            cb = CountryBuilding(country_id=country.id, building_id=b_id, total_count=count)
            session.add(cb)
        else:
            cb.total_count += count
            
        await session.commit()
        
        await message.answer(
            f"◆ Успешное строительство\n"
            f"------------------------------------\n"
            f"• Построено: {building.name} ({count} шт.)\n"
            f"• Потрачено: {total_cost:.2f} B$\n"
            f"• Остаток казны: {country.treasury:.2f} B$\n"
            f"• {inf_msg}"
        )

@router.message(Command("set_prod"))
async def cmd_set_prod(message: Message):
    # /set_prod [item_id] [building_id] [count]
    args = message.text.split()
    if len(args) != 4:
        await message.answer("⚠️ Использование: `/set_prod [ID_техники] [ID_завода] [Количество]`", parse_mode="Markdown")
        return
        
    try:
        i_id = int(args[1])
        b_id = int(args[2])
        count = int(args[3])
        if count <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Ошибка: Аргументы должны быть положительными числами.")
        return
        
    cfg = get_config()
    item = next((i for i in cfg.items if i.item_id == i_id), None)
    if not item:
        await message.answer(f"❌ Ошибка: Техника с ID {i_id} не найдена.")
        return
        
    if item.required_factory_id != b_id:
        await message.answer(f"❌ Ошибка: Для этой техники требуется завод с ID {item.required_factory_id}.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        from database import CountryBuilding, CountryProduction
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == b_id
        ))
        
        total_b = cb.total_count if cb else 0
        
        # Считаем, сколько таких заводов уже занято
        all_prods = await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id))
        used_b = 0
        for cp in all_prods:
            c_item = next((i for i in cfg.items if i.item_id == cp.item_id), None)
            if c_item and c_item.required_factory_id == b_id:
                used_b += cp.assigned_factories
                
        free_b = total_b - used_b
        if free_b < count:
            await message.answer(f"❌ Ошибка: Недостаточно свободных заводов (доступно: {free_b}).")
            return
            
        cp = await session.scalar(select(CountryProduction).where(
            CountryProduction.country_id == country.id,
            CountryProduction.item_id == i_id
        ))
        
        if cp:
            cp.assigned_factories += count
        else:
            cp = CountryProduction(country_id=country.id, item_id=i_id, assigned_factories=count)
            session.add(cp)
            
        await session.commit()
        await message.answer(f"✅ Назначено {count} заводов на производство: **{item.name}**.", parse_mode="Markdown")

@router.message(Command("unset_prod"))
async def cmd_unset_prod(message: Message):
    # /unset_prod [item_id] [count|all]
    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Использование: `/unset_prod [ID_техники] [Количество|all]`", parse_mode="Markdown")
        return
        
    try:
        i_id = int(args[1])
        count_str = args[2].lower()
    except ValueError:
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        from database import CountryProduction
        cp = await session.scalar(select(CountryProduction).where(
            CountryProduction.country_id == country.id,
            CountryProduction.item_id == i_id
        ))
        
        if not cp or cp.assigned_factories == 0:
            await message.answer("❌ Ошибка: Нет задействованных заводов на этой линии.")
            return
            
        if count_str == 'all':
            remove_count = cp.assigned_factories
        else:
            try:
                remove_count = int(count_str)
                if remove_count <= 0: raise ValueError
            except ValueError:
                await message.answer("❌ Ошибка: Количество должно быть числом или 'all'.")
                return
                
        if remove_count > cp.assigned_factories:
            remove_count = cp.assigned_factories
            
        cp.assigned_factories -= remove_count
        if cp.assigned_factories == 0:
            await session.delete(cp)
            
        await session.commit()
        await message.answer(f"✅ Снято {remove_count} заводов с линии ID {i_id}.")

@router.message(Command("next_turn"))
async def cmd_next_turn(message: Message, bot: Bot):
    from database import GameState
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            await message.answer("Ошибка: Эта команда доступна только Root-администратору.")
            return

        cfg = get_config()
        countries = await session.scalars(select(Country))
        
        state = await session.scalar(select(GameState))
        if not state:
            state = GameState(turn_number=1)
            session.add(state)
        
        # Увеличиваем ход
        state.turn_number += 1
        current_year = cfg.game_settings.start_year + (state.turn_number * cfg.game_settings.turn_duration_days) // 365
        
        report = f"◆ Отчет о ходе (Ход {state.turn_number}, Год {current_year})\n------------------------------------\n"
        
        for country in countries:
            # 1. Сброс лимита строительства
            country.built_this_turn = 0
            
            # 2. Добыча ОА
            from database import CountryBuilding
            spy_buildings = await session.scalar(
                select(CountryBuilding.total_count)
                .where(CountryBuilding.country_id == country.id, CountryBuilding.building_id == 4)
            )
            spy_count = spy_buildings if spy_buildings else 0
            country.intel_points += spy_count * 10.0
            
            # 3. Авто-мобилизация
            if country.martial_law:
                # min 0.01%, max 0.1% -> 0.0001 to 0.001
                mob_percent = 0.0001 + 0.0009 * (country.war_support / 100.0)
                mob_amount = int(country.taxpayers * mob_percent)
                country.taxpayers -= mob_amount
                country.military += mob_amount
                
            # 4. Естественный прирост
            growth = int(country.taxpayers * cfg.game_settings.base_population_growth)
            country.taxpayers += growth
            
            # 5. Финансы
            tax_income = country.taxpayers * cfg.game_settings.tax_per_taxpayer_billion
            if country.martial_law:
                tax_income *= 0.5 # штраф -50% (было 30%)
                
            # Доход от фабрик (id=5)
            factory_buildings = await session.scalar(
                select(CountryBuilding.total_count)
                .where(CountryBuilding.country_id == country.id, CountryBuilding.building_id == 5)
            )
            factory_count = factory_buildings if factory_buildings else 0
            factory_income = factory_count * 0.3 # 0.3 B$ per factory
            
            tax_income += factory_income
                
            upkeep = country.military * cfg.game_settings.military_upkeep_per_soldier_billion
            
            country.treasury += tax_income
            country.treasury -= upkeep
            
            # 6. Производство
            from database import CountryProduction, CountryStockpile
            productions = await session.scalars(
                select(CountryProduction)
                .where(CountryProduction.country_id == country.id)
            )
            for cp in productions:
                i_cfg = next((i for i in cfg.items if i.item_id == cp.item_id), None)
                if i_cfg:
                    produced = cp.assigned_factories * i_cfg.output_per_factory
                    cs = await session.scalar(
                        select(CountryStockpile)
                        .where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == cp.item_id)
                    )
                    if not cs:
                        cs = CountryStockpile(country_id=country.id, item_id=cp.item_id, amount=produced)
                        session.add(cs)
                    else:
                        cs.amount += produced

            try:
                msg = (
                    f"◆ Новый Ход! (Год {current_year})\n"
                    f"------------------------------------\n"
                    f"• Доход (Налоги + Фабрики): +{tax_income:.2f} B$\n"
                    f"• Содержание армии: -{upkeep:.2f} B$\n"
                    f"• Прирост населения: +{growth:,} чел.\n"
                    f"• Очки агентуры (ОА): +{spy_count * 10.0} ОА\n"
                    f"• Текущая казна: {country.treasury:.2f} B$"
                )
                await bot.send_message(country.owner_id, msg)
            except Exception:
                pass
                
        await session.commit()
        await message.answer(f"✅ Ход {state.turn_number} успешно завершен! Сводки отправлены игрокам. Текущий год: {current_year}.")

@router.message(Command("set_stat"))
async def cmd_set_stat(message: Message):
    # /set_stat [тег_страны/ID] [параметр] [значение]
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            await message.answer("Ошибка: Эта команда доступна только Root-администратору.")
            return

        args = message.text.split()
        if len(args) != 4:
            await message.answer("Использование: `/set_stat [ID_страны] [параметр] [значение]`", parse_mode="Markdown")
            return
            
        c_id_str = args[1]
        param = args[2]
        val_str = args[3]
        
        try:
            c_id = int(c_id_str)
            country = await session.scalar(select(Country).where(Country.id == c_id))
            if not country:
                await message.answer("Ошибка: Страна с таким ID не найдена.")
                return
                
            if hasattr(country, param):
                col_type = type(getattr(country, param))
                if col_type == int:
                    setattr(country, param, int(val_str))
                elif col_type == float:
                    setattr(country, param, float(val_str))
                elif col_type == bool:
                    setattr(country, param, val_str.lower() in ('true', '1', 'yes'))
                else:
                    setattr(country, param, val_str)
                    
                await session.commit()
                await message.answer(f"✅ Параметр {param} страны {country.name} (ID: {country.id}) изменен на {val_str}.")
            else:
                await message.answer("Ошибка: Неверный параметр.")
                
        except ValueError:
            await message.answer("Ошибка: Неверный формат значения.")

@router.message(Command("util"))
@router.message(Command("scrap"))
async def cmd_util(message: Message):
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: `/util [ID_техники] [Количество]`", parse_mode="Markdown")
        return
        
    try:
        i_id = int(args[1])
        count = int(args[2])
        if count <= 0: raise ValueError
    except ValueError:
        await message.answer("Ошибка: Аргументы должны быть положительными числами.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        from database import CountryStockpile
        cs = await session.scalar(select(CountryStockpile).where(
            CountryStockpile.country_id == country.id,
            CountryStockpile.item_id == i_id
        ))
        
        if not cs or cs.amount < count:
            avail = cs.amount if cs else 0
            await message.answer(f"Ошибка: Недостаточно техники на складе (доступно: {avail:,}).")
            return
            
        cs.amount -= count
        if cs.amount == 0:
            await session.delete(cs)
            
        await session.commit()
        await message.answer(f"✅ Успешно утилизировано {count:,} ед. техники (ID {i_id}).")


@router.message(Command("add_stat"))
async def cmd_add_stat(message: Message):
    # /add_stat [тег_страны/ID] [параметр] [значение]
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            await message.answer("Ошибка: Эта команда доступна только Root-администратору.")
            return

        args = message.text.split()
        if len(args) != 4:
            await message.answer("Использование: `/add_stat [ID_страны] [параметр] [значение]`", parse_mode="Markdown")
            return
            
        c_id_str = args[1]
        param = args[2]
        val_str = args[3]
        
        try:
            c_id = int(c_id_str)
            country = await session.scalar(select(Country).where(Country.id == c_id))
            if not country:
                await message.answer("Ошибка: Страна с таким ID не найдена.")
                return
                
            if hasattr(country, param):
                col_type = type(getattr(country, param))
                current_val = getattr(country, param)
                if col_type == int:
                    setattr(country, param, current_val + int(val_str))
                elif col_type == float:
                    setattr(country, param, current_val + float(val_str))
                else:
                    await message.answer("Ошибка: Этот параметр нельзя увеличить/уменьшить (он не числовой).")
                    return
                    
                await session.commit()
                await message.answer(f"✅ Параметр {param} страны {country.name} (ID: {country.id}) изменен. Новое значение: {getattr(country, param)}.")
            else:
                await message.answer("Ошибка: Неверный параметр.")
                
        except ValueError:
            await message.answer("Ошибка: Неверный формат ID или значения.")
        except Exception as e:
            await message.answer(f"Непредвиденная ошибка: {e}")


@router.message(Command("guide"))
async def cmd_guide(message: Message):
    text = (
        "◆ <b>Подробное руководство для новичков</b>\n"
        "------------------------------------\n"
        "Добро пожаловать в бота управления страной ВПИ! Здесь вы берете под свой контроль целое государство.\n\n"
        "🏛 <b>Основы экономики:</b>\n"
        "• Ваша казна пополняется за счет налогов с населения и гражданских фабрик.\n"
        "• Содержание армии стоит денег. Чем больше армия, тем больше расходы.\n"
        "• Следите за инфляцией! Если строить слишком много зданий за один ход (больше 5), экономика перегреется и цены вырастут.\n\n"
        "⚙️ <b>Производство (ВПК):</b>\n"
        "• Военные заводы производят технику и вооружение.\n"
        "• Для производства техники нужны заводы определенного типа (например, Военный завод для винтовок).\n"
        "• Команды: <code>/buildings</code>, <code>/build</code>, <code>/production</code>, <code>/set_prod</code>.\n\n"
        "⚔️ <b>Военное положение:</b>\n"
        "Команда <code>/army</code> позволяет включить 🔴 <b>Военное положение</b>. \n"
        "<b>Плюсы:</b> Каждый ход часть гражданских автоматически мобилизуется в армию (зависит от Поддержки войны).\n"
        "<b>Минусы:</b> Сильнейший удар по экономике! Сбор налогов с населения падает на 50%, так как экономика перестраивается на военные рельсы.\n\n"
        "🕵️ <b>Разведка и Шпионаж:</b>\n"
        "• Здание «Агентура» каждый ход приносит Очки Агентуры (ОА).\n"
        "• За ОА можно узнавать данные о других странах (экономику, армию) или проводить диверсии (остановка их заводов).\n"
        "• Команда: <code>/spy</code>.\n\n"
        "🤝 <b>Торговля:</b>\n"
        "• Вы можете обмениваться деньгами и техникой с другими странами.\n"
        "• Команда: <code>/trade</code>.\n\n"
        "<i>Используйте <code>/help</code> для просмотра всех команд!</i>"
    )
    await message.answer(text, parse_mode="HTML")
