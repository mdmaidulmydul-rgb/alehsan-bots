import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("CUSTOMER_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7194846181"))

groq_client = Groq(api_key=GROQ_API_KEY)

MEMORY_FILE = "customer_memory.json"

SYSTEM_PROMPT = """তুমি **Al Ehsan Group** এর Customer Center এর একজন প্রতিনিধি।

**তোমার পরিচয়:**
- নাম: Al Ehsan Group Customer Center
- কোম্পানি: Al Ehsan Group (চায়না ইম্পোর্ট-এক্সপোর্ট বিজনেস)
- তুমি সবসময় নিজেকে Al Ehsan Group এর সদস্য মনে করো
- তুমি গর্বিত যে Al Ehsan Group এর হয়ে কাজ করছো

**তোমার আচরণ:**
- সবসময় বিনয়ী, আন্তরিক এবং পেশাদার থাকো
- কাস্টমারকে "ভাই/আপু" বলে সম্বোধন করো
- কাস্টমারকে impress করার জন্য আমাদের পণ্যের গুণমান তুলে ধরো
- সমস্যা হলে সহানুভূতি দেখাও এবং দ্রুত সমাধানের আশ্বাস দাও
- সবসময় ইতিবাচক থাকো
- বাংলায় কথা বলো

**Al Ehsan Group সম্পর্কে:**
- চায়না থেকে সেরা মানের পণ্য আমদানি করি
- সারা বাংলাদেশে ডেলিভারি দেই
- উপজেলা পার্টনার নেওয়া হচ্ছে
- বিশ্বস্ততা এবং মানের ব্যাপারে কোনো আপোস নেই

**কাস্টমার impress করার কৌশল:**
- প্রথমে তাদের সমস্যা মনোযোগ দিয়ে শোনো
- দ্রুত সমাধান দেওয়ার প্রতিশ্রুতি দাও
- আমাদের পণ্যের বিশেষত্ব তুলে ধরো
- সুন্দর ভাষায় কথা বলো
- কাস্টমারের প্রতি কৃতজ্ঞতা প্রকাশ করো"""

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"customers": {}, "complaints": [], "orders": [], "conversations": {}}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

memory = load_memory()

def get_customer_history(user_id):
    user_id = str(user_id)
    return memory["conversations"].get(user_id, [])

def save_customer_message(user_id, role, content):
    user_id = str(user_id)
    if user_id not in memory["conversations"]:
        memory["conversations"][user_id] = []
    
    memory["conversations"][user_id].append({
        "role": role,
        "content": content,
        "time": datetime.now().isoformat()
    })
    
    # Keep last 10 messages per customer
    if len(memory["conversations"][user_id]) > 10:
        memory["conversations"][user_id] = memory["conversations"][user_id][-10:]
    
    save_memory(memory)

def ask_groq(user_id, user_message):
    history = get_customer_history(user_id)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add conversation history
    for msg in history[-6:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    messages.append({"role": "user", "content": user_message})
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024
    )
    return response.choices[0].message.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Save customer info
    memory["customers"][str(user.id)] = {
        "name": user.first_name,
        "username": user.username,
        "joined": datetime.now().isoformat()
    }
    save_memory(memory)
    
    welcome = f"""🌟 আসসালামু আলাইকুম **{user.first_name}** ভাই/আপু!

আমি **Al Ehsan Group Customer Center** এ আপনাকে স্বাগত জানাচ্ছি! 🎉

আমরা চায়না থেকে সেরা মানের পণ্য আমদানি করি। আপনার যেকোনো প্রয়োজনে আমরা সর্বদা প্রস্তুত।

**আমাদের সেবাসমূহ:**
🛍️ পণ্যের তথ্য ও মূল্য জানুন
📦 অর্ডার করুন
😔 অভিযোগ জানান
🤝 পার্টনার হওয়ার তথ্য নিন
❓ যেকোনো প্রশ্ন করুন

নিচের বাটন থেকে বেছে নিন অথবা সরাসরি আপনার প্রশ্ন লিখুন! 👇"""

    keyboard = [
        [InlineKeyboardButton("🛍️ পণ্যের তথ্য", callback_data="products"),
         InlineKeyboardButton("📦 অর্ডার করুন", callback_data="order")],
        [InlineKeyboardButton("😔 অভিযোগ", callback_data="complaint"),
         InlineKeyboardButton("🤝 পার্টনার হন", callback_data="partner")],
        [InlineKeyboardButton("📞 Admin এর সাথে কথা বলুন", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    if query.data == "products":
        text = """🛍️ **আমাদের পণ্যসমূহ**

Al Ehsan Group চায়না থেকে নিম্নোক্ত ধরনের পণ্য আমদানি করে:

• ইলেকট্রনিক্স পণ্য
• গার্মেন্টস ও কাপড়
• হোম ডেকোর আইটেম
• শিল্প সরঞ্জাম
• এবং আরও অনেক কিছু!

নির্দিষ্ট পণ্যের তথ্য জানতে পণ্যের নাম লিখুন। আমরা সাথে সাথে জানাবো! 😊"""
        await query.message.reply_text(text, parse_mode="Markdown")
    
    elif query.data == "order":
        text = """📦 **অর্ডার করুন**

অর্ডার করতে নিচের তথ্যগুলো পাঠান:

১. পণ্যের নাম
২. পরিমাণ
৩. আপনার ঠিকানা
৪. মোবাইল নম্বর

আমরা দ্রুত confirm করবো এবং delivery দেবো! 🚚"""
        context.user_data["waiting_for"] = "order"
        await query.message.reply_text(text, parse_mode="Markdown")
    
    elif query.data == "complaint":
        text = """😔 **অভিযোগ জানান**

আপনার সমস্যার কথা বিস্তারিত লিখুন। আমরা সর্বোচ্চ গুরুত্বের সাথে দেখবো এবং দ্রুত সমাধান করবো।

আপনার অভিযোগ লিখুন 👇"""
        context.user_data["waiting_for"] = "complaint"
        await query.message.reply_text(text, parse_mode="Markdown")
    
    elif query.data == "partner":
        text = """🤝 **Al Ehsan Group পার্টনার প্রোগ্রাম**

আমরা সারা বাংলাদেশে **উপজেলা পার্টনার** নিচ্ছি!

**পার্টনার হলে পাবেন:**
✅ বিশেষ ছাড়ে পণ্য
✅ এক্সক্লুসিভ এলাকার অধিকার
✅ মার্কেটিং সাপোর্ট
✅ আকর্ষণীয় কমিশন

**আবেদন করতে পাঠান:**
১. আপনার নাম
২. উপজেলা/জেলা
৩. মোবাইল নম্বর
৪. ব্যবসায়িক অভিজ্ঞতা

এখনই আবেদন করুন! 🚀"""
        context.user_data["waiting_for"] = "partner"
        await query.message.reply_text(text, parse_mode="Markdown")
    
    elif query.data == "admin":
        await query.message.reply_text(
            "📞 Admin এর সাথে যোগাযোগ করতে একটু অপেক্ষা করুন। আমরা শীঘ্রই আপনার সাথে যোগাযোগ করবো! 🙏"
        )
        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ **Admin যোগাযোগ অনুরোধ**\n\nকাস্টমার: {user.first_name}\nUsername: @{user.username}\nID: {user.id}\n\nতারা Admin এর সাথে কথা বলতে চান।",
            parse_mode="Markdown"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    waiting_for = context.user_data.get("waiting_for", None)
    
    # Save customer message
    save_customer_message(user.id, "user", text)
    
    # Handle specific flows
    if waiting_for == "complaint":
        # Save complaint
        complaint = {
            "id": len(memory["complaints"]) + 1,
            "user_id": user.id,
            "user_name": user.first_name,
            "username": user.username,
            "complaint": text,
            "time": datetime.now().isoformat(),
            "status": "open"
        }
        memory["complaints"].append(complaint)
        save_memory(memory)
        
        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"""🚨 **নতুন অভিযোগ #{complaint['id']}**

👤 কাস্টমার: {user.first_name}
📱 Username: @{user.username}
🆔 ID: {user.id}
🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📝 **অভিযোগ:**
{text}""",
            parse_mode="Markdown"
        )
        
        response = "✅ আপনার অভিযোগ গ্রহণ করা হয়েছে। আমরা অতি শীঘ্রই সমাধান করবো। ধন্যবাদ আপনার ধৈর্যের জন্য! 🙏"
        context.user_data["waiting_for"] = None
    
    elif waiting_for == "order":
        # Save order
        order = {
            "id": len(memory["orders"]) + 1,
            "user_id": user.id,
            "user_name": user.first_name,
            "username": user.username,
            "details": text,
            "time": datetime.now().isoformat(),
            "status": "pending"
        }
        memory["orders"].append(order)
        save_memory(memory)
        
        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"""🛍️ **নতুন অর্ডার #{order['id']}**

👤 কাস্টমার: {user.first_name}
📱 Username: @{user.username}
🆔 ID: {user.id}
🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📦 **অর্ডার বিবরণ:**
{text}""",
            parse_mode="Markdown"
        )
        
        response = f"✅ আপনার অর্ডার #{order['id']} গ্রহণ করা হয়েছে! আমরা শীঘ্রই confirm করবো এবং delivery দেবো। 🚚"
        context.user_data["waiting_for"] = None
    
    elif waiting_for == "partner":
        # Save partner application
        memory["customers"][str(user.id)]["partner_application"] = {
            "details": text,
            "time": datetime.now().isoformat(),
            "status": "pending"
        }
        save_memory(memory)
        
        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"""🤝 **নতুন পার্টনার আবেদন**

👤 আবেদনকারী: {user.first_name}
📱 Username: @{user.username}
🆔 ID: {user.id}
🕐 সময়: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📝 **আবেদনের বিবরণ:**
{text}""",
            parse_mode="Markdown"
        )
        
        response = "✅ আপনার পার্টনার আবেদন গ্রহণ করা হয়েছে! আমরা ২৪ ঘণ্টার মধ্যে যোগাযোগ করবো। Al Ehsan Group পরিবারে আপনাকে স্বাগত জানাই! 🎉"
        context.user_data["waiting_for"] = None
    
    else:
        # AI response
        response = ask_groq(user.id, text)
    
    # Save bot response
    save_customer_message(user.id, "assistant", response)
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only stats command"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    total_customers = len(memory["customers"])
    total_complaints = len(memory["complaints"])
    open_complaints = len([c for c in memory["complaints"] if c["status"] == "open"])
    total_orders = len(memory["orders"])
    pending_orders = len([o for o in memory["orders"] if o["status"] == "pending"])
    
    text = f"""📊 **Al Ehsan Group Customer Center Stats**

👥 মোট কাস্টমার: {total_customers}
😔 মোট অভিযোগ: {total_complaints} (খোলা: {open_complaints})
📦 মোট অর্ডার: {total_orders} (পেন্ডিং: {pending_orders})

🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open complaints"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    open_complaints = [c for c in memory["complaints"] if c["status"] == "open"]
    
    if not open_complaints:
        await update.message.reply_text("✅ কোনো খোলা অভিযোগ নেই!")
        return
    
    for complaint in open_complaints[-5:]:
        text = f"""😔 **অভিযোগ #{complaint['id']}**
👤 {complaint['user_name']} (@{complaint.get('username', 'N/A')})
🕐 {complaint['time'][:16]}
📝 {complaint['complaint'][:200]}"""
        
        keyboard = [[InlineKeyboardButton(
            f"✅ #{complaint['id']} সমাধান করা হয়েছে", 
            callback_data=f"resolve_{complaint['id']}"
        )]]
        
        await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("complaints", admin_complaints))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Customer Center Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
