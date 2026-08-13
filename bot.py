import os
import json
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATA_FILE = "bot_data.json"
CONFIG_FILE = "config.json"

# =========================================================================
# 📌 BACA PAIRING GRUP DARI CONFIG.JSON
# =========================================================================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                return cfg.get("GROUP_PAIRS", {})
        except Exception as e:
            logger.error(f"Gagal membaca {CONFIG_FILE}: {e}")
    return {}

GROUP_PAIRS = load_config()

# 📌 DAFTAR PEMETAAN USERNAME -> NAME TAG
USER_NAME_TAGS = {
    "@lubu_hiat": "LUBU PAKAM",
    "@zkyy07": "ADS",
    "@max77kix": "MAX",
    "@tiliqua_gigas": "TILIQUA_AG",
}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"known_groups": {}, "messages": {}}
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            data.setdefault("known_groups", {})
            data.setdefault("messages", {})
            return data
    except Exception:
        return {"known_groups": {}, "messages": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Gagal simpan DB: {e}")

def silent_register_group(chat):
    if chat.type in ['group', 'supergroup']:
        data = load_data()
        data["known_groups"][str(chat.id)] = chat.title or f"Grup {chat.id}"
        save_data(data)

def clean_mentions_from_message(message):
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []

    if not text:
        return ""

    mention_entities = [
        e for e in entities if e.type in ["mention", "text_mention"]
    ]
    mention_entities.sort(key=lambda x: x.offset, reverse=True)

    text_list = list(text)
    for ent in mention_entities:
        start = ent.offset
        end = ent.offset + ent.length
        del text_list[start:end]

    cleaned_text = "".join(text_list)
    cleaned_text = re.sub(r'@[^\s]+', '', cleaned_text)
    cleaned_text = re.sub(r' +', ' ', cleaned_text).strip()

    return cleaned_text

# Perintah untuk mengecek ID Grup
async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"📌 ID Grup ini adalah: `{chat.id}`\n\nJudul: {chat.title}", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or (update.message.text and update.message.text.startswith('/')):
        return

    chat = update.effective_chat
    silent_register_group(chat)

    chat_id_str = str(chat.id)
    message_id = update.message.message_id
    user = update.effective_user
    chat_title = chat.title or "Grup"

    data = load_data()
    # Muat konfigurasi terbaru tiap kali ada pesan
    pairs = load_config()

    target_chat_id = None
    reply_to_target_msg_id = None

    # 1. Cek Balasan / Reply
    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        target_chat_id = data["messages"].get(f"origin_chat_{chat_id_str}_{replied_msg_id}")
        reply_to_target_msg_id = data["messages"].get(f"map_{chat_id_str}_{replied_msg_id}")

    # 2. Cek Pasangan dari Config
    if not target_chat_id:
        if chat_id_str in pairs:
            target_chat_id = pairs[chat_id_str]
        else:
            for staff_id, vendor_id in pairs.items():
                if vendor_id == chat_id_str:
                    target_chat_id = staff_id
                    break

    # Jika grup tidak dipasangkan di config.json, bot tidak akan merespons
    if not target_chat_id:
        return

    try:
        is_from_staff = "STAFF" in chat_title.upper()
        sender_name = user.full_name or user.first_name or "Pengirim"
        username_key = f"@{user.username.lower()}" if user.username else ""
        name_tag = USER_NAME_TAGS.get(username_key, "-")

        header_block = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Pengirim : {sender_name}\n"
            f"🏷 Name Tag  : {name_tag}\n"
            f"📍 Asal Grup : {chat_title}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not is_from_staff:
            clean_text = clean_mentions_from_message(update.message)
            full_text = f"{header_block}{clean_text}"

            if update.message.text:
                sent_msg = await context.bot.send_message(
                    chat_id=int(target_chat_id),
                    text=full_text,
                    reply_to_message_id=reply_to_target_msg_id
                )
            elif update.message.photo:
                photo_file_id = update.message.photo[-1].file_id
                sent_msg = await context.bot.send_photo(
                    chat_id=int(target_chat_id),
                    photo=photo_file_id,
                    caption=full_text,
                    reply_to_message_id=reply_to_target_msg_id
                )
            elif update.message.document:
                doc_file_id = update.message.document.file_id
                sent_msg = await context.bot.send_document(
                    chat_id=int(target_chat_id),
                    document=doc_file_id,
                    caption=full_text,
                    reply_to_message_id=reply_to_target_msg_id
                )
            else:
                sent_msg = await context.bot.copy_message(
                    chat_id=int(target_chat_id),
                    from_chat_id=int(chat_id_str),
                    message_id=message_id,
                    reply_to_message_id=reply_to_target_msg_id
                )
        else:
            sent_msg = await context.bot.copy_message(
                chat_id=int(target_chat_id),
                from_chat_id=int(chat_id_str),
                message_id=message_id,
                reply_to_message_id=reply_to_target_msg_id
            )

        data["messages"][f"origin_chat_{target_chat_id}_{sent_msg.message_id}"] = chat_id_str
        data["messages"][f"map_{target_chat_id}_{sent_msg.message_id}"] = message_id
        data["messages"][f"map_{chat_id_str}_{message_id}"] = sent_msg.message_id
        save_data(data)

    except Exception as e:
        logger.error(f"Gagal meneruskan pesan: {e}")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN belum diisi!")
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("id", get_id_command))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    logger.info("Bot Berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
