import asyncio
import json
import logging
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any
import discord
import httpx
from discord.errors import LoginFailure
from discord.ext import commands
from app.config import get_settings
from app.extractor import detect_mime_type, get_extractor
from app.logging_config import configure_logging
from app.schemas import ExtractedInvoiceData

logger = logging.getLogger(__name__)

INVOICE_MEMORY: dict[int, ExtractedInvoiceData] = {}

def decimal_json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")

def invoice_to_json(data: ExtractedInvoiceData) -> str:
    return json.dumps(
        data.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        default=decimal_json_default,
    )

def format_money(value: Any, currency: str | None = None) -> str:
    if value is None:
        return "Not found"
    return f"{currency} {value}" if currency else str(value)

def format_invoice_summary(data: ExtractedInvoiceData) -> str:
    item_lines = []
    for item in data.items[:5]:
        description = item.description or "Unnamed item"
        amount = format_money(item.amount, data.currency)
        item_lines.append(f"- {description}: {amount}")

    items_text = "\n".join(item_lines) if item_lines else "No line items found."
    if len(data.items) > 5:
        items_text += f"\n- ...and {len(data.items) - 5} more item(s)"

    return (
        "**Invoice extracted successfully**\n\n"
        f"**Invoice No:** {data.invoice_number or 'Not found'}\n"
        f"**Date:** {data.invoice_date or 'Not found'}\n"
        f"**Seller:** {data.seller.name or 'Not found'}\n"
        f"**Buyer:** {data.buyer.name or 'Not found'}\n"
        f"**Subtotal:** {format_money(data.subtotal, data.currency)}\n"
        f"**VAT:** {format_money(data.vat_amount, data.currency)}\n"
        f"**Total:** {format_money(data.total_amount, data.currency)}\n\n"
        f"**Items**\n{items_text}"
    )


def build_invoice_embed(data: ExtractedInvoiceData) -> discord.Embed:
    embed = discord.Embed(
        title="Invoice extracted successfully",
        color=discord.Color.green(),
    )
    embed.add_field(name="Invoice No", value=data.invoice_number or "Not found", inline=True)
    embed.add_field(name="Date", value=str(data.invoice_date or "Not found"), inline=True)
    embed.add_field(name="Total", value=format_money(data.total_amount, data.currency), inline=True)
    embed.add_field(name="Seller", value=data.seller.name or "Not found", inline=True)
    embed.add_field(name="Buyer", value=data.buyer.name or "Not found", inline=True)
    embed.add_field(name="VAT", value=format_money(data.vat_amount, data.currency), inline=True)
    embed.add_field(name="Subtotal", value=format_money(data.subtotal, data.currency), inline=True)
    embed.add_field(name="Discount", value=format_money(data.discount, data.currency), inline=True)

    item_lines = []
    for item in data.items[:5]:
        description = item.description or "Unnamed item"
        amount = format_money(item.amount, data.currency)
        item_lines.append(f"- {description}: {amount}")
    if len(data.items) > 5:
        item_lines.append(f"- ...and {len(data.items) - 5} more item(s)")

    embed.add_field(
        name="Items",
        value="\n".join(item_lines)[:1024] if item_lines else "No line items found.",
        inline=False,
    )
    if data.remarks:
        embed.set_footer(text=data.remarks[:2048])
    return embed


async def ask_gemini_about_invoice(question: str, invoice: ExtractedInvoiceData) -> str:
    settings = get_settings()
    if not settings.gemini_api_key:
        return "Gemini is not configured. Add `GEMINI_API_KEY` in `backend/.env` first."

    prompt = (
        "You are an invoice assistant inside a Discord bot. "
        "Answer the user's question using only the invoice JSON below. "
        "If the answer is missing or uncertain, say that it was not found in the invoice. "
        "Keep the answer concise.\n\n"
        f"Invoice JSON:\n{invoice_to_json(invoice)}\n\n"
        f"Question: {question}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    headers = {"x-goog-api-key": settings.gemini_api_key}

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.is_error:
            detail = response.text[:300].replace("\n", " ")
            logger.error("Gemini invoice Q&A failed status=%s detail=%s", response.status_code, detail)
            return f"Gemini could not answer right now. Status: {response.status_code}"

    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


async def save_attachment_temporarily(attachment: discord.Attachment) -> Path:
    suffix = Path(attachment.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
    await attachment.save(temp_path)
    return temp_path


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info("Discord invoice bot logged in as %s", bot.user)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        await bot.process_commands(message)
        if message.content.startswith(bot.command_prefix):
            return

        invoice_data = INVOICE_MEMORY.get(message.channel.id)
        if not invoice_data:
            return

        async with message.channel.typing():
            try:
                answer = await ask_gemini_about_invoice(message.content, invoice_data)
                await message.reply(answer[:get_settings().discord_max_reply_chars])
            except Exception:
                logger.exception("Discord natural-language invoice chat failed")
                await message.reply("Sorry, I could not answer that invoice question.")

    @bot.command(name="ping")
    async def ping(ctx: commands.Context) -> None:
        await ctx.reply("pong")

    @bot.command(name="invoice")
    async def invoice(ctx: commands.Context) -> None:
        if not ctx.message.attachments:
            await ctx.reply("Attach an invoice image or PDF with `!invoice`.")
            return

        settings = get_settings()
        attachment = ctx.message.attachments[0]
        if attachment.size > settings.max_upload_bytes:
            await ctx.reply(f"That file is too large. Maximum size is {settings.max_upload_bytes} bytes.")
            return

        mime_type = detect_mime_type(attachment.filename, attachment.filename)
        if mime_type not in settings.allowed_content_types:
            allowed = ", ".join(sorted(settings.allowed_content_types.values()))
            await ctx.reply(f"Unsupported file type. Please upload one of: {allowed}")
            return

        status_message = await ctx.reply("Extracting invoice with Gemini...")
        temp_path: Path | None = None
        try:
            temp_path = await save_attachment_temporarily(attachment)
            extractor = get_extractor()
            extracted = await extractor.extract(str(temp_path), attachment.filename)
            INVOICE_MEMORY[ctx.channel.id] = extracted
            await status_message.edit(content=None, embed=build_invoice_embed(extracted))
        except Exception:
            logger.exception("Discord invoice extraction failed file_name=%s", attachment.filename)
            await status_message.edit(content="Sorry, invoice extraction failed. Check backend logs for details.")
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    @bot.command(name="ask")
    async def ask(ctx: commands.Context, *, question: str | None = None) -> None:
        if not question:
            await ctx.reply("Ask a question like `!ask what is the total amount?`")
            return

        invoice_data = INVOICE_MEMORY.get(ctx.channel.id)
        if not invoice_data:
            await ctx.reply("Upload an invoice first with `!invoice`, then ask a question.")
            return

        status_message = await ctx.reply("Thinking...")
        try:
            answer = await ask_gemini_about_invoice(question, invoice_data)
            await status_message.edit(content=answer[:get_settings().discord_max_reply_chars])
        except Exception:
            logger.exception("Discord invoice Q&A failed")
            await status_message.edit(content="Sorry, I could not answer that invoice question.")

    @bot.command(name="invoice_json")
    async def invoice_json(ctx: commands.Context) -> None:
        invoice_data = INVOICE_MEMORY.get(ctx.channel.id)
        if not invoice_data:
            await ctx.reply("No invoice is stored for this channel yet. Use `!invoice` first.")
            return
        await ctx.reply(f"```json\n{invoice_to_json(invoice_data)[:1800]}\n```")

    @bot.command(name="clear_invoice")
    async def clear_invoice(ctx: commands.Context) -> None:
        removed = INVOICE_MEMORY.pop(ctx.channel.id, None)
        if removed:
            await ctx.reply("Cleared the stored invoice for this channel.")
            return
        await ctx.reply("There is no stored invoice for this channel.")

    @bot.command(name="help_invoice")
    async def help_invoice(ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="Invoice Bot Commands",
            description="Upload an invoice, extract key fields, and ask Gemini follow-up questions.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="!ping", value="Check whether the bot is online.", inline=False)
        embed.add_field(
            name="!invoice",
            value="Upload an invoice image or PDF with this command to extract invoice data.",
            inline=False,
        )
        embed.add_field(
            name="!ask <question>",
            value="Ask about the last invoice uploaded in this channel.",
            inline=False,
        )
        embed.add_field(name="!invoice_json", value="Show the extracted invoice JSON.", inline=False)
        embed.add_field(name="!clear_invoice", value="Forget the stored invoice for this channel.", inline=False)
        await ctx.reply(embed=embed)

    return bot

async def main() -> None:
    configure_logging()
    settings = get_settings()
    discord_bot_token = settings.discord_bot_token.strip() if settings.discord_bot_token else None
    if not discord_bot_token or discord_bot_token == "your_discord_bot_token":
        raise RuntimeError("DISCORD_BOT_TOKEN is missing. Add it to backend/.env.")

    bot = build_bot()
    try:
        await bot.start(discord_bot_token)
    except LoginFailure as exc:
        raise RuntimeError(
            "Discord rejected DISCORD_BOT_TOKEN. Copy the Bot token from the Discord Developer Portal "
            "Bot page, not the client secret or public key. If needed, reset the token and update backend/.env."
        ) from exc
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
