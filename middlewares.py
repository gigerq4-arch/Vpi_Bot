from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from database import async_session, Country
import logging

class ApprovalMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # We handle Message and CallbackQuery
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
            # Allow basic commands without approval check
            if text.startswith(("/start", "/admin", "/approve", "/reject", "/exp_approve", "/exp_reject")):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            cb_data = event.data or ""
            # Allow registration and admin moderation buttons
            if cb_data == "register_country" or cb_data.startswith("approve_") or cb_data.startswith("reject_") or cb_data.startswith("exp_"):
                return await handler(event, data)
        else:
            return await handler(event, data)

        # Check DB for approval status
        async with async_session() as session:
            country = await session.scalar(select(Country).where(Country.owner_id == user_id))
            if country and not getattr(country, 'is_approved', True):
                if isinstance(event, Message):
                    await event.answer("⏳ Ваша анкета находится на рассмотрении. Пожалуйста, дождитесь решения администратора.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⏳ Ваша анкета на модерации.", show_alert=True)
                return

        return await handler(event, data)
