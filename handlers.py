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
    religion = State()
    stats = State() # Ожидаем ввод формата: "Стабильность Поддержка" (напр. "80 20")
    area = State()
    flag = State()
    map = State()

class ArmyManage(StatesGroup):
    hire = State()
    demob = State()

class ExpandState(StatesGroup):
    army = State()
    population = State()
    vehicles = State()
    map = State()

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
        "• /profile, /eco — Статистика и экономика страны\n"
        "• /army — Управление армией (найм, демобилизация)\n"
        "• /buildings, /build — Справочник и постройка зданий\n        • /destroy — Снос здания (без возврата средств)\n"
        "• /production, /prod — Просмотр состояния ВПК и складов\n"
        "• /rate, /rates — Нормы производства техники (за 1 завод)\n"
        "• /set_prod, /unset_prod — Назначение и снятие заводов\n"
        "• /util [ID техники] [Кол-во] — Утилизация техники\n"
        "• /spy — Шпионаж и диверсии\n"
        "• /trade — Торговля с другими странами\n"
        
        "• /nuclear, /nuke — Ядерная программа\n"
        "• /lab_assign, /lab_remove — Назначить/Снять военные заводы и лаборатории\n"
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
            "• /add_stat [ID страны] [параметр] [значение] — Добавить статы\n"
            "• /world_stat [параметр] [значение] — Установить точное значение стата ВСЕМ странам мира (рождаемость и др.)\n"
            "• /world_event [параметр] [значение] [Текст] — Добавить/отнять статы у ВСЕХ стран мира с рассылкой\n"
            "  *Параметры: treasury, taxpayers, military, stability, war_support, inflation, intel_points, area, growth_modifier*\n"
        )
        
    await message.answer(text)

@router.message(Command("rate", "rates"))
async def cmd_rate(message: Message):
    cfg = get_config()
    
    res = "📊 <b>Объемы производства (с 1 завода)</b>\n"
    res += "------------------------------------\n"
    
    categories = {}
    for i in cfg.items:
        if i.category not in categories:
            categories[i.category] = []
        categories[i.category].append(i)
        
    for cat, items in categories.items():
        res += f"\n🔹 <b>{cat}</b>:\n"
        for i in items:
            b_cfg = next((b for b in cfg.buildings if b.building_id == i.required_factory_id), None)
            b_name = b_cfg.name if b_cfg else f"Завод ID {i.required_factory_id}"
            
            # Format output neatly
            if i.output_per_factory >= 1000:
                output_str = f"{int(i.output_per_factory):,}".replace(",", " ") + " шт."
            elif i.output_per_factory < 1:
                output_str = f"{i.output_per_factory:.2f} шт."
            else:
                output_str = f"{int(i.output_per_factory)} шт."
                
            res += f"  • {i.name}: {output_str} (Требует: {b_name})\n"
            
    await message.answer(res, parse_mode="HTML")

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
        
        # Stability Modifiers
        stab = country.stability
        stab_tax_mult = 1.10 if stab >= 80 else (0.50 if stab < 20 else (0.80 if stab < 40 else 1.0))
        stab_growth_bonus = 0.2 if stab >= 90 else (-0.6 if stab < 20 else (-0.2 if stab < 40 else 0.0))

        pop_growth = cfg.game_settings.base_population_growth + getattr(country, 'growth_modifier', 0.0) + stab_growth_bonus
        pop_growth = round(pop_growth, 2)
        
        tax_income = country.taxpayers * cfg.game_settings.tax_per_taxpayer_billion
        if country.martial_law:
            tax_income *= 0.5 # Военное положение: штраф 50% на налоги
            
        war_upkeep_mult = 0.9 if country.war_support >= 80 else 1.0
        military_upkeep = country.military * cfg.game_settings.military_upkeep_per_soldier_billion * war_upkeep_mult
        
        from database import CountryBuilding
        buildings = await session.scalars(select(CountryBuilding).where(CountryBuilding.country_id == country.id))
        
        total_factories = 0
        factory_income = 0.0
        agencies = 0
        
        for b in buildings:
            b_cfg = next((x for x in cfg.buildings if x.building_id == b.building_id), None)
            if not b_cfg: continue
            
            if b.building_id == 5:
                total_factories += b.total_count
                factory_income += b.total_count * getattr(b_cfg, 'income_billion', 0.0)
            elif getattr(b_cfg, 'income_billion', 0.0) > 0:
                factory_income += b.total_count * getattr(b_cfg, 'income_billion', 0.0)
                
            if b.building_id == 4:
                agencies += b.total_count

        # Apply stability modifier to total income
        tax_income *= stab_tax_mult
        factory_income *= stab_tax_mult
        
        net_income = tax_income + factory_income - military_upkeep

        text = (
            f"👤 <b>Профиль страны: {country.name}</b>\n"
            f"------------------------------------\n"
            f"🏛 Идеология: {country.ideology}\n"
            f"🕍 Религия: {getattr(country, 'religion', 'Не указана')}\n"
            f"👑 Правитель: {country.ruler}\n"
            f"------------------------------------\n"
            f"💰 Казна: {country.treasury:.2f} B$\n"
            f"👥 Население: {country.taxpayers / 1000000:.2f} млн. чел. (Прирост: {pop_growth}%)\n"
            f"💵 Налоги: {tax_income:.2f} B$\n"
        )
        
        if total_factories > 0:
            text += (
                f"🏭 Фабрики: {total_factories} шт\n"
                f"🏭 Доход с фабрик: {factory_income:.2f} B$\n"
            )
            
        stab_eff = ""
        if stab_tax_mult == 1.1: stab_eff = " (+10% к налогам и фабрикам)"
        elif stab_tax_mult == 0.8: stab_eff = " (-20% к налогам и фабрикам)"
        elif stab_tax_mult == 0.5: stab_eff = " (-50% к налогам и фабрикам)"
            
        text += (
            f"📈 Инфляция: {country.inflation:.1f}%\n"
            f"⚖️ Эффект стабильности:{stab_eff}\n"
            f"⚖️ Стабильность: {country.stability:.2f}%\n"
            f"🪖 Поддержка войны: {country.war_support:.1f}%" + (" (-10% к содержанию, +10% к пр-ву)\n" if country.war_support >= 80 else "\n") + (
            f"🪖 Регулярная армия: {country.military:,} чел., расход: {military_upkeep:.2f} B$\n")
            f"💰 Чистый доход: {net_income:.2f} B$\n\n"
            f"🕵️ Очки агентуры (ОА): {country.intel_points:.1f} (Агентур: {agencies})\n"
            f"🛡 Контрразведка: {country.counter_intel_points:.1f} ОА"
        )
        
        await message.answer(text, parse_mode="HTML")
@router.callback_query(F.data == "register_country")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        if country:
            await callback.answer("У вас уже есть страна!", show_alert=True)
            return
            
    await state.set_state(Registration.name)
    await callback.message.edit_text("◆ Введите название вашей страны:")

@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Registration.ideology)
    await message.answer("◆ Введите идеологию:")

@router.message(Registration.ideology)
async def process_ideology(message: Message, state: FSMContext):
    await state.update_data(ideology=message.text)
    await state.set_state(Registration.ruler)
    await message.answer("◆ Введите имя правителя:")

@router.message(Registration.ruler)
async def process_ruler(message: Message, state: FSMContext):
    await state.update_data(ruler=message.text)
    await state.set_state(Registration.party)
    await message.answer("◆ Введите название правящей партии:")

@router.message(Registration.party)
async def process_party(message: Message, state: FSMContext):
    await state.update_data(party=message.text)
    await state.set_state(Registration.religion)
    await message.answer("◆ Введите государственную религию:")

@router.message(Registration.religion)
async def process_religion(message: Message, state: FSMContext):
    await state.update_data(religion=message.text)
    await state.set_state(Registration.stats)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🕊 Экономика и процветание (100% / 50%)")],
            [KeyboardButton(text="⚔️ Милитаризм и экспансия (50% / 100%)")],
            [KeyboardButton(text="⚖️ Золотая середина (75% / 75%)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "◆ Выберите путь развития вашей страны:\n"
        "------------------------------------\n"
        "От этого выбора будет зависеть баланс Стабильности и Поддержки войны.\n\n"
        "🕊 <b>Экономика и процветание:</b> Стабильность 100%, Поддержка войны 50%\n(<b>+10%</b> к налогам и фабрикам, <b>+0.2%</b> к приросту населения каждый ход).\n\n"
        "⚔️ <b>Милитаризм:</b> Стабильность 50%, Поддержка войны 100%\n(<b>-20%</b> к налогам и фабрикам, отток населения <b>-0.2%</b>, но <b>-10%</b> к содержанию армии и <b>+10%</b> к производству оружия).\n\n"
        "⚖️ <b>Золотая середина:</b> Стабильность 75%, Поддержка войны 75%\n(Без бонусов и без штрафов).\n\n"
        "<i>(Выбирайте с умом, изменить этот параметр будет тяжело)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(Registration.stats)
async def process_stats(message: Message, state: FSMContext):
    text = message.text
    if "100%" in text and "50%" in text:
        stab, war = 100.0, 50.0
    elif "50%" in text and "100%" in text:
        stab, war = 50.0, 100.0
    elif "75%" in text and "75%" in text:
        stab, war = 75.0, 75.0
    else:
        await message.answer("❌ Пожалуйста, используйте кнопки на клавиатуре для выбора.")
        return
        
    await state.update_data(stability=stab, war_support=war)
    await state.set_state(Registration.area)
    
    from aiogram.types import ReplyKeyboardRemove
    await message.answer("◆ Введите площадь страны в кв. км (не более 150000):", reply_markup=ReplyKeyboardRemove())

@router.message(Registration.area)
async def process_area(message: Message, state: FSMContext):
    try:
        area = float(message.text)
        if area > 150000.0 or area <= 0:
            await message.answer("Ошибка: Площадь должна быть от 1 до 150000. Попробуйте еще раз.")
            return
        await state.update_data(area=area)
        await state.set_state(Registration.flag)
        await message.answer("◆ Отправьте фото флага вашей страны:")
    except ValueError:
        await message.answer("Ошибка ввода. Ожидается число.")

@router.message(Registration.flag, F.photo | F.document)
async def process_flag(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await state.update_data(flag=photo_id)
    await state.set_state(Registration.map)
    await message.answer("◆ Отправьте фото карты вашей страны:")

@router.message(Registration.map, F.photo | F.document)
async def process_map(message: Message, state: FSMContext, bot: Bot):
    photo_id = message.photo[-1].file_id if message.photo else message.document.file_id
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
        f"• Религия: {data.get('religion', 'Не указана')}\n"
        f"• Стабильность: {data['stability']}%\n"
        f"• Поддержка войны: {data['war_support']}%\n"
        f"• Площадь: {data['area']} кв. км"
    )
    
    # Сохраняем анкету во временное хранилище (в реальном проекте лучше в БД в статус pending)
    # Здесь для упрощения мы сразу создадим страну, но без флага is_approved,
    # однако в ТЗ нет флага is_approved, так что мы просто отправим админам на валидацию.
    # Так как нам нужно прокинуть данные, проще сохранить страну в БД и одобрить/отклонить ее потом.
    # Но чтобы не усложнять, мы сохраним анкету в state.
    
    cfg = get_config()
    
    if user_id == cfg.game_settings.root_admin_id:
        # Авто-апрув для админов (или если админов нет)
        country = Country(
            owner_id=user_id, name=data['name'], ideology=data['ideology'],
            ruler=data['ruler'], party=data['party'], religion=data.get('religion', 'Не указана'),
            stability=data['stability'], war_support=data['war_support'], area=data['area'],
            flag_photo_id=data['flag'], map_photo_id=photo_id,
            treasury=10.0, taxpayers=1000000, military=1000, martial_law=False,
            built_this_turn=0, inflation=0.0, intel_points=0.0, counter_intel_points=0.0
        )
        async with async_session() as session:
            session.add(country)
            await session.commit()
            
        await message.answer("✅ Ваша страна была автоматически одобрена!\nВведите /start для управления.")
        
        # Announce in public chat
        public_chat = cfg.game_settings.public_chat_id
        reg_thread = getattr(cfg.game_settings, 'registration_thread_id', None)
        if public_chat:
            short_anketa = (
                f"🎉 <b>Новая страна на политической арене!</b>\n\n"
                f"🏳️ <b>Название:</b> {data['name']}\n"
                f"🏛 <b>Идеология:</b> {data['ideology']}\n"
                f"👑 <b>Правитель:</b> {data['ruler']}\n"
                f"🕍 <b>Религия:</b> {data.get('religion', 'Не указана')}"
            )
            try:
                await bot.send_photo(
                    chat_id=public_chat,
                    message_thread_id=reg_thread,
                    photo=data['flag'],
                    caption=short_anketa,
                    parse_mode="HTML"
                )
            except Exception as e:
                import logging
                logging.error(f"Failed to send public reg notification: {e}")
    else:
        # В реальной задаче кэшируем данные. Сейчас создадим страну и прикрепим статус, если отклонят - удалим.
        country = Country(
            owner_id=user_id, name=data['name'], ideology=data['ideology'],
            ruler=data['ruler'], party=data['party'], religion=data.get('religion', 'Не указана'),
            stability=data['stability'], war_support=data['war_support'], area=data['area'],
            flag_photo_id=data['flag'], map_photo_id=photo_id,
            treasury=10.0, taxpayers=1000000, military=1000, martial_law=False,
            built_this_turn=0, inflation=0.0, intel_points=0.0, counter_intel_points=0.0
        )
        async with async_session() as session:
            session.add(country)
            await session.commit()
            
        try:
            from keyboards import get_moderation_keyboard
            await bot.send_photo(
                chat_id=cfg.game_settings.admin_chat_id, photo=data['flag'], caption=f"Флаг страны: {data['name']}"
            )
            await bot.send_photo(
                chat_id=cfg.game_settings.admin_chat_id, photo=photo_id, caption=anketa,
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
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ ОДОБРЕНО")
    try:
        await bot.send_message(user_id, "✅ Ваша страна одобрена администратором! Введите /start")
    except Exception:
        pass
        
    # Public announcement
    cfg = get_config()
    public_chat = cfg.game_settings.public_chat_id
    reg_thread = getattr(cfg.game_settings, 'registration_thread_id', None)
    
    if public_chat:
        async with async_session() as session:
            country = await session.scalar(select(Country).where(Country.owner_id == user_id))
            if country:
                short_anketa = (
                    f"🎉 <b>Новая страна на политической арене!</b>\n\n"
                    f"🏳️ <b>Название:</b> {country.name}\n"
                    f"🏛 <b>Идеология:</b> {country.ideology}\n"
                    f"👑 <b>Правитель:</b> {country.ruler}\n"
                    f"🕍 <b>Религия:</b> {getattr(country, 'religion', 'Не указана')}"
                )
                try:
                    await bot.send_photo(
                        chat_id=public_chat,
                        message_thread_id=reg_thread,
                        photo=country.flag_photo_id,
                        caption=short_anketa,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    import logging
                    logging.error(f"Failed to send public reg notification: {e}")

@router.callback_query(F.data.startswith("reject_"))
async def reject_country(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == user_id))
        if country:
            await session.delete(country)
            await session.commit()
            
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ ОТКЛОНЕНО")
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

@router.message(Command("production", "prod"))
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
            if b_cfg.building_id == 4: # Исключаем агентуру
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
            f"Выберите страну для проведения шпионской операции:\n*(Для перевода ОА в контрразведку используйте /counter_intel [кол-во])*:",
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
        
        # Counter-intelligence check
        if target.counter_intel_points >= final_cost:
            target.counter_intel_points -= final_cost
            await session.commit()
            await callback.message.edit_text(f"🚨 ПРОВАЛ ОПЕРАЦИИ 🚨\nКонтрразведка {target.name} перехватила ваших агентов! Вы потеряли {final_cost:.1f} ОА.")
            await callback.answer()
            return
        elif target.counter_intel_points > 0:
            target.counter_intel_points = 0
        
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


@router.message(Command("counter_intel"))
async def cmd_counter_intel(message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: `/counter_intel [кол-во]`", parse_mode="Markdown")
        return
    try:
        amount = float(args[1])
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Количество должно быть положительным числом.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country: return
        
        if country.intel_points < amount:
            await message.answer(f"❌ Недостаточно Очков Агентуры (ОА). Доступно: {country.intel_points:.1f}")
            return
            
        country.intel_points -= amount
        country.counter_intel_points += amount
        await session.commit()
        await message.answer(f"✅ Переведено {amount:.1f} ОА в контрразведку. Теперь там {country.counter_intel_points:.1f} ОА.")

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
                res += f"• ID: {b.building_id} | {b.name} — {actual_cost:.2f} B$  <i>{desc.strip(' ()')}</i>\n\n"
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
        
        # -----------------------------
        # УЯЗВИМОСТЬ: Проверка на изученность ядерной бомбы
        # -----------------------------
        if i_id == 21: # Ядерная бомба
            completed = all([
                getattr(country, 'nuclear_phase_1', 0) >= 100,
                getattr(country, 'nuclear_phase_2', 0) >= 100,
                getattr(country, 'nuclear_phase_3', 0) >= 100,
                getattr(country, 'nuclear_phase_4', 0) >= 100,
                getattr(country, 'nuclear_phase_5', 0) >= 100
            ])
            if not completed:
                await message.answer("❌ Ошибка: Ядерная программа еще не изучена полностью!")
                return
        
        from database import CountryBuilding, CountryProduction
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == b_id
        ))
        
        total_b = cb.total_count if cb else 0
        
        all_prods = await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id))
        all_prods = list(all_prods)
        
        # Считаем, сколько таких заводов уже занято (как основных, так и вспомогательных)
        used_b = 0
        for cp in all_prods:
            c_item = next((i for i in cfg.items if i.item_id == cp.item_id), None)
            if c_item:
                if c_item.required_factory_id == b_id:
                    used_b += cp.assigned_factories
                if getattr(c_item, 'secondary_factory_id', None) == b_id:
                    used_b += cp.assigned_factories * getattr(c_item, 'secondary_factory_count', 1)
                
        # Если здание b_id - это лаборатория (6), нужно еще учесть те, что на исследованиях!
        if b_id == 6:
            used_in_research = (getattr(country, 'lab_assigned_phase_1', 0) + 
                                getattr(country, 'lab_assigned_phase_2', 0) + 
                                getattr(country, 'lab_assigned_phase_3', 0) + 
                                getattr(country, 'lab_assigned_phase_4', 0) + 
                                getattr(country, 'lab_assigned_phase_5', 0))
            used_b += used_in_research
                
        free_b = total_b - used_b
        if free_b < count:
            await message.answer(f"❌ Ошибка: Недостаточно свободных заводов (доступно: {free_b}).")
            return
            
        # -----------------------------
        # УЯЗВИМОСТЬ: Проверка на вспомогательные заводы (например, 5 военных заводов для бомбы)
        # -----------------------------
        sec_b_id = getattr(item, 'secondary_factory_id', None)
        if sec_b_id:
            sec_count_needed = count * getattr(item, 'secondary_factory_count', 1)
            
            cb_sec = await session.scalar(select(CountryBuilding).where(
                CountryBuilding.country_id == country.id,
                CountryBuilding.building_id == sec_b_id
            ))
            total_sec_b = cb_sec.total_count if cb_sec else 0
            
            used_sec_b = 0
            for cp in all_prods:
                c_item = next((i for i in cfg.items if i.item_id == cp.item_id), None)
                if c_item:
                    if c_item.required_factory_id == sec_b_id:
                        used_sec_b += cp.assigned_factories
                    if getattr(c_item, 'secondary_factory_id', None) == sec_b_id:
                        used_sec_b += cp.assigned_factories * getattr(c_item, 'secondary_factory_count', 1)
            
            # Если sec_b_id - лаборатория, учитываем исследования
            if sec_b_id == 6:
                used_in_research = (getattr(country, 'lab_assigned_phase_1', 0) + 
                                    getattr(country, 'lab_assigned_phase_2', 0) + 
                                    getattr(country, 'lab_assigned_phase_3', 0) + 
                                    getattr(country, 'lab_assigned_phase_4', 0) + 
                                    getattr(country, 'lab_assigned_phase_5', 0))
                used_sec_b += used_in_research
            
            free_sec_b = total_sec_b - used_sec_b
            if free_sec_b < sec_count_needed:
                await message.answer(f"❌ Ошибка: Недостаточно вспомогательных заводов (ID {sec_b_id}). Нужно: {sec_count_needed}, свободно: {free_sec_b}.")
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
        
        sec_msg = f" (и {sec_count_needed} вспомог. заводов)" if sec_b_id else ""
        await message.answer(f"✅ Успешно назначено {count} заводов{sec_msg} на линию ID {i_id}.")

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


@router.message(Command("util"))
async def cmd_util(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Использование: `/util [ID техники] [Количество]`", parse_mode="Markdown")
        return
        
    try:
        item_id = int(args[1])
        amount = int(args[2])
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ ID техники и количество должны быть положительными числами.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
        from database import CountryStockpile
        stock = await session.scalar(
            select(CountryStockpile)
            .where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == item_id)
        )
        
        if not stock or stock.amount < amount:
            await message.answer(f"❌ У вас нет столько техники (ID: {item_id}) на складе!")
            return
            
        stock.amount -= amount
        
        # Optionally, give some money back? 
        # The user said "утилизации денег" which might mean they want money back.
        # Let's give back a small fraction of cost, or maybe just scrap it.
        # Let's read config
        cfg = get_config()
        i_cfg = next((i for i in cfg.items if i.item_id == item_id), None)
        item_name = i_cfg.name if i_cfg else "Неизвестно"
        
        if stock.amount == 0:
            await session.delete(stock)
            
        await session.commit()
        await message.answer(f"✅ Успешно утилизировано {amount} шт. техники: {item_name}.")

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
                mob_percent = 0.0001 + 0.0009 * (country.war_support / 100.0)
                mob_amount = int(country.taxpayers * mob_percent)
                country.taxpayers -= mob_amount
                country.military += mob_amount
                    
            # Stability Modifiers
            stab = country.stability
            stab_tax_mult = 1.10 if stab >= 80 else (0.50 if stab < 20 else (0.80 if stab < 40 else 1.0))
            stab_growth_bonus = 0.2 if stab >= 90 else (-0.6 if stab < 20 else (-0.2 if stab < 40 else 0.0))

            # 4. Естественный прирост
            base_mod = (cfg.game_settings.base_population_growth + getattr(country, "growth_modifier", 0.0) + stab_growth_bonus) / 100.0
            growth = int(country.taxpayers * base_mod)
            country.taxpayers += growth
            if country.taxpayers < 0:
                country.taxpayers = 0

            # 5. Финансы
            tax_income = country.taxpayers * cfg.game_settings.tax_per_taxpayer_billion
            if country.martial_law:
                tax_income *= 0.5 # штраф -50%
                
            # Доход от всех зданий
            factory_income = 0.0
            
            buildings = await session.scalars(select(CountryBuilding).where(CountryBuilding.country_id == country.id))
            
            for b in buildings:
                b_cfg = next((x for x in cfg.buildings if x.building_id == b.building_id), None)
                if b_cfg and getattr(b_cfg, 'income_billion', 0.0) > 0:
                    factory_income += b.total_count * b_cfg.income_billion
                        
            tax_income *= stab_tax_mult
            factory_income *= stab_tax_mult
            
            tax_income += factory_income
                
            war_upkeep_mult = 0.9 if country.war_support >= 80 else 1.0
            upkeep = country.military * cfg.game_settings.military_upkeep_per_soldier_billion * war_upkeep_mult
            
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
                    war_prod_mult = 1.1 if country.war_support >= 80 else 1.0
                    produced = cp.assigned_factories * i_cfg.output_per_factory * war_prod_mult
                    cs = await session.scalar(
                        select(CountryStockpile)
                        .where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == cp.item_id)
                    )
                    if not cs:
                        cs = CountryStockpile(country_id=country.id, item_id=cp.item_id, amount=produced)
                        session.add(cs)
                    else:
                        cs.amount += produced

            # 7. Ядерная программа
            for phase in range(1, 6):
                lab_col = f"lab_assigned_phase_{phase}"
                prog_col = f"nuclear_phase_{phase}"
                assigned = getattr(country, lab_col, 0)
                current_prog = getattr(country, prog_col, 0)
                
                if assigned > 0 and current_prog < 100:
                    # Пусть 1 лаборатория дает 10% за ход
                    new_prog = current_prog + (assigned * 10.0)
                    if new_prog > 100: new_prog = 100.0
                    setattr(country, prog_col, new_prog)
                    
                    if new_prog >= 100 and current_prog < 100:
                        setattr(country, lab_col, 0) # Автоматически снимаем лаборатории после завершения
            
            
            personal_report = (
                f"📅 <b>Новый Ход! (Год {current_year})</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 <b>Финансы:</b>\n"
                f"➕ Доход: +{tax_income:.2f} B$\n"
                f"➖ Содержание армии: -{upkeep:.2f} B$\n"
                f"🏦 Итого в казне: {country.treasury:.2f} B$\n\n"
                f"👥 <b>Демография:</b>\n"
                f"📈 Прирост населения: {'+' if growth >= 0 else ''}{growth:,} чел.\n"
            )
            if spy_count > 0:
                personal_report += (
                    f"\n🕵️ <b>Спецслужбы:</b>\n"
                    f"➕ Получено ОА: +{spy_count * 10.0:.1f} ОА\n"
                )
                
            try:
                await bot.send_message(country.owner_id, personal_report, parse_mode="HTML")
            except Exception:
                pass
                



        await session.commit()
        

            
        # Уведомление о новом ходе
        try:
            await bot.send_message(
                chat_id=cfg.game_settings.public_chat_id,
                message_thread_id=cfg.game_settings.public_chat_thread_id,
                text=f"🔔 <b>НАЧАЛСЯ НОВЫЙ ХОД (ГОД {current_year})</b> 🔔\n\nИгроки могут обновить свои ресурсы и продолжить действия.",
                parse_mode="HTML"
            )
        except Exception:
            pass
            
        await message.answer("Ход успешно завершен!")

@router.message(Command("expand"))
async def cmd_expand(message: Message, state: FSMContext):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
        from database import GameState
        game_state = await session.scalar(select(GameState))
        turn = game_state.turn_number if game_state else 1
        last_expand = getattr(country, 'last_expand_turn', 0) or 0
        if turn - last_expand < 3:
            await message.answer(f"❌ Вы не можете расширяться так часто! Ждите {3 - (turn - last_expand)} хода.")
            return
            
        await state.set_state(ExpandState.army)
        await message.answer("◆ Введите количество человек для экспедиции (из армии):")

@router.message(ExpandState.army)
async def process_expand_army(message: Message, state: FSMContext):
    try:
        army = int(message.text)
        if army < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if army > country.military:
            await message.answer(f"❌ У вас нет столько войск! Доступно: {country.military}")
            return
            
    await state.update_data(army=army)
    await state.set_state(ExpandState.population)
    await message.answer("◆ Введите количество колонистов (из населения):")

@router.message(ExpandState.population)
async def process_expand_population(message: Message, state: FSMContext):
    try:
        pop = int(message.text)
        if pop < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if pop > country.taxpayers:
            await message.answer(f"❌ У вас нет столько населения! Доступно: {country.taxpayers}")
            return
            
    await state.update_data(population=pop)
    await state.set_state(ExpandState.vehicles)
    await message.answer("◆ Введите технику через запятую (Формат: ID количество), или напишите 'Нет':")

@router.message(ExpandState.vehicles)
async def process_expand_vehicles(message: Message, state: FSMContext):
    text_input = message.text.strip().lower()
    vehicles = {}
    if text_input != 'нет':
        try:
            parts = message.text.split(',')
            for p in parts:
                v_id, count = map(int, p.strip().split())
                if count <= 0: raise ValueError
                vehicles[v_id] = vehicles.get(v_id, 0) + count
        except Exception:
            await message.answer("❌ Ошибка формата! Пример: '1 10, 2 5' или 'Нет'")
            return
            
        async with async_session() as session:
            country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
            from database import CountryStockpile
            for v_id, count in vehicles.items():
                stock = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == v_id))
                if not stock or stock.amount < count:
                    await message.answer(f"❌ Недостаточно техники ID {v_id} на складе!")
                    return
                    
    await state.update_data(vehicles=vehicles)
    await state.set_state(ExpandState.map)
    await message.answer("◆ Отправьте фото карты с вашей заявкой на расширение:")

@router.message(ExpandState.map, F.photo)
async def process_expand_map(message: Message, state: FSMContext, bot: Bot):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    user_id = message.from_user.id
    
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == user_id))
        
        country.military -= data['army']
        country.taxpayers -= data['population']
        
        vehicles_dict = data.get('vehicles', {})
        v_text = ""
        cfg = get_config()
        if vehicles_dict:
            from database import CountryStockpile
            for v_id, v_count in vehicles_dict.items():
                stock = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == v_id))
                stock.amount -= v_count
                
                i_cfg = next((i for i in cfg.items if i.item_id == v_id), None)
                name = i_cfg.name if i_cfg else "Неизвестно"
                v_text += f"\nID {v_id}: {v_count} шт. ({name})"
        else:
            v_text = "\nНет"
            
        from database import GameState, ExpandRequest
        game_state = await session.scalar(select(GameState))
        turn = game_state.turn_number if game_state else 1
        country.last_expand_turn = turn
        
        import json
        req = ExpandRequest(
            user_id=user_id,
            army=data['army'],
            population=data['population'],
            vehicles=json.dumps(vehicles_dict),
            photo_id=photo_id
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)
        req_id = req.id
        
        anketa = (
            f"🗺 **Запрос на расширение #{req_id}**\n"
            f"От страны: {country.name}\n"
            f"Солдат: {data['army']}\n"
            f"Колонистов: {data['population']}\n"
            f"Техника:{v_text}\n\n"
            f"Для модерации используйте:\n"
            f"`/exp_approve {req_id} [Текст результата]`\n"
            f"`/exp_reject {req_id} [Причина]`"
        )
        
        try:
            await bot.send_photo(chat_id=cfg.game_settings.admin_chat_id, photo=photo_id, caption=anketa, parse_mode="Markdown")
        except Exception:
            pass
            
        await message.answer("✅ Ваш запрос на расширение отправлен на проверку администратору. Войска и ресурсы временно списаны. В случае отклонения они вернутся.")
        await state.clear()

@router.message(ExpandState.map)
async def fallback_expand_map(message: Message):
    await message.answer("❌ Пожалуйста, отправьте фото!")

@router.message(Command("exp_approve"))
async def cmd_exp_approve(message: Message, bot: Bot):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            return
            
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Использование: `/exp_approve [ID] [Комментарий]`", parse_mode="Markdown")
        return
        
    try:
        req_id = int(args[1])
    except ValueError:
        return
        
    comment = args[2] if len(args) > 2 else "Нет комментария"
    
    async with async_session() as session:
        from database import ExpandRequest
        req = await session.get(ExpandRequest, req_id)
        if not req:
            await message.answer("Заявка не найдена.")
            return
            
        import expand_events
        import random
        # 70% шанс на успех/нейтрал
        if random.random() < 0.7:
            ev = random.choice(expand_events.GOOD_EVENTS)
        else:
            ev = random.choice(expand_events.BAD_EVENTS)
            
        event_text = ev["text"]
        
        country = await session.scalar(select(Country).where(Country.owner_id == req.user_id))
        if country:
            country.treasury += ev.get("money", 0)
            
        await session.delete(req)
        await session.commit()
        
        result_msg = (
            f"🗺 **Результаты расширения**\n"
            f"Комментарий ГМ: {comment}\n\n"
            f"События в экспедиции:\n"
            f"{event_text}"
        )
        
        try:
            await bot.send_message(req.user_id, result_msg, parse_mode="Markdown")
        except:
            pass
            
        await message.answer(f"✅ Заявка #{req_id} одобрена.")

@router.message(Command("exp_reject"))
async def cmd_exp_reject(message: Message, bot: Bot):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            return
            
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Использование: `/exp_reject [ID] [Причина]`", parse_mode="Markdown")
        return
        
    try:
        req_id = int(args[1])
    except ValueError:
        return
        
    comment = args[2] if len(args) > 2 else "Нет комментария"
    
    async with async_session() as session:
        from database import ExpandRequest
        req = await session.get(ExpandRequest, req_id)
        if not req:
            await message.answer("Заявка не найдена.")
            return
            
        country = await session.scalar(select(Country).where(Country.owner_id == req.user_id))
        if country:
            country.military += req.army
            country.taxpayers += req.population
            
            import json
            from database import CountryStockpile
            vehicles = json.loads(req.vehicles)
            for v_id_str, count in vehicles.items():
                v_id = int(v_id_str)
                stock = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == v_id))
                if stock:
                    stock.amount += count
                else:
                    session.add(CountryStockpile(country_id=country.id, item_id=v_id, amount=count))
                    
        await session.delete(req)
        await session.commit()
        
        result_msg = (
            f"❌ Ваша заявка отклонена.\n"
            f"Комментарий ГМ: {comment}\n\n"
            f"Все выделенные войска, колонисты и техника возвращены."
        )
        
        try:
            await bot.send_message(req.user_id, result_msg, parse_mode="Markdown")
        except:
            pass
            
        await message.answer(f"✅ Заявка #{req_id} отклонена.")

@router.message(Registration.flag)
async def fallback_flag(message: Message):
    await message.answer("❌ Пожалуйста, отправьте фото (флаг)!")

@router.message(Registration.map)
async def fallback_map(message: Message):
    await message.answer("❌ Пожалуйста, отправьте фото (карту)!")


@router.message(Command("set_stat"))
async def cmd_set_stat(message: Message, bot: Bot):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            return
            
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("Использование: `/set_stat [ID страны] [параметр] [значение]`", parse_mode="Markdown")
        return
        
    try:
        c_id = int(args[1])
        param = args[2]
        val = float(args[3])
    except ValueError:
        await message.answer("❌ Неверный формат чисел.")
        return
        
    async with async_session() as session:
        country = await session.get(Country, c_id)
        if not country:
            await message.answer("❌ Страна не найдена.")
            return
            
        if not hasattr(country, param):
            await message.answer(f"❌ Параметр `{param}` не найден у страны.", parse_mode="Markdown")
            return
            
        setattr(country, param, val)
        await session.commit()
        await message.answer(f"✅ У страны {country.name} параметр `{param}` установлен на {val}", parse_mode="Markdown")


@router.message(Command("add_stat"))
async def cmd_add_stat(message: Message, bot: Bot):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            return
            
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("Использование: `/add_stat [ID страны] [параметр] [значение]`", parse_mode="Markdown")
        return
        
    try:
        c_id = int(args[1])
        param = args[2]
        val = float(args[3])
    except ValueError:
        await message.answer("❌ Неверный формат чисел.")
        return
        
    async with async_session() as session:
        country = await session.get(Country, c_id)
        if not country:
            await message.answer("❌ Страна не найдена.")
            return
            
        if not hasattr(country, param):
            await message.answer(f"❌ Параметр `{param}` не найден у страны.", parse_mode="Markdown")
            return
            
        old_val = getattr(country, param)
        try:
            old_val = float(old_val)
        except (ValueError, TypeError):
            await message.answer(f"❌ Параметр `{param}` не является числом.", parse_mode="Markdown")
            return
            
        setattr(country, param, old_val + val)
        await session.commit()
        await message.answer(f"✅ У страны {country.name} параметр `{param}` изменён на {val}. Теперь: {old_val + val}", parse_mode="Markdown")


@router.message(Command("add_item"))
async def cmd_add_item(message: Message, bot: Bot):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not user or user.role != RoleEnum.root:
            return
            
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("Использование: `/add_item [ID страны] [ID техники/вещи] [количество]`", parse_mode="Markdown")
        return
        
    try:
        c_id = int(args[1])
        item_id = int(args[2])
        amount = float(args[3])
    except ValueError:
        await message.answer("❌ Неверный формат чисел.")
        return
        
    async with async_session() as session:
        country = await session.get(Country, c_id)
        if not country:
            await message.answer("❌ Страна не найдена.")
            return
            
        cfg = get_config()
        item_cfg = next((i for i in cfg.items if i.item_id == item_id), None)
        if not item_cfg:
            await message.answer(f"❌ Техника с ID {item_id} не найдена в конфигурации.")
            return

        from database import CountryStockpile
        stock = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == country.id, CountryStockpile.item_id == item_id))
        
        if not stock:
            if amount > 0:
                stock = CountryStockpile(country_id=country.id, item_id=item_id, amount=amount)
                session.add(stock)
            else:
                await message.answer(f"❌ У страны нет этой техники на складе, нельзя отнять.")
                return
        else:
            stock.amount += amount
            if stock.amount < 0:
                stock.amount = 0
                
        await session.commit()
        await message.answer(f"✅ У страны {country.name} техника '{item_cfg.name}' (ID {item_id}) изменена на {amount}. Теперь на складе: {stock.amount}")


@router.message(Command("guide"))
async def cmd_guide(message: Message):
    text = (
        "◆ Руководство по механикам ВПИ\n"
        "------------------------------------\n"
        "Добро пожаловать в бота управления страной!\n\n"
        "📝 Регистрация: Название, Идеология, Правитель, Партия.\n\n"
        "🏛 Экономика, Налоги и Демография (/profile)\n"
        "• Казна в B$. Налоги поступают каждый ход от населения.\n"
        "• Инфляция: массовое строительство перегревает экономику, снижая доход.\n"
        "• <b>Стабильность:</b> Напрямую влияет на доходы и рождаемость.\n"
        "  - <b>≥ 80%:</b> Экономический бум (+10% к налогам и доходу с фабрик), высокий прирост населения (+0.2% к базовому).\n"
        "  - <b>< 40%:</b> Забастовки и миграция (-20% к доходам, -0.2% прирост).\n"
        "  - <b>< 20%:</b> Коллапс (-50% к доходам, массовая убыль населения).\n\n"
        "🏭 ВПК и Строительство (/buildings, /build)\n"
        "• Заводы приносят пассивный доход и дают мощности.\n"
        "• Нормы производства смотрите через /rate.\n"
        "• /set_prod назначает заводы на выпуск вооружения.\n"
        "• Ненужную технику можно разобрать (/util).\n\n"
        "🪖 Армия (/army)\n"
        "• Нанимайте солдат. Отрицательный баланс приводит к дезертирству!\n\n"
        "🕵️ Шпионаж (/spy) и Торговля (/trade)\n"
        "• Контрразведка: Агентурные сети пассивно генерируют Очки Разведки (ОА), которые автоматически защищают страну от диверсий врага.\n"
        "• Через торговлю можно передавать технику и деньги союзникам.\n\n"
        "☢️ Ядерная программа (/nuclear)\n"
        "• Для производства бомб нужна 1 Лаборатория и 5 Военных заводов.\n"
        "• Сначала исследуйте все этапы проекта, назначив заводы (/lab_assign), и только после этого можно производить само оружие.\n\n"
        "⚠️ Каждый ход администратор начисляет налоги и завершает строительство."
    )
    await message.answer(text, parse_mode="HTML")


# ==========================================
# СИСТЕМА РЕФОРМ (С БЮДЖЕТОМ И ОПИСАНИЕМ)
# ==========================================
class ReformState(StatesGroup):
    waiting_for_money = State()
    waiting_for_desc = State()

@router.message(Command("reform"))
async def cmd_reform(message: Message, state: FSMContext):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
    await state.set_state(ReformState.waiting_for_money)
    await message.answer(
        "📜 <b>Проведение реформы</b>\n\n"
        "Какую сумму (B$) вы хотите выделить на эту реформу?\n"
        f"<i>Доступно в казне: {country.treasury:.2f} B$</i>",
        parse_mode="HTML"
    )

@router.message(ReformState.waiting_for_money)
async def process_reform_money(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное положительное число.")
        return

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await state.clear()
            return
            
        if amount > country.treasury:
            await message.answer(f"❌ Недостаточно средств! В казне всего: {country.treasury:.2f} B$")
            return

    await state.update_data(reform_amount=amount)
    await state.set_state(ReformState.waiting_for_desc)
    await message.answer(
        "Напишите краткое описание реформы (или отправьте '-' если без описания):"
    )

@router.message(ReformState.waiting_for_desc)
async def process_reform_desc(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("reform_amount", 0.0)
    desc = message.html_text
    if desc.strip() == '-':
        desc = "<i>Без описания</i>"

    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await state.clear()
            return

        # Deduct money
        country.treasury -= amount
        await session.commit()
        
        msg_text = (
            f"✅ <b>Реформа успешно проведена!</b>\n\n"
            f"📜 <b>Новая реформа: {country.name}</b>\n"
            f"💰 Выделено средств: <b>{amount:.2f} B$</b>\n\n"
            f"📝 Описание:\n{desc}"
        )
        
        try:
            await bot.send_message(chat_id=message.from_user.id, text=msg_text, parse_mode="HTML")
            if message.chat.type != "private":
                await message.answer(f"✅ Реформа успешно проведена! Списано {amount:.2f} B$. Подробности отправлены в ЛС.")
        except Exception:
            # Fallback if bot cannot DM the user
            await message.answer(msg_text, parse_mode="HTML")

    await state.clear()

@router.message(Command("destroy", "demolish"))
async def cmd_destroy(message: Message):
    # Синтаксис: /destroy [building_id] [count]
    args = message.text.split()
    if len(args) != 3:
        await message.answer(
            "◆ Ошибка синтаксиса\n"
            "------------------------------------\n"
            "Использование: `/destroy [ID_здания] [Количество]`\n"
            "Пример: `/destroy 1 2`",
            parse_mode="Markdown"
        )
        return
        
    try:
        b_id = int(args[1])
        count = int(args[2])
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Ошибка: ID здания и Количество должны быть положительными числами.")
        return
        
    cfg = get_config()
    building = next((b for b in cfg.buildings if b.building_id == b_id), None)
    
    if not building:
        await message.answer(f"❌ Ошибка: Здание с ID {b_id} не найдено.")
        return
        
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
        from database import CountryBuilding, CountryProduction
        cb = await session.scalar(select(CountryBuilding).where(
            CountryBuilding.country_id == country.id,
            CountryBuilding.building_id == b_id
        ))
        
        if not cb or cb.total_count < count:
            await message.answer(f"❌ У вас нет столько зданий этого типа. Доступно для сноса: {cb.total_count if cb else 0}.")
            return
            
        # Проверяем, не заняты ли эти здания на производстве
        all_prods = await session.scalars(select(CountryProduction).where(CountryProduction.country_id == country.id))
        all_prods = list(all_prods)
        
        used_b = 0
        for cp in all_prods:
            c_item = next((i for i in cfg.items if i.item_id == cp.item_id), None)
            if c_item:
                if c_item.required_factory_id == b_id:
                    used_b += cp.assigned_factories
                if getattr(c_item, 'secondary_factory_id', None) == b_id:
                    used_b += cp.assigned_factories * getattr(c_item, 'secondary_factory_count', 1)
        
        if b_id == 6:
            used_in_research = (getattr(country, 'lab_assigned_phase_1', 0) + 
                                getattr(country, 'lab_assigned_phase_2', 0) + 
                                getattr(country, 'lab_assigned_phase_3', 0) + 
                                getattr(country, 'lab_assigned_phase_4', 0) + 
                                getattr(country, 'lab_assigned_phase_5', 0))
            used_b += used_in_research
            
        free_b = cb.total_count - used_b
        
        if count > free_b:
            await message.answer(
                f"❌ Ошибка: Вы пытаетесь снести здания, которые сейчас используются!\n"
                f"Всего зданий: {cb.total_count}, занято: {used_b}, свободно: {free_b}.\n"
                f"Сперва освободите их (снимите производство: `/unset_prod`, либо остановите изучение ядерной программы)."
            )
            return
            
        cb.total_count -= count
        if cb.total_count == 0:
            await session.delete(cb)
            
        await session.commit()
        
        await message.answer(
            f"✅ Вы успешно снесли {count} шт. здания «{building.name}».\n"
            f"Средства за снос не возвращаются."
        )
