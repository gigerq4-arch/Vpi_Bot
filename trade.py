from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import async_session, Country, TradeSession, TradeStatusEnum, CountryStockpile
from engine import get_config

router = Router()

class TradeState(StatesGroup):
    waiting_for_give = State()
    waiting_for_want = State()

def get_trade_keyboard(trade_id: int, is_sender: bool, is_draft: bool):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if is_draft and is_sender:
        builder.button(text="➕ Предложить", callback_data=f"trade_addgive_{trade_id}")
        builder.button(text="➕ Попросить", callback_data=f"trade_addwant_{trade_id}")
        builder.button(text="📨 Отправить предложение", callback_data=f"trade_send_{trade_id}")
        builder.button(text="❌ Отменить", callback_data=f"trade_cancel_{trade_id}")
        builder.adjust(2, 1, 1)
    elif not is_draft and not is_sender:
        builder.button(text="✅ Принять", callback_data=f"trade_accept_{trade_id}")
        builder.button(text="❌ Отклонить", callback_data=f"trade_decline_{trade_id}")
        builder.adjust(2)
    return builder.as_markup()

def format_slots(slots: dict, cfg):
    text = ""
    money = slots.get('money', 0)
    if money > 0:
        text += f"• Деньги: {money:.2f} B$\n"
    
    items = slots.get('items', {})
    if items:
        for item_id_str, amount in items.items():
            item_id = int(item_id_str)
            item_cfg = next((i for i in cfg.items if i.item_id == item_id), None)
            name = item_cfg.name if item_cfg else f"ID {item_id}"
            text += f"• {name}: {amount:,} шт.\n"
            
    if not text:
        text = "• Ничего\n"
    return text

@router.message(Command("trade"))
async def cmd_trade(message: Message):
    async with async_session() as session:
        country = await session.scalar(select(Country).where(Country.owner_id == message.from_user.id))
        if not country:
            await message.answer("❌ У вас нет страны!")
            return
            
        all_countries = await session.scalars(select(Country).where(Country.id != country.id))
        targets = list(all_countries)
        
        if not targets:
            await message.answer("⚠️ В мире больше нет других стран для торговли.")
            return
            
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for t in targets:
            builder.button(text=f"🤝 {t.name}", callback_data=f"trade_start_{t.id}")
        builder.adjust(2)
        
        await message.answer(
            f"🤝 **Торговля**\n"
            f"------------------------------------\n"
            f"Выберите страну для торгового предложения:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("trade_start_"))
async def trade_start(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        sender = await session.scalar(select(Country).where(Country.owner_id == callback.from_user.id))
        target = await session.scalar(select(Country).where(Country.id == target_id))
        if not sender or not target:
            await callback.answer("Ошибка базы данных.", show_alert=True)
            return
            
        trade = TradeSession(
            sender_country_id=sender.id,
            receiver_country_id=target.id,
            sender_slots={"money": 0.0, "items": {}},
            receiver_slots={"money": 0.0, "items": {}},
            status=TradeStatusEnum.active
        )
        session.add(trade)
        await session.commit()
        await session.refresh(trade)
        
        cfg = get_config()
        text = (
            f"🤝 **Торговое предложение (Черновик)**\n"
            f"Получатель: {target.name}\n\n"
            f"**Вы отдаете:**\n{format_slots(trade.sender_slots, cfg)}\n"
            f"**Вы просите:**\n{format_slots(trade.receiver_slots, cfg)}"
        )
        
        await callback.message.edit_text(text, reply_markup=get_trade_keyboard(trade.id, True, True), parse_mode="Markdown")

@router.callback_query(F.data.startswith("trade_cancel_"))
async def trade_cancel(callback: CallbackQuery):
    trade_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        trade = await session.scalar(select(TradeSession).where(TradeSession.id == trade_id))
        if not trade:
            await callback.answer("Сделка не найдена.", show_alert=True)
            return
        trade.status = TradeStatusEnum.cancelled
        await session.commit()
        await callback.message.edit_text("❌ Торговое предложение отменено.")

@router.callback_query(F.data.startswith("trade_addgive_"))
async def trade_addgive(callback: CallbackQuery, state: FSMContext):
    trade_id = int(callback.data.split("_")[2])
    await state.update_data(trade_id=trade_id)
    await state.set_state(TradeState.waiting_for_give)
    await callback.message.answer(
        "📝 Введите что хотите отдать.\n"
        "Формат для денег: `money [сумма]` (например, `money 10.5`)\n"
        "Формат для техники: `[ID_техники] [количество]` (например, `1 1000`)\n"
        "Введите `отмена` для отмены.",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("trade_addwant_"))
async def trade_addwant(callback: CallbackQuery, state: FSMContext):
    trade_id = int(callback.data.split("_")[2])
    await state.update_data(trade_id=trade_id)
    await state.set_state(TradeState.waiting_for_want)
    await callback.message.answer(
        "📝 Введите что хотите попросить.\n"
        "Формат для денег: `money [сумма]` (например, `money 10.5`)\n"
        "Формат для техники: `[ID_техники] [количество]` (например, `1 1000`)\n"
        "Введите `отмена` для отмены.",
        parse_mode="Markdown"
    )
    await callback.answer()

async def process_slot_input(message: Message, state: FSMContext, is_give: bool):
    text = message.text.lower()
    if text == "отмена":
        await state.clear()
        await message.answer("Ввод отменен. Откройте сообщение с торговлей для продолжения.")
        return
        
    parts = text.split()
    if len(parts) != 2:
        await message.answer("❌ Неверный формат. Ожидается: `[тип/ID] [количество]`", parse_mode="Markdown")
        return
        
    data = await state.get_data()
    trade_id = data.get('trade_id')
    
    async with async_session() as session:
        trade = await session.scalar(select(TradeSession).where(TradeSession.id == trade_id))
        if not trade:
            await message.answer("Сделка не найдена.")
            await state.clear()
            return
            
        slots = dict(trade.sender_slots) if is_give else dict(trade.receiver_slots)
        
        if parts[0] == "money":
            try:
                amount = float(parts[1])
                if amount < 0: raise ValueError
                slots['money'] = slots.get('money', 0) + amount
            except ValueError:
                await message.answer("❌ Неверная сумма денег.")
                return
        else:
            try:
                item_id = int(parts[0])
                amount = int(parts[1])
                if amount < 0: raise ValueError
                
                cfg = get_config()
                if not any(i.item_id == item_id for i in cfg.items):
                    await message.answer(f"❌ Техника с ID {item_id} не найдена.")
                    return
                    
                if 'items' not in slots:
                    slots['items'] = {}
                # In JSON we use string keys
                str_id = str(item_id)
                slots['items'][str_id] = slots['items'].get(str_id, 0) + amount
            except ValueError:
                await message.answer("❌ Неверный ID или количество.")
                return
                
        if is_give:
            # Need to assign a completely new dict to trigger SQLAlchemy JSON mutation detection properly
            # Or use flag_modified
            from sqlalchemy.orm.attributes import flag_modified
            trade.sender_slots = slots
            flag_modified(trade, "sender_slots")
        else:
            from sqlalchemy.orm.attributes import flag_modified
            trade.receiver_slots = slots
            flag_modified(trade, "receiver_slots")
            
        await session.commit()
        await state.clear()
        
        # We should edit the original message, but we don't have its ID easily accessible without saving it.
        # So we just send a new one.
        cfg = get_config()
        receiver = await session.scalar(select(Country).where(Country.id == trade.receiver_country_id))
        
        text = (
            f"🤝 **Торговое предложение (Черновик)**\n"
            f"Получатель: {receiver.name}\n\n"
            f"**Вы отдаете:**\n{format_slots(trade.sender_slots, cfg)}\n"
            f"**Вы просите:**\n{format_slots(trade.receiver_slots, cfg)}"
        )
        
        await message.answer(text, reply_markup=get_trade_keyboard(trade.id, True, True), parse_mode="Markdown")

@router.message(TradeState.waiting_for_give)
async def trade_input_give(message: Message, state: FSMContext):
    await process_slot_input(message, state, True)

@router.message(TradeState.waiting_for_want)
async def trade_input_want(message: Message, state: FSMContext):
    await process_slot_input(message, state, False)

@router.callback_query(F.data.startswith("trade_send_"))
async def trade_send(callback: CallbackQuery, bot: Bot):
    trade_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        trade = await session.scalar(select(TradeSession).where(TradeSession.id == trade_id))
        if not trade or trade.sender_ready:
            await callback.answer("Сделка уже отправлена или не найдена.", show_alert=True)
            return
            
        trade.sender_ready = True
        
        sender = await session.scalar(select(Country).where(Country.id == trade.sender_country_id))
        receiver = await session.scalar(select(Country).where(Country.id == trade.receiver_country_id))
        
        # Check if sender actually has what they offer
        money = trade.sender_slots.get('money', 0)
        if sender.treasury < money:
            await callback.answer("❌ У вас недостаточно денег для этой сделки!", show_alert=True)
            return
            
        for item_id_str, amount in trade.sender_slots.get('items', {}).items():
            cs = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == sender.id, CountryStockpile.item_id == int(item_id_str)))
            if not cs or cs.amount < amount:
                await callback.answer("❌ У вас недостаточно техники для этой сделки!", show_alert=True)
                return
                
        await session.commit()
        
        await callback.message.edit_text("✅ Торговое предложение отправлено!", parse_mode="Markdown")
        
        cfg = get_config()
        text = (
            f"🤝 **Новое торговое предложение!**\n"
            f"Отправитель: {sender.name}\n\n"
            f"**Вам предлагают:**\n{format_slots(trade.sender_slots, cfg)}\n"
            f"**У вас просят:**\n{format_slots(trade.receiver_slots, cfg)}"
        )
        
        try:
            await bot.send_message(receiver.owner_id, text, reply_markup=get_trade_keyboard(trade.id, False, False), parse_mode="Markdown")
        except Exception:
            pass

@router.callback_query(F.data.startswith("trade_decline_"))
async def trade_decline(callback: CallbackQuery, bot: Bot):
    trade_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        trade = await session.scalar(select(TradeSession).where(TradeSession.id == trade_id))
        if not trade or trade.status != TradeStatusEnum.active:
            await callback.message.edit_text("❌ Торговля уже завершена или отменена.")
            return
            
        trade.status = TradeStatusEnum.cancelled
        await session.commit()
        await callback.message.edit_text("❌ Вы отклонили предложение.")
        
        sender = await session.scalar(select(Country).where(Country.id == trade.sender_country_id))
        try:
            await bot.send_message(sender.owner_id, "❌ Ваше торговое предложение было отклонено.")
        except:
            pass

@router.callback_query(F.data.startswith("trade_accept_"))
async def trade_accept(callback: CallbackQuery, bot: Bot):
    trade_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        trade = await session.scalar(select(TradeSession).where(TradeSession.id == trade_id))
        if not trade or trade.status != TradeStatusEnum.active:
            await callback.message.edit_text("❌ Торговля уже завершена или отменена.")
            return
            
        sender = await session.scalar(select(Country).where(Country.id == trade.sender_country_id))
        receiver = await session.scalar(select(Country).where(Country.id == trade.receiver_country_id))
        
        # Verify sender items
        s_money = trade.sender_slots.get('money', 0)
        if sender.treasury < s_money:
            await callback.answer("У отправителя уже нет этих средств.", show_alert=True)
            return
        for item_id_str, amount in trade.sender_slots.get('items', {}).items():
            cs = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == sender.id, CountryStockpile.item_id == int(item_id_str)))
            if not cs or cs.amount < amount:
                await callback.answer("У отправителя уже нет нужного количества техники.", show_alert=True)
                return
                
        # Verify receiver items
        r_money = trade.receiver_slots.get('money', 0)
        if receiver.treasury < r_money:
            await callback.answer("У вас недостаточно средств!", show_alert=True)
            return
        for item_id_str, amount in trade.receiver_slots.get('items', {}).items():
            cs = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == receiver.id, CountryStockpile.item_id == int(item_id_str)))
            if not cs or cs.amount < amount:
                await callback.answer("У вас нет нужного количества техники!", show_alert=True)
                return
                
        # Do the exchange
        sender.treasury -= s_money
        receiver.treasury += s_money
        
        receiver.treasury -= r_money
        sender.treasury += r_money
        
        # Transfer from sender to receiver
        for item_id_str, amount in trade.sender_slots.get('items', {}).items():
            item_id = int(item_id_str)
            cs_s = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == sender.id, CountryStockpile.item_id == item_id))
            cs_s.amount -= amount
            
            cs_r = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == receiver.id, CountryStockpile.item_id == item_id))
            if not cs_r:
                cs_r = CountryStockpile(country_id=receiver.id, item_id=item_id, amount=amount)
                session.add(cs_r)
            else:
                cs_r.amount += amount
                
        # Transfer from receiver to sender
        for item_id_str, amount in trade.receiver_slots.get('items', {}).items():
            item_id = int(item_id_str)
            cs_r = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == receiver.id, CountryStockpile.item_id == item_id))
            cs_r.amount -= amount
            
            cs_s = await session.scalar(select(CountryStockpile).where(CountryStockpile.country_id == sender.id, CountryStockpile.item_id == item_id))
            if not cs_s:
                cs_s = CountryStockpile(country_id=sender.id, item_id=item_id, amount=amount)
                session.add(cs_s)
            else:
                cs_s.amount += amount
                
        trade.status = TradeStatusEnum.completed
        await session.commit()
        
        await callback.message.edit_text("✅ Сделка успешно завершена!")
        try:
            await bot.send_message(sender.owner_id, f"✅ Сделка с {receiver.name} завершена!")
        except:
            pass
