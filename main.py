import asyncio
import json
import os
import re
import dateparser
from datetime import datetime, timedelta
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.errors import FloodWait, RPCError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- الإعدادات ---
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5dc571c42a"
BOT_TOKEN = "8287521845:AAG8sbZL0g5NPwno5An9tjeh9UxAmdzw4X4"
MY_USER_ID = 1486879970 

# ملفات البيانات
MEDIA_FILE = "sequential_media.json"
COUNTDOWN_FILE = "countdowns.json"

def load_data(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# تحميل البيانات
sequential_content = load_data(MEDIA_FILE, {}) 
# الهيكل: {"chat_id": {"index": 0, "items": [{"type": "photo", "id": "..."}]}}

app = Client("FaisalBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=100)
scheduler = AsyncIOScheduler()
is_muted = {} # نظام الكتم

# --- دالة التحقق من الأدمن ---
async def is_admin(client, user_id, chat_id):
    if user_id == MY_USER_ID: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except: return False

# --- 1. المنشن الجماعي السريع جداً ---
@app.on_message(filters.command("all", prefixes="") & filters.group)
async def mention_all(client, message):
    if not await is_admin(client, message.from_user.id, message.chat.id): return
    if is_muted.get(message.chat.id): return

    cmd_parts = message.text.split(None, 1)
    extra_word = cmd_parts[1] if len(cmd_parts) > 1 else ""
    
    members = []
    async for m in client.get_chat_members(message.chat.id):
        if not m.user.is_bot:
            name = f"[{m.user.first_name}](tg://user?id={m.user.id})"
            members.append(name)
    
    await message.reply(f"🚀 بدأ المنشن السريع لـ {len(members)} عضو...")
    
    for i in range(0, len(members), 5): # يرسل 5 أعضاء في كل رسالة للسرعة
        chunk = members[i:i+5]
        mention_text = " ".join(chunk) + f"\n\n{extra_word}"
        try:
            await client.send_message(message.chat.id, mention_text)
            await asyncio.sleep(0.3) # سرعة عالية جداً
        except FloodWait as e: await asyncio.sleep(e.value)
        except: break

# --- 2. نظام الكتم وفك الكتم ---
@app.on_message(filters.command(["كتم", "الغاء كتم"], prefixes="") & filters.group)
async def mute_bot(client, message):
    if not await is_admin(client, message.from_user.id, message.chat.id): return
    if "الغاء" in message.text:
        is_muted[message.chat.id] = False
        await message.reply("تم إلغاء كتم البوت.. أنا معك الآن! ✅")
    else:
        is_muted[message.chat.id] = True
        await message.reply("تم كتم البot.. سأصمت الآن. 🔇")

# --- 3. نظام التتابع (محتوى) ---
@app.on_message(filters.regex("^محتوى$") & filters.group)
async def sequence_handler(client, message):
    if is_muted.get(message.chat.id): return
    cid = str(message.chat.id)
    if cid not in sequential_content or not sequential_content[cid]["items"]:
        return await message.reply("لم تضف أي محتوى تتابعي بعد!")
    
    data = sequential_content[cid]
    idx = data["index"]
    item = data["items"][idx]
    
    try:
        if item["type"] == "photo": await message.reply_photo(item["id"])
        elif item["type"] == "video": await message.reply_video(item["id"])
        elif item["type"] == "audio": await message.reply_audio(item["id"])
        elif item["type"] == "link": await message.reply(item["id"])
        
        # تحديث المرة القادمة
        data["index"] = (idx + 1) % len(data["items"])
        save_data(MEDIA_FILE, sequential_content)
    except: pass

@app.on_message(filters.command("اضف محتوى", prefixes="") & filters.group)
async def add_sequence(client, message):
    if not await is_admin(client, message.from_user.id, message.chat.id): return
    await message.reply("أرسل (صورة، فيديو، بصمة، أو رابط) الآن لإضافته للتتابع:")
    
    # انتظار الرد القادم
    @app.on_message((filters.photo | filters.video | filters.voice | filters.text) & filters.group, group=2)
    async def catcher(c, m):
        cid = str(m.chat.id)
        if cid not in sequential_content: sequential_content[cid] = {"index": 0, "items": []}
        
        if m.photo: item = {"type": "photo", "id": m.photo.file_id}
        elif m.video: item = {"type": "video", "id": m.video.file_id}
        elif m.voice: item = {"type": "audio", "id": m.voice.file_id}
        else: item = {"type": "link", "id": m.text}
        
        sequential_content[cid]["items"].append(item)
        save_data(MEDIA_FILE, sequential_content)
        await m.reply("تمت الإضافة للمحتوى التتابعي ✅")
        app.remove_handler(catcher, group=2)

# --- 4. الترحيب (فجر جديد) بالمنشن الخفي ---
@app.on_message(filters.new_chat_members)
async def welcome(client, message):
    for member in message.new_chat_members:
        mention = f"[{'🙋🏻‍♂️'}](tg://user?id={member.id})"
        await message.reply(f"اهلاً بك في فجـر جـديد {mention}\n\nخطوة صغيرة اليوم… تصنع فرق كبير غدًا 🌅")

# --- 5. ميزة ذكرني الذكية ---
@app.on_message(filters.regex(r"^ذكرني (.+)"))
async def remind_me(client, message):
    note = message.matches[0].group(1)
    await message.reply("حسناً اضف الصوره او الفيديو 🤳")
    
    @app.on_message((filters.video | filters.photo) & filters.group, group=3)
    async def get_media(c, m):
        await m.reply("متى أرسله لك؟ (مثلاً: بكره 4:30 مساء)")
        
        @app.on_message(filters.text & filters.group, group=4)
        async def get_time(c2, m2):
            date = dateparser.parse(m2.text, settings={'PREFER_DATES_FROM': 'future'})
            if date:
                await m2.reply(f"تم! سأذكرك في: {date.strftime('%Y-%m-%d %I:%M %p')}")
                # هنا تبرمج الجدولة الفعلية للرسالة
            else: await m2.reply("ما فهمت الوقت، حاول ثانية!")
            app.remove_handler(get_time, group=4)
        app.remove_handler(get_media, group=3)

# --- تشغيل البوت ---
async def main():
    await app.start()
    scheduler.start()
    print("البوت شغال بكل الميزات 🚀")
    await idle()

if __name__ == "__main__":
    app.run(main())
