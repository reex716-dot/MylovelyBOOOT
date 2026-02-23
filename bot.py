import asyncio
import json
import os
import dateparser
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import ChatMemberStatus
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- الإعدادات (التوكن الجديد والبيانات) ---
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5dc571c42a"
BOT_TOKEN = "8514118433:AAEvB4nWdb6qkMUq8WsY-SWzgmQmxOmyMzQ"
MY_USER_ID = 1486879970 

# ملفات تخزين البيانات لضمان عدم ضياعها عند إعادة التشغيل
MEDIA_FILE = "sequential_media.json"

def load_data(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# تحميل بيانات المحتوى التتابعي
sequential_content = load_data(MEDIA_FILE, {}) 

app = Client("FaisalBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=100)
scheduler = AsyncIOScheduler()
is_muted = {} # نظام الكتم لكل شات على حدة

# --- دالة التحقق من رتبة الأدمن ---
async def is_admin(client, user_id, chat_id):
    if user_id == MY_USER_ID: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except: return False

# --- 1. المنشن الجماعي السريع (all) مع ميزة الكلمة الجانبية ---
@app.on_message(filters.regex(r"^all") & filters.group)
async def mention_all(client, message):
    if is_muted.get(message.chat.id): return
    if not await is_admin(client, message.from_user.id, message.chat.id): return

    # استخراج الكلمة التي بجانب all إن وجدت
    cmd_parts = message.text.split(None, 1)
    extra_word = cmd_parts[1] if len(cmd_parts) > 1 else ""
    
    members = []
    async for m in client.get_chat_members(message.chat.id):
        if not m.user.is_bot:
            members.append(f"[{m.user.first_name}](tg://user?id={m.user.id})")
    
    # تقسيم المنشن لمجموعات (5 أعضاء لكل رسالة) لضمان أقصى سرعة
    for i in range(0, len(members), 5):
        chunk = members[i:i+5]
        mention_text = " ".join(chunk) + (f"\n\n{extra_word}" if extra_word else "")
        try:
            await client.send_message(message.chat.id, mention_text)
            await asyncio.sleep(0.1) # سرعة خارقة
        except FloodWait as e: await asyncio.sleep(e.value)
        except: break

# --- 2. نظام الكتم وفك الكتم ---
@app.on_message(filters.regex("^(كتم|الغاء كتم)$") & filters.group)
async def mute_bot(client, message):
    if not await is_admin(client, message.from_user.id, message.chat.id): return
    if "الغاء" in message.text:
        is_muted[message.chat.id] = False
        await message.reply("تم إلغاء كتم البوت.. أبشر بعزك! ✅")
    else:
        is_muted[message.chat.id] = True
        await message.reply("تم كتم البوت.. سأصمت الآن 🔇")

# --- 3. نظام التتابع (إرسال المحتوى بالترتيب) ---
@app.on_message(filters.regex("^محتوى$") & filters.group)
async def sequence_handler(client, message):
    if is_muted.get(message.chat.id): return
    cid = str(message.chat.id)
    if cid not in sequential_content or not sequential_content[cid]["items"]:
        return await message.reply("أضف محتوى أولاً باستخدام: `اضف محتوى`")
    
    data = sequential_content[cid]
    idx = data["index"]
    item = data["items"][idx]
    
    try:
        if item["type"] == "photo": await message.reply_photo(item["id"])
        elif item["type"] == "video": await message.reply_video(item["id"])
        elif item["type"] == "audio": await message.reply_voice(item["id"])
        elif item["type"] == "link": await message.reply(item["id"])
        
        # تحديث المؤشر للمرة القادمة (أو العودة للبداية)
        data["index"] = (idx + 1) % len(data["items"])
        save_data(MEDIA_FILE, sequential_content)
    except: pass

@app.on_message(filters.command("اضف محتوى", prefixes="") & filters.group)
async def add_sequence(client, message):
    if not await is_admin(client, message.from_user.id, message.chat.id): return
    await message.reply("أرسل الآن (صورة، فيديو، بصمة، أو رابط) لإضافته للقائمة:")
    
    @app.on_message((filters.photo | filters.video | filters.voice | filters.text) & filters.group, group=2)
    async def catcher(c, m):
        if m.from_user.id != message.from_user.id: return
        cid = str(m.chat.id)
        if cid not in sequential_content: sequential_content[cid] = {"index": 0, "items": []}
        
        if m.photo: item = {"type": "photo", "id": m.photo.file_id}
        elif m.video: item = {"type": "video", "id": m.video.file_id}
        elif m.voice: item = {"type": "audio", "id": m.voice.file_id}
        else: item = {"type": "link", "id": m.text}
        
        sequential_content[cid]["items"].append(item)
        save_data(MEDIA_FILE, sequential_content)
        await m.reply(f"تمت الإضافة بنجاح! الترتيب الحالي: {len(sequential_content[cid]['items'])} ✅")
        app.remove_handler(catcher, group=2)

# --- 4. الترحيب (فجر جديد) بالمنشن الخفي 🙋🏻‍♂️ ---
@app.on_message(filters.new_chat_members)
async def welcome(client, message):
    for member in message.new_chat_members:
        mention = f"[{'🙋🏻‍♂️'}](tg://user?id={member.id})"
        await message.reply(f"اهلاً بك في فجـر جـديد {mention}\n\nخطوة صغيرة اليوم… تصنع فرق كبير غدًا 🌅")

# --- 5. ميزة ذكرني الذكية (وسائط + وقت) ---
@app.on_message(filters.regex(r"^ذكرني (.+)"))
async def remind_me(client, message):
    note = message.matches[0].group(1)
    await message.reply("حسناً أرسل الصورة أو الفيديو الآن 🤳")
    
    @app.on_message((filters.video | filters.photo) & filters.group, group=3)
    async def get_media(c, m):
        if m.from_user.id != message.from_user.id: return
        file_id = m.photo.file_id if m.photo else m.video.file_id
        is_video = bool(m.video)
        await m.reply("متى أرسله لك؟ (مثلاً: بكره 4:30 مساء)")
        
        @app.on_message(filters.text & filters.group, group=4)
        async def get_time(c2, m2):
            if m2.from_user.id != message.from_user.id: return
            date = dateparser.parse(m2.text, settings={'PREFER_DATES_FROM': 'future'})
            if date:
                await m2.reply(f"تم! سأذكرك بـ '{note}' في موعدك المحدد ⏳")
                # جدولة المهمة
                scheduler.add_job(
                    send_reminder, "date", run_date=date, 
                    args=[m2.chat.id, file_id, note, is_video]
                )
            else: await m2.reply("لم أفهم الوقت، حاول مجدداً بصيغة أوضح.")
            app.remove_handler(get_time, group=4)
        app.remove_handler(get_media, group=3)

async def send_reminder(chat_id, file_id, note, is_video):
    if is_video: await app.send_video(chat_id, file_id, caption=f"🔔 تذكير: {note}")
    else: await app.send_photo(chat_id, file_id, caption=f"🔔 تذكير: {note}")

# --- تشغيل البوت ---
async def main():
    await app.start()
    scheduler.start()
    print("البوت شغال بأقوى نسخة وبالتوكن الجديد 🚀")
    await idle()

if __name__ == "__main__":
    app.run(main())
