import json
import os
import qrcode
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 7581895473

USERS_FILE = "users.json"
HISTORY_FILE = "history.json"

# ================= FILE HELPERS =================

def load(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

users = load(USERS_FILE, {})
history = load(HISTORY_FILE, [])
current_test = {}

# ================= PDF GENERATOR =================

def generate_pdf(test):

    filename = f"natija_{test['code']}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)

    sorted_results = sorted(
        test["results"],
        key=lambda x: x["percent"],
        reverse=True
    )

    data = [["O'rin", "Ism Familiya", "Foiz", "To'g'ri javoblar"]]

    for i, r in enumerate(sorted_results, start=1):
        fullname = f"{r['surname']} {r['name']}"
        # Safe access to question_count
        q_count = test.get("question_count", "N/A")
        data.append([
            str(i),
            fullname,
            f"{r['percent']}%",
            f"{r['correct']}/{q_count}"
        ])

    table = Table(data, colWidths=[60, 260, 100, 100], rowHeights=35)

    style = [
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f4e79")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]

    for i, r in enumerate(sorted_results, start=1):
        percent = r["percent"]

        if percent >= 90:
            color = colors.green
        elif percent >= 70:
            color = colors.blue
        elif percent >= 50:
            color = colors.orange
        else:
            color = colors.red

        style.append(('TEXTCOLOR', (2,i), (2,i), color))

    table.setStyle(TableStyle(style))
    doc.build([table])
    return filename

# ================= CERTIFICATE =================

def generate_certificate(user, percent, tg_id, test_code):

    width, height = 1600, 1000
    img = Image.new("RGB", (width, height), "#eeeeee")
    draw = ImageDraw.Draw(img)

    # ===== TASHQI QALIN RAMKA =====
    draw.rectangle([10, 10, width-10, height-10],
                   outline="#2c3e50", width=40)

    # ===== ICHKI OLTIN RAMKA =====
    draw.rectangle([80, 80, width-80, height-80],
                   outline="#f1c40f", width=8)

    # ===== FONTLAR =====
    try:
        title_font = ImageFont.truetype("arial.ttf", 95) 
        subtitle_font = ImageFont.truetype("arial.ttf", 40) 
        name_font = ImageFont.truetype("arial.ttf", 85) 
        text_font = ImageFont.truetype("arial.ttf", 48) 
        small_font = ImageFont.truetype("arial.ttf", 36)

    except:
        title_font = subtitle_font = name_font = text_font = small_font = ImageFont.load_default()

    def center(text, y, font, color="#2c3e50"):
        w = draw.textlength(text, font=font)
        draw.text(((width - w) / 2, y), text, fill=color, font=font)

    # ===== SERTIFIKAT =====
    center("SERTIFIKAT", 170, title_font, "#2c3e50")

    # ===== IZOH MATN =====
    center(
        "Ushbu sertifikat matematika fanidan olingan bilim darajasini tasdiqlaydi",
        300, subtitle_font
    )

    # ===== ISM =====
    fullname = f"{user['surname'].upper()} {user['name'].upper()}"
    center(fullname, 430, name_font, "#e74c3c")

    # ===== ASOSIY MATN =====
    line1 = "Matematika fanidan o'tkazilgan test sinovida"
    line2 = f"ishtirok etib, {percent}% natija qayd etdi."

    center(line1, 610, text_font)
    center(line2, 680, text_font)

    # ===== SANA =====
    today = datetime.now().strftime("%d.%m.%Y")
    draw.text((140, 860),
              f"Sana: {today}",
              fill="#2c3e50",
              font=small_font)

    # ===== AKADEMIYA NOMI =====
    academy = "Matematika Prime Akademiyasi"
    w = draw.textlength(academy, font=small_font)
    draw.text((width - w - 140, 860),
              academy,
              fill="#2c3e50",
              font=small_font)

    filename = f"cert_{tg_id}_{test_code}.jpg"
    img.save(filename, quality=95)
    return filename

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🆕 Yangi test", callback_data="new")],
            [InlineKeyboardButton("📊 Natijalar", callback_data="results")]
        ]
        await update.message.reply_text(
            "👑 ADMIN PANEL",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    uid = str(update.effective_user.id)

    if uid not in users:
        context.user_data["step"] = "name"
        await update.message.reply_text("👤 Ismingiz:")
        return

    await update.message.reply_text("📝 Testga javob yuborish (kod)*(kalitlar)\nMasalan: 55*abcde")

# ================= TEXT HANDLER =================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = str(update.effective_user.id)
    text = update.message.text.strip().lower()

    # ===== ADMIN =====
    if update.effective_user.id == ADMIN_ID:

        step = context.user_data.get("admin_step")

        if step == "code":
            context.user_data["new_code"] = text
            context.user_data["admin_step"] = "key"
            await update.message.reply_text("Kalitni kiriting:")
            return

        if step == "key":
            global current_test
            current_test = {
                "code": context.user_data["new_code"],
                "key": text,
                "results": {}
            }
            context.user_data.clear()

            keyboard = [[InlineKeyboardButton("🛑 Testni tugatish", callback_data="stop")]]

            await update.message.reply_text(
                "🚀 Test boshlandi!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if step == "which":
            # Search from latest tests first
            for test in reversed(history):
                if test["code"] == text:
                    try:
                        file = generate_pdf(test)
                        await update.message.reply_document(open(file, "rb"))
                        os.remove(file)
                        context.user_data.clear()
                        return
                    except Exception as e:
                        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")
                        return

            await update.message.reply_text("❌ Test topilmadi")
            return

        return

    # ===== USER REGISTRATION =====
    if uid not in users:

        step = context.user_data.get("step")

        if step == "name":
            context.user_data["name"] = text
            context.user_data["step"] = "surname"
            await update.message.reply_text("Familiya:")
            return

        if step == "surname":
            users[uid] = {
                "name": context.user_data["name"],
                "surname": text
            }
            save(USERS_FILE, users)
            context.user_data.clear()
            await update.message.reply_text("🎉 Ro'yxatdan o'tdingiz !\n\n✅ Testda javob berish uchun /start tugmasini qayta bosing !")
            return

    # ===== TEST ANRSWE =====
    if not current_test:
        await update.message.reply_text("⏳ Bunday test mavjud emas yoki test kodi kirishda xatolik mavjud !\n\n👤 Muamolar haqida adminga murojaat qilishingiz mumkin: @Prime_math")
        return

    if "*" not in text:
        await update.message.reply_text("❗Javoblarni quyidagi formatda kiriting: 55*abcde")
        return

    code, ans = text.split("*", 1)

    if code != current_test["code"]:
        return

    key = current_test["key"]

    correct = sum(
        1 for i in range(len(key))
        if i < len(ans) and ans[i] == key[i]
    )

    percent = int((correct / len(key)) * 100)

    current_test["results"][uid] = {
        "correct": correct,
        "percent": percent,
        "answers": ans
    }

    await update.message.reply_text("✅ Javob qabul qilindi, javobingizni o'zgartirish uchun qayta o'zgartirilgan javobingizni kiriting !")

# ================= STOP TEST =================

async def stop_test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    global current_test

    if not current_test:
        await query.edit_message_text("❌ Bunday test mavjud emas !")
        return

    key = current_test["key"]
    results_list = []

    for uid, data in current_test["results"].items():

        user = users.get(uid)
        if not user:
            continue

        answers = data["answers"]
        correct = data["correct"]
        percent = data["percent"]

        result_text = "📊 Sizning natijangiz:\n\n"

        for i in range(len(key)):
            if i < len(answers):
                emoji = "✅" if answers[i] == key[i] else "❌"
                result_text += f"{i+1}. {answers[i].upper()} {emoji}\n"
            else:
                result_text += f"{i+1}. ❌\n"

        if percent >= 90:
            praise = "🏆 Vapshe a'loku, marslikmisiz...!"
        elif percent >= 70:
            praise = "👏 Yaxshi natija!"
        elif percent >= 50:
            praise = "✍️ Harakat qiling!"
        else:
            praise = "😅 Bo'mapsiz eee..."

        result_text += f"\n📈 Natija: {percent}%\n\n"
        result_text += praise
        result_text += "\n\n📢 Telegram: @Matematika_prime"
        result_text += "\n▶️ YouTube: youtube.com/@MatematikaPrime"

        await context.bot.send_message(int(uid), result_text)

        try:
            img = generate_certificate(user, percent, uid, current_test["code"])
            await context.bot.send_document(int(uid), open(img, "rb"))
            os.remove(img)
        except Exception as e:
            print(f"Certificate error: {e}")

        results_list.append({
            "name": user["name"],
            "surname": user["surname"],
            "percent": percent,
            "correct": correct
        })

    history.append({
        "code": current_test["code"],
        "question_count": len(key),
        "results": results_list
    })

    save(HISTORY_FILE, history)
    current_test = {}

    await query.edit_message_text("✅ Test yakunlandi")

# ================= ADMIN BUTTONS =================

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "new":
        context.user_data["admin_step"] = "code"
        await query.edit_message_text("Test kodini kiriting:")
        return

    if query.data == "results":
        context.user_data["admin_step"] = "which"
        await query.edit_message_text("Qaysi test kodi kerak?")
        return

    if query.data == "stop":
        await stop_test(update, context)

# ================= ERROR HANDLER =================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Update {update} caused error {context.error}")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    app.add_error_handler(error_handler)

    print("🔥 PRIME ISHLADI")
    app.run_polling()

if __name__ == "__main__":
    main()
