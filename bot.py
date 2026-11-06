"""Crypto price alert bot: current prices on request and alerts when a coin crosses a price or moves by a percent.

    python bot.py
"""
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import aiohttp  # noqa: E402
from aiogram import Bot, Dispatcher, F, Router  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.filters import Command, CommandObject, CommandStart  # noqa: E402
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message  # noqa: E402

import db  # noqa: E402
from alerts import ParseError, coin_id, describe, fired, fmt_price, parse_rule, ticker  # noqa: E402
from prices import PriceError, Prices  # noqa: E402

log = logging.getLogger("alerts")
router = Router()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHECK_SECONDS = int(os.getenv("CHECK_SECONDS", "60"))
MAX_ALERTS = int(os.getenv("MAX_ALERTS_PER_USER", "20"))
prices: Prices | None = None

HELP = (
    "<b>Цены</b>\n/price sol ton btc — текущая цена и изменение за 24 ч\n\n"
    "<b>Алерты</b>\n/alert sol > 200 — цена поднимется до $200\n/alert ton < 2.5 — опустится до $2.5\n"
    "/alert btc +5% — вырастет на 5% от текущей\n/alert eth -10% — упадёт на 10%\n\n"
    "/alerts — мои алерты и удаление\n\n"
    "Монеты: тикеры BTC, ETH, SOL, TON, BNB, XRP и другие, или любой id с CoinGecko. Цены: CoinGecko."
)


@router.message(CommandStart())
@router.message(Command("help"))
async def start(m: Message) -> None:
    await m.answer("Привет! Я слежу за ценами криптовалют и пишу, когда срабатывает ваше условие.\n\n" + HELP)


@router.message(Command("price"))
async def price(m: Message, command: CommandObject) -> None:
    ids = [coin_id(w) for w in (command.args or "btc eth sol ton").replace(",", " ").split()][:10]
    try:
        data = await prices.get(ids)
    except (PriceError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        await m.answer(f"Не удалось получить цены: {e}")
        return
    lines = []
    for cid in ids:
        d = data.get(cid)
        if not d:
            lines.append(f"{cid}: не нашёл такую монету")
            continue
        ch = d.get("usd_24h_change") or 0
        lines.append(f"<b>{ticker(cid)}</b> ${fmt_price(d['usd'])}  {'🟢' if ch >= 0 else '🔴'} {ch:+.2f}% за 24 ч")
    await m.answer("\n".join(lines))


@router.message(Command("alert"))
async def add_alert(m: Message, command: CommandObject) -> None:
    try:
        rule = parse_rule(command.args or "")
    except ParseError as e:
        await m.answer(f"{e}\n\nПримеры: /alert sol > 200, /alert btc +5%")
        return
    if len(await db.active(m.from_user.id)) >= MAX_ALERTS:
        await m.answer(f"У вас уже {MAX_ALERTS} алертов. Удалите ненужные в /alerts.")
        return
    try:
        d = (await prices.get([rule.coin])).get(rule.coin)
    except (PriceError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        await m.answer(f"Не удалось проверить цену: {e}")
        return
    if not d:
        await m.answer(f"Не нашёл монету «{rule.coin}». Используйте тикер (sol, ton) или id с coingecko.com.")
        return
    now = d["usd"]
    if fired(rule.kind, rule.value, now, now):
        await m.answer(f"Условие уже выполнено: {ticker(rule.coin)} сейчас ${fmt_price(now)}.")
        return
    aid = await db.add(m.from_user.id, rule.coin, rule.kind, rule.value, now)
    await m.answer(f"✅ Алерт #{aid}: {describe(rule.kind, rule.value, rule.coin, now)}\n"
                   f"Сейчас ${fmt_price(now)}. Проверяю каждые {CHECK_SECONDS} с.")


@router.message(Command("alerts"))
async def list_alerts(m: Message) -> None:
    rows = await db.active(m.from_user.id)
    if not rows:
        await m.answer("Активных алертов нет. Добавьте: /alert sol > 200")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 #{r['id']} {describe(r['kind'], r['value'], r['coin'], r['base'])}",
                              callback_data=f"del:{r['id']}")] for r in rows])
    await m.answer(f"Ваши алерты ({len(rows)}). Нажмите, чтобы удалить:", reply_markup=kb)


@router.callback_query(F.data.startswith("del:"))
async def delete_alert(c: CallbackQuery) -> None:
    ok = await db.delete(c.from_user.id, int(c.data.split(":", 1)[1]))
    await c.answer("Удалено" if ok else "Уже удалено или сработало")
    rows = await db.active(c.from_user.id)
    if rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 #{r['id']} {describe(r['kind'], r['value'], r['coin'], r['base'])}",
                                  callback_data=f"del:{r['id']}")] for r in rows])
        await c.message.edit_text(f"Ваши алерты ({len(rows)}). Нажмите, чтобы удалить:", reply_markup=kb)
    else:
        await c.message.edit_text("Активных алертов нет.")


async def check_loop(bot: Bot) -> None:
    """One batched price request per cycle for all coins with active alerts."""
    while True:
        await asyncio.sleep(CHECK_SECONDS)
        rows = await db.active()
        if not rows:
            continue
        try:
            data = await prices.get(sorted({r["coin"] for r in rows}))
        except (PriceError, aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning("prices: %s", e)
            continue
        for r in rows:
            d = data.get(r["coin"])
            if not d or not fired(r["kind"], r["value"], r["base"], d["usd"]):
                continue
            await db.mark_fired(r["id"])
            try:
                await bot.send_message(r["user_id"], f"🔔 Сработал алерт #{r['id']}: "
                                                     f"{describe(r['kind'], r['value'], r['coin'], r['base'])}\n"
                                                     f"{ticker(r['coin'])} сейчас ${fmt_price(d['usd'])}")
            except Exception as e:  # noqa: BLE001 - user blocked the bot
                log.warning("send %s: %s", r["user_id"], e)


async def main() -> None:
    global prices
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env (copy .env.example)")
    await db.init()
    async with aiohttp.ClientSession() as http:
        prices = Prices(http)
        bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(router)
        asyncio.create_task(check_loop(bot))
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
