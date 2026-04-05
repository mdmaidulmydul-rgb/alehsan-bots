import os
import json
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("MARKETING_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7194846181"))

groq_client = Groq(api_key=GROQ_API_KEY)

# Memory storage
MEMORY_FILE = "marketing_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conversations": [], "groups": {}, "posts": [], "settings": {}}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

memory = load_memory()

def ask_groq(prompt, system_prompt=None):
    if not system_prompt:
        system_prompt = """তুমি Al Ehsan Group এর Marketing Manager Bot। 
        তুমি একজন অভিজ্ঞ মার্কেটিং ম্যানেজার। 
        তুমি বাংলায় কথা বলো।
        তুমি চায়না ইম্পোর্ট-এক্সপোর্ট বিজনেসের জন্য কাজ করো।
        তোমার কাছে সব কিছু মনে থাকে।"""
    
    # Add memory context
    mem_context = ""
    if memory["conversations"]:
        recent = memory["conversations"][-5:]
        mem_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
    
    messages = [{"role": "system", "content": system_prompt}]
    if mem_context:
        messages.append({"role": "system", "content": f"Previous context:\n{mem_context}"})
    messages.append({"role": "user", "content": prompt})
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024
    )
    return response.choices[0].message.content

def add_order_button_to_image(image_bytes, caption=""):
    """Add 'অর্ডার করুন' button overlay to image"""
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size
    
    # Create overlay
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Add semi-transparent banner at bottom
    banner_height = int(height * 0.15)
    draw.rectangle(
        [(0, height - banner_height), (width, height)],
        fill=(138, 43, 226, 200)  # Purple with transparency
    )
    
    # Add Al Ehsan Group watermark
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
                                         max(20, width // 20))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 
                                         max(14, width // 30))
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Al Ehsan Group text
    text = "Al Ehsan Group"
    draw.text((20, height - banner_height + 10), text, font=font_large, fill=(255, 255, 255, 255))
    
    # Order button area
    btn_text = "📦 অর্ডার করুন"
    draw.text((20, height - banner_height // 2), btn_text, font=font_small, fill=(255, 215, 0, 255))
    
    # Merge
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")
    
    output = BytesIO()
    result.save(output, format="JPEG", quality=95)
    output.seek(0)
    return output

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = f"""🌟 **আসসালামু আলাইকুম {user.first_name}!**

আমি **Al Ehsan Group Marketing Manager Bot** 🤖

**আমি যা করতে পারি:**
📸 ছবি পাঠাও → আমি edit করে অর্ডার বাটন যোগ করবো
📢 `/post [group_id]` → নির্দিষ্ট গ্রুপে পোস্ট করবো
➕ `/addgroup [group_id] [name]` → নতুন গ্রুপ যোগ করো
📋 `/groups` → সব গ্রুপের লিস্ট
💬 যেকোনো প্রশ্ন করো, আমি উত্তর দেবো!

**Al Ehsan Group** 🇧🇩🇨🇳"""
    
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos - edit and add order button"""
    user = update.effective_user
    
    # Only admin can use this
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ শুধুমাত্র Admin এই feature টি ব্যবহার করতে পারবেন।")
        return
    
    await update.message.reply_text("🎨 ছবি edit করছি... একটু অপেক্ষা করুন!")
    
    try:
        # Get the photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Download photo
        photo_bytes = await file.download_as_bytearray()
        
        # Get caption from message
        caption = update.message.caption or ""
        
        # Add order button to image
        edited_image = add_order_button_to_image(bytes(photo_bytes), caption)
        
        # Create inline keyboard for posting
        groups = memory.get("groups", {})
        keyboard = []
        
        if groups:
            for group_id, group_name in groups.items():
                keyboard.append([InlineKeyboardButton(
                    f"📢 {group_name} এ পোস্ট করো", 
                    callback_data=f"post_{group_id}"
                )])
        
        keyboard.append([InlineKeyboardButton("✅ শুধু Save করো", callback_data="save_only")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Save edited image temporarily
        context.user_data["edited_image"] = edited_image.read()
        context.user_data["caption"] = caption
        
        # Send edited image back
        edited_image.seek(0)
        
        # Generate AI caption suggestion
        ai_caption = ask_groq(
            f"এই পণ্যের জন্য একটি আকর্ষণীয় মার্কেটিং ক্যাপশন লিখো বাংলায়। পণ্যের বিবরণ: {caption if caption else 'চায়না ইম্পোর্ট পণ্য'}। ৩-৪ লাইনে লিখো, ইমোজি ব্যবহার করো।"
        )
        
        await update.message.reply_photo(
            photo=BytesIO(context.user_data["edited_image"]),
            caption=f"✅ **Edit হয়েছে!**\n\n**AI ক্যাপশন সাজেশন:**\n{ai_caption}\n\nকোন গ্রুপে পোস্ট করবো?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Save to memory
        memory["posts"].append({
            "time": datetime.now().isoformat(),
            "caption": caption,
            "ai_caption": ai_caption
        })
        save_memory(memory)
        
    except Exception as e:
        logger.error(f"Photo error: {e}")
        await update.message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("post_"):
        group_id = query.data.replace("post_", "")
        
        if "edited_image" in context.user_data:
            try:
                caption = context.user_data.get("caption", "")
                ai_caption = f"📦 Al Ehsan Group\n\nঅর্ডার করতে Admin এ যোগাযোগ করুন।"
                
                # Create order button
                keyboard = [[InlineKeyboardButton("📦 অর্ডার করুন", url="https://t.me/AlEhsanGroup")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_photo(
                    chat_id=int(group_id),
                    photo=BytesIO(context.user_data["edited_image"]),
                    caption=ai_caption,
                    reply_markup=reply_markup
                )
                
                group_name = memory["groups"].get(group_id, group_id)
                await query.edit_message_caption(
                    caption=f"✅ **{group_name}** এ পোস্ট করা হয়েছে!"
                )
                
            except Exception as e:
                await query.message.reply_text(f"❌ পোস্ট করতে সমস্যা: {str(e)}")
    
    elif query.data == "save_only":
        await query.edit_message_caption(caption="✅ ছবি save হয়েছে!")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a group to memory"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ ব্যবহার: `/addgroup [group_id] [group_name]`", parse_mode="Markdown")
        return
    
    group_id = context.args[0]
    group_name = " ".join(context.args[1:])
    
    memory["groups"][group_id] = group_name
    save_memory(memory)
    
    await update.message.reply_text(f"✅ **{group_name}** গ্রুপ যোগ হয়েছে!\nID: `{group_id}`", parse_mode="Markdown")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all groups"""
    groups = memory.get("groups", {})
    if not groups:
        await update.message.reply_text("❌ কোনো গ্রুপ যোগ করা হয়নি। `/addgroup` দিয়ে যোগ করুন।")
        return
    
    text = "📋 **যোগ করা গ্রুপসমূহ:**\n\n"
    for gid, gname in groups.items():
        text += f"• **{gname}** — `{gid}`\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with AI"""
    user = update.effective_user
    text = update.message.text
    
    # Save to memory
    memory["conversations"].append({"role": "user", "content": f"{user.first_name}: {text}"})
    if len(memory["conversations"]) > 20:
        memory["conversations"] = memory["conversations"][-20:]
    
    # Get AI response
    response = ask_groq(text)
    
    memory["conversations"].append({"role": "assistant", "content": response})
    save_memory(memory)
    
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addgroup", add_group))
    app.add_handler(CommandHandler("groups", list_groups))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Marketing Manager Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
