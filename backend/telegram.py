"""Отправка заказа в Telegram и обработка нажатий на inline-кнопки.

Как это работает
----------------
1. Уведомление уходит через MCP-сервер `tgbot-mcp` (инструмент
   `send_notification_with_buttons`) — как требует задача. Резерв: прямой
   вызов Bot API с тем же текстом и той же клавиатурой.
2. Telegram кладёт в inline-кнопку `callback_data` = текст кнопки
   (ограничение tgbot-mcp). Поэтому заказ определяется по `message_id`
   сообщения: он сохраняется в таблице `telegram_buttons` вместе с
   заказом и подписью кнопки.
3. Фоновый poller читает `getUpdates`, ловит `callback_query`, находит заказ
   по `message_id`, меняет статус заказа, пишет событие в `order_events`,
   закрывает «часики» через `answerCallbackQuery` и отвечает в чат.

Текстовые ответы менеджера тоже обрабатываются: если в сообщении есть
номер заказа, он попадает в событие заказа.
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

try:  # пакетный импорт
    from . import db, order_status, settings
except ImportError:  # запуск как top-level модуль (uvicorn main:app)
    import db  # type: ignore[no-redef]
    import order_status  # type: ignore[no-redef]
    import settings  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

BUTTON_ACCEPT = "✅ Принял"
BUTTON_CALLBACK = "📞 Перезвонил"
BUTTON_REJECT = "❌ Отказ"
BUTTONS = [BUTTON_ACCEPT, BUTTON_CALLBACK, BUTTON_REJECT]

# Кнопка -> (новый статус заказа, подпись события)
BUTTON_ACTIONS: dict[str, tuple[str, str]] = {
    BUTTON_ACCEPT: ("accepted", "Заказ принят менеджером"),
    BUTTON_CALLBACK: ("accepted", "Менеджер перезвонит клиенту"),
    BUTTON_REJECT: ("rejected", "Заказ отклонён менеджером"),
}

# Уведомления клиенту о статусе заказа. Ключ — статус, значение — текст.
# {order_number} подставляется при отправке.
CLIENT_STATUS_TEXTS: dict[str, str] = {
    "accepted": (
        "✅ Заказ {order_number} принят в работу!\n\n"
        "Мы уже начали его собирать. Сообщим, когда можно будет забрать."
    ),
    "in_progress": (
        "🔧 Заказ {order_number} — в работе.\n\n"
        "Собираем детали по вашему заказу."
    ),
    "ready": (
        "📦 Заказ {order_number} готов к выдаче!\n\n"
        "Ждём вас по адресу: {address}\n"
        "Режим работы: {hours}. Приятной покупки!"
    ),
    "completed": (
        "🎉 Заказ {order_number} выдан.\n\n"
        "Спасибо за покупку! Будем рады видеть вас снова."
    ),
    "rejected": (
        "❌ Заказ {order_number} отклонён.\n\n"
        "Если есть вопросы — позвоните нам: {phone}"
    ),
    "cancelled": (
        "Заказ {order_number} отменён.\n\n"
        "Если есть вопросы — позвоните нам: {phone}"
    ),
}

# Статусы, о которых клиенту сообщаем. «Новый» — это и так новость,
# о которой клиент знает: он сам только что оформил заказ.
CLIENT_NOTIFY_STATUSES = (
    "accepted",
    "in_progress",
    "ready",
    "completed",
    "rejected",
    "cancelled",
)

ORDER_NUMBER_RE = re.compile(r"A-\d{6}-\d{4}")
MESSAGE_ID_RE = re.compile(r"message_id=(\d+)")
_MARKDOWN_SPECIALS = re.compile(r"([_*`\[\]])")


def _escape(text: str) -> str:
    """Экранировать Markdown-спецсимволы Telegram (parse_mode=Markdown)."""
    return _MARKDOWN_SPECIALS.sub(r"\\\1", text)


def _mask_token(text: str) -> str:
    """Убрать токен бота из текста ошибки (Telegram-ошибки содержат полный URL)."""
    token = settings.TELEGRAM_BOT_TOKEN
    if token and token in text:
        text = text.replace(token, "***")
    return text


def _tool_call_error(result: Any) -> str | None:
    """Достать текст ошибки из CallToolResult.

    В mcp 2.x поле называется `is_error` (в 1.x — `isError`), поэтому
    проверяем оба варианта: иначе упавший вызов молча считается успешным.
    """
    is_error = getattr(result, "is_error", None)
    if is_error is None:
        is_error = getattr(result, "isError", None)
    if not is_error:
        return None

    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return _mask_token(
        "tgbot-mcp вернул ошибку: " + ("; ".join(parts) or "is_error=True")
    )


def _store_now() -> datetime:
    tz = timezone(timedelta(hours=settings.STORE_UTC_OFFSET_HOURS))
    return datetime.now(tz)


def is_night_order(moment: datetime) -> bool:
    """Ночной заказ — 22:00–08:00 по времени магазина."""
    hour = moment.hour
    start = settings.NIGHT_ORDER_START_HOUR
    end = settings.NIGHT_ORDER_END_HOUR
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def _telegram_api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


class TelegramNotifier:
    """Отправка уведомлений + poller нажатий на inline-кнопки."""

    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: Any = None
        self._lock = asyncio.Lock()
        self._disabled = not settings.TELEGRAM_USE_MCP
        self._poller: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # -- жизненный цикл ----------------------------------------------------

    async def start(self) -> None:
        if not self._disabled:
            try:
                await self._ensure_session()
                logger.info("Telegram MCP-сессия tgbot-mcp поднята")
            except Exception as exc:  # noqa: BLE001 — старт не должен ронять API
                logger.warning(
                    "MCP tgbot-mcp недоступен (%s), будет использован Bot API",
                    _mask_token(str(exc)),
                )
                self._disabled = True
        self._stop_event.clear()
        self._poller = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._poller is not None:
            self._poller.cancel()
            try:
                await self._poller
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.debug("Ошибка остановки poller", exc_info=True)
            self._poller = None
        await self.stop_session()

    async def stop_session(self) -> None:
        async with self._lock:
            if self._stack is not None:
                try:
                    await self._stack.aclose()
                except Exception:  # noqa: BLE001
                    logger.debug("Ошибка закрытия MCP-стека", exc_info=True)
            self._stack = None
            self._session = None

    async def _ensure_session(self) -> None:
        if self._session is not None:
            return
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=settings.TELEGRAM_MCP_COMMAND,
            args=[
                settings.TELEGRAM_MCP_PACKAGE,
                "--connect-timeout",
                str(settings.TELEGRAM_MCP_TIMEOUT_SECONDS),
            ],
            # Передаём токен и chat_id именно в окружение процесса —
            # ключи `--env KEY=VALUE` доезжают не во все версии fastmcp.
            env={
                "TELEGRAM_BOT_TOKEN": settings.TELEGRAM_BOT_TOKEN,
                "TELEGRAM_CHAT_ID": settings.TELEGRAM_CHAT_ID,
            },
        )
        stack = AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._stack = stack
        self._session = session

    # -- отправка -----------------------------------------------------------

    async def send_order_notification(
        self,
        *,
        order_id: int,
        order_number: str,
        customer_name: str,
        phone: str | None,
        telegram: str | None,
        car_info: str | None,
        pickup_label: str,
        address: str | None,
        items: list[tuple[str, int, float, bool, int]],
        total: float,
        comment: str | None,
        created_at: datetime,
        is_night: bool,
    ) -> tuple[bool, str]:
        """Отправить заказ. Возвращает (успех, канал доставки).

        `message_id` отправленного сообщения сохраняется в
        `telegram_buttons`, чтобы poller знал, какой заказ соответствует
        нажатой кнопке.
        """
        summary = f"Новый заказ {order_number} — {customer_name}"
        details = self._format_details(
            order_number=order_number,
            customer_name=customer_name,
            phone=phone,
            telegram=telegram,
            car_info=car_info,
            pickup_label=pickup_label,
            address=address,
            items=items,
            total=total,
            comment=comment,
            created_at=created_at,
            is_night=is_night,
        )

        if not self._disabled:
            try:
                async with self._lock:
                    await self._ensure_session()
                    result = await self._session.call_tool(
                        "send_notification_with_buttons",
                        {
                            "event": "question",
                            "summary": _escape(summary),
                            "details": details,
                            "buttons": BUTTONS,
                            "icon": "🛒",
                        },
                    )
                error = _tool_call_error(result)
                if error:
                    raise RuntimeError(error)
                message_id = self._extract_message_id(result)
                await self._remember_buttons(order_id, message_id)
                logger.info(
                    "Заказ %s отправлен через tgbot-mcp (message_id=%s)",
                    order_number,
                    message_id,
                )
                return True, "tgbot-mcp"
            except Exception as exc:  # noqa: BLE001 — уходим на резерв
                logger.warning(
                    "Отправка через MCP не удалась (%s), пробуем Bot API",
                    _mask_token(str(exc)),
                )
                await self.stop_session()

        return await self._send_via_bot_api(
            order_id=order_id, summary=summary, details=details
        )

    @staticmethod
    def _extract_message_id(result: Any) -> int | None:
        """Вытащить message_id из текста ответа tgbot-mcp."""
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if not text:
                continue
            match = MESSAGE_ID_RE.search(text)
            if match:
                return int(match.group(1))
        return None

    async def _remember_buttons(
        self, order_id: int, message_id: int | None
    ) -> None:
        """Привязать message_id к заказу и кнопкам."""
        if message_id is None:
            return
        try:
            await db.execute(
                "DELETE FROM telegram_buttons WHERE order_id = $1", order_id
            )
            for label in BUTTONS:
                await db.execute(
                    """
                    INSERT INTO telegram_buttons
                        (order_id, message_id, action, label)
                    VALUES ($1, $2, $3, $4)
                    """,
                    order_id,
                    message_id,
                    BUTTON_ACTIONS.get(label, ("accepted", label))[0],
                    label,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось сохранить привязку кнопок к заказу: %s", exc
            )

    @staticmethod
    def _format_details(
        *,
        order_number: str,
        customer_name: str,
        phone: str | None,
        telegram: str | None,
        car_info: str | None,
        pickup_label: str,
        address: str | None,
        items: list[tuple[str, int, float, bool, int]],
        total: float,
        comment: str | None,
        created_at: datetime,
        is_night: bool,
    ) -> str:
        lines = [f"Заказ: {_escape(order_number)}"]
        lines.append(f"Имя: {_escape(customer_name)}")
        contact = " — ".join(part for part in (phone, telegram) if part)
        if contact:
            lines.append(f"Контакты: {_escape(contact)}")
        if car_info:
            lines.append(f"Авто: {_escape(car_info)}")
        lines.append(f"Получение: {_escape(pickup_label)}")
        if address:
            lines.append(f"Адрес: {_escape(address)}")
        lines.append("")
        lines.append("Товары:")
        max_days = 0
        for name, qty, price, is_on_order, order_days in items:
            line = f"• {_escape(name)} × {qty} — {price:,.0f} ₽".replace(",", " ")
            if is_on_order:
                line += f"  ⏳ под заказ ({order_days} дн.)"
                max_days = max(max_days, order_days)
            lines.append(line)
        lines.append(f"Итого: {total:,.0f} ₽".replace(",", " "))
        if max_days:
            lines.append(f"⏳ Часть позиций под заказ — до {max_days} дн.")
        if comment:
            lines.append("")
            lines.append(f"Комментарий: {_escape(comment)}")
        stamp = created_at.strftime("%d.%m.%Y %H:%M")
        lines.append(f"Время: {stamp}")
        if is_night:
            night_window = (
                f"{settings.NIGHT_ORDER_START_HOUR:02d}:00–"
                f"{settings.NIGHT_ORDER_END_HOUR:02d}:00"
            )
            lines.append(
                f"🌙 Приоритетный заказ ({night_window} — магазин закрыт)"
            )
        return "\n".join(lines)

    async def _send_via_bot_api(
        self, *, order_id: int, summary: str, details: str
    ) -> tuple[bool, str]:
        keyboard = [
            [{"text": label, "callback_data": label[:64]}]
            for label in BUTTONS
        ]
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": f"🛒 *{_escape(summary)}*\n\n{details}",
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard},
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    _telegram_api("sendMessage"), json=payload
                )
                response.raise_for_status()
                data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "unknown Telegram error"))
            message_id = (data.get("result") or {}).get("message_id")
            await self._remember_buttons(order_id, message_id)
            return True, "telegram-bot-api"
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Отправка в Telegram не удалась: %s", _mask_token(str(exc))
            )
            return False, f"failed: {_mask_token(str(exc))}"

    # -- poller нажатий -----------------------------------------------------

    async def _poll_loop(self) -> None:
        """Читает getUpdates и обрабатывает нажатия на inline-кнопки."""
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return
        offset = 0
        logger.info("Telegram poller запущен")
        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                while not self._stop_event.is_set():
                    try:
                        response = await client.get(
                            _telegram_api("getUpdates"),
                            params={
                                "offset": offset,
                                "timeout": 20,
                                "allowed_updates": ["callback_query", "message"],
                            },
                        )
                        data = response.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Ошибка опроса Telegram: %s", _mask_token(str(exc))
                        )
                        await asyncio.sleep(5)
                        continue

                    if not data.get("ok"):
                        await asyncio.sleep(5)
                        continue

                    for update in data.get("result", []):
                        offset = max(offset, int(update.get("update_id", 0)) + 1)
                        try:
                            await self._handle_update(update)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Не удалось обработать апдейт Telegram: %s", exc
                            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram poller остановлен: %s", exc)

    async def _handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
        elif "message" in update:
            await self._handle_text(update["message"])

    async def _handle_callback(self, callback: dict) -> None:
        data = callback.get("data") or ""
        callback_id = callback.get("id")
        message = callback.get("message") or {}
        message_id = message.get("message_id")

        order = None
        if message_id is not None:
            order = await db.fetchrow(
                """
                SELECT o.id, o.order_number, o.status, o.customer_name,
                       o.telegram, o.telegram_chat_id, o.address, o.phone
                FROM telegram_buttons b
                JOIN orders o ON o.id = b.order_id
                WHERE b.message_id = $1 AND b.label = $2 AND b.used_at IS NULL
                ORDER BY b.id DESC
                LIMIT 1
                """,
                message_id,
                data,
            )

        if order is None:
            await self._answer_callback(callback_id, "Заказ не найден")
            return

        status, note = BUTTON_ACTIONS.get(
            data, ("accepted", f"Менеджер нажал «{data}»")
        )
        await order_status.apply_order_status(
            db,
            order["id"],
            status,
            note=note,
        )
        # Клиенту тоже сообщаем о смене статуса.
        await self.notify_client_status(
            order_number=order["order_number"],
            status=status,
            chat_id=order.get("telegram_chat_id"),
            telegram_username=order.get("telegram"),
            address=order.get("address"),
            phone=order.get("phone"),
        )
        await db.execute(
            "UPDATE telegram_buttons SET used_at = now() WHERE order_id = $1",
            order["id"],
        )
        await self._answer_callback(callback_id, "Готово")
        await self._send_text(
            f"Заказ {order['order_number']}: {note}. Статус — {status}."
        )
        logger.info(
            "Нажата кнопка «%s» по заказу %s", data, order["order_number"]
        )

    async def _handle_start(self, message: dict, text: str) -> None:
        """Клиент нажал «Старт» в боте.

        Если передан номер заказа (/start A-261021-0061) — запоминаем чат
        клиента и привязываем к заказу, чтобы присылать уведомления о
        статусе. Если номера нет — просто запоминаем чат: клиент мог
        указать свой Telegram в форме заказа, и мы найдём его по username.
        """
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        user = message.get("from") or {}
        username = (user.get("username") or "").strip().lstrip("@") or None

        match = ORDER_NUMBER_RE.search(text)
        order_number = match.group(0) if match else None

        await db.execute(
            """
            INSERT INTO telegram_chats (chat_id, username, order_number)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id) DO UPDATE
            SET username = COALESCE(EXCLUDED.username, telegram_chats.username),
                order_number = COALESCE(
                    EXCLUDED.order_number, telegram_chats.order_number
                ),
                updated_at = now()
            """,
            chat_id,
            username,
            order_number,
        )

        if order_number:
            await db.execute(
                """
                UPDATE orders
                SET telegram_chat_id = $1, updated_at = now()
                WHERE order_number = $2
                """,
                chat_id,
                order_number,
            )
            logger.info(
                "Клиент %s подписался на уведомления по заказу %s",
                username or chat_id,
                order_number,
            )
            await self._send_to_chat(
                chat_id,
                f"✅ Вы подписались на уведомления по заказу "
                f"{order_number}.\n\nСообщим, когда заказ будет готов.",
            )
            return

        await self._send_to_chat(
            chat_id,
            f"👋 Это бот магазина «{settings.STORE_NAME}».\n\n"
            "Чтобы получать уведомления о заказе, отправьте сюда его номер "
            "— например A-261021-0061.",
        )

    async def _send_to_chat(self, chat_id: int, text: str) -> None:
        """Отправить сообщение в конкретный чат (клиенту)."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    _telegram_api("sendMessage"),
                    json={"chat_id": chat_id, "text": text},
                )
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось отправить сообщение в чат %s: %s",
                chat_id,
                _mask_token(str(exc)),
            )

    async def _handle_text(self, message: dict) -> None:
        """Входящее сообщение: подписка клиента или комментарий менеджера."""
        text = (message.get("text") or "").strip()
        if not text:
            return

        # Подписка клиента: /start или /start A-261021-0061.
        if text.startswith("/start"):
            await self._handle_start(message, text)
            return

        match = ORDER_NUMBER_RE.search(text)
        if not match:
            return
        order_number = match.group(0)
        order = await db.fetchrow(
            "SELECT id, order_number FROM orders WHERE order_number = $1",
            order_number,
        )
        if order is None:
            return
        await db.execute(
            """
            INSERT INTO order_events (order_id, status, note, actor)
            VALUES ($1, (SELECT status FROM orders WHERE id = $1), $2, 'manager')
            """,
            order["id"],
            text,
        )
        await self._send_text(
            f"Сообщение по заказу {order_number} записано в комментарии менеджера."
        )

    async def _answer_callback(self, callback_id: str | None, text: str) -> None:
        if not callback_id:
            return
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    _telegram_api("answerCallbackQuery"),
                    json={"callback_query_id": callback_id, "text": text},
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("answerCallbackQuery не удался: %s", exc)

    async def notify_client_status(
        self,
        *,
        order_number: str,
        status: str,
        chat_id: int | None = None,
        telegram_username: str | None = None,
        address: str | None = None,
        phone: str | None = None,
    ) -> bool:
        """Сообщить клиенту о смене статуса его заказа.

        Бот может написать клиенту только если клиент сам начал диалог
        (Telegram не даёт писать тем, кто бота не активировал). Поэтому
        chat_id ищем: сперва в заказе, затем по username в telegram_chats.

        Возвращает True, если сообщение ушло.
        """
        if status not in CLIENT_NOTIFY_STATUSES:
            return False

        template = CLIENT_STATUS_TEXTS.get(status)
        if not template:
            return False

        target_chat = chat_id
        if target_chat is None and telegram_username:
            target_chat = await self._find_chat_by_username(telegram_username)
        if target_chat is None:
            logger.info(
                "Нет chat_id для клиента заказа %s — уведомление «%s» пропущено",
                order_number,
                status,
            )
            return False

        store_hours = f"{settings.STORE_OPEN_HOUR}:00–{settings.STORE_CLOSE_HOUR}:00"
        text = template.format(
            order_number=order_number,
            address=address or settings.STORE_ADDRESS,
            phone=phone or settings.STORE_PHONE,
            hours=store_hours,
        )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    _telegram_api("sendMessage"),
                    json={
                        "chat_id": target_chat,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                response.raise_for_status()
                data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "unknown Telegram error"))
            logger.info(
                "Клиенту заказа %s отправлено уведомление «%s»",
                order_number,
                status,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось уведомить клиента заказа %s: %s",
                order_number,
                _mask_token(str(exc)),
            )
            return False

    async def _find_chat_by_username(self, username: str) -> int | None:
        """Найти chat_id клиента по username, если он уже писал боту."""
        clean = (username or "").strip().lstrip("@")
        if not clean:
            return None
        try:
            row = await db.fetchrow(
                """
                SELECT chat_id FROM telegram_chats
                WHERE lower(username) = lower($1)
                LIMIT 1
                """,
                clean,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось найти chat клиента: %s", exc)
            return None
        return int(row["chat_id"]) if row else None

    async def _send_text(self, text: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    _telegram_api("sendMessage"),
                    json={
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": text,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Отправка ответа в Telegram не удалась: %s", exc)


notifier = TelegramNotifier()
