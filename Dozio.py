import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State

from config import BOT_TOKEN
from database import (
    init_db,
    get_user_by_telegram_id,
    get_user_by_username,
    create_user,
    get_tasks_for_user,
    create_report,
    create_task,
    get_reports_for_supervisor,
    rate_report,
    get_team_users,
    get_all_users_by_role,
    get_reports_for_user,
)
from datetime import datetime
import jdatetime
import logging

logging.basicConfig(level=logging.INFO)

CANCEL_BTN = KeyboardButton(text="❌ کنسل")
def admin_menu():
    kb = [
        [KeyboardButton(text="➕ افزودن مدیر میانی"), KeyboardButton(text="➕ تعریف تسک")],
        [KeyboardButton(text="📥 مشاهده گزارش‌ها"), KeyboardButton(text="🗂 مشاهده تسک‌های فعال")],
        [KeyboardButton(text="👥 لیست کاربران")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def manager_menu():
    kb = [
        [KeyboardButton(text="➕ افزودن کاربر"), KeyboardButton(text="➕ تعریف تسک")],
        [KeyboardButton(text="📝 ثبت گزارش برای مدیر"), KeyboardButton(text="📥 مشاهده گزارش‌ها")],
        [KeyboardButton(text="🗂 مشاهده تسک‌های فعال"), KeyboardButton(text="👥 لیست اعضای تیم")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def member_menu():
    kb = [
        [KeyboardButton(text="🗂 مشاهده تسک‌های فعال"), KeyboardButton(text="📝 ارسال گزارش")],
        [KeyboardButton(text="📥 مشاهده گزارش‌های من")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ کنسل")]], resize_keyboard=True)

def cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[[CANCEL_BTN]], resize_keyboard=True)

# --- استیت‌ها
class AddManagerState(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_position = State()

class AddUserState(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_position = State()

class ReportState(StatesGroup):
    waiting_for_report = State()

class ManagerReportState(StatesGroup):
    waiting_for_report = State()

class TaskCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_deadline = State()
    waiting_for_reminder = State()
    waiting_for_assignee = State()

class ScoreState(StatesGroup):
    waiting_for_report_id = State()
    waiting_for_score = State()

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(Command("start"))
    async def handle_start(message: types.Message, state: FSMContext):
        telegram_id = message.from_user.id
        username = message.from_user.username or ""
        name = message.from_user.full_name
        user = get_user_by_telegram_id(telegram_id)
        if not user:
            # اگر اولین بار است می‌آید، مدیر اصلی می‌شود (اولین نفر)
            if not get_all_users_by_role('admin'):
                create_user(telegram_id, username, name, role="admin")
                role = "admin"
            else:
                # اگر فقط username ثبت شده بوده و الان کاربر با ربات چت کرد، username و telegram_id را آپدیت کن
                user_by_username = get_user_by_username(username)
                if user_by_username:
                    create_user(telegram_id, username, name, role=user_by_username['role'], supervisor_id=user_by_username['supervisor_id'])
                    role = user_by_username['role']
                else:
                    create_user(telegram_id, username, name, role="member")
                    role = "member"
        else:
            role = user['role']

        if role == 'admin':
            await message.answer("خوش اومدی مدیر اصلی 👑", reply_markup=admin_menu())
        elif role == 'manager':
            await message.answer("خوش اومدی مدیر میانی 🌟", reply_markup=manager_menu())
        else:
            await message.answer("سلام! خوش اومدی. از منوی زیر استفاده کن:", reply_markup=member_menu())

    @dp.message(F.text == CANCEL_BTN.text)
    async def cancel_anytime(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if user:
            if user['role'] == 'admin':
                await message.answer("عملیات لغو شد.", reply_markup=admin_menu())
            elif user['role'] == 'manager':
                await message.answer("عملیات لغو شد.", reply_markup=manager_menu())
            else:
                await message.answer("عملیات لغو شد.", reply_markup=member_menu())
        else:
            await message.answer("عملیات لغو شد.")
        await state.clear()

    # --- افزودن مدیر میانی
    @dp.message(F.text == "➕ افزودن مدیر میانی")
    async def add_manager_start(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if not user or user['role'] != 'admin':
            await message.answer("دسترسی فقط برای مدیر اصلی!", reply_markup=admin_menu())
            return
        await message.answer("آیدی عددی یا یوزرنیم مدیر میانی را وارد کنید (مثلاً: @user یا 123456789):", reply_markup=cancel_menu())
        await state.set_state(AddManagerState.waiting_for_id)

    @dp.message(AddManagerState.waiting_for_id)
    async def add_manager_name(message: types.Message, state: FSMContext):
        text = message.text.strip()
        telegram_id = None
        username = None
        if text.startswith('@'):
            username = text[1:]
        elif text.isdigit():
            telegram_id = int(text)
        else:
            await message.answer("فرمت آیدی/یوزرنیم اشتباه است.", reply_markup=cancel_menu())
            return
        await state.update_data(telegram_id=telegram_id, username=username)
        await message.answer("نام کامل مدیر میانی را وارد کنید:", reply_markup=cancel_menu())
        await state.set_state(AddManagerState.waiting_for_name)

    @dp.message(AddManagerState.waiting_for_name)
    async def add_manager_position(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer("سمت (مثلاً: مدیر فروش):", reply_markup=cancel_menu())
        await state.set_state(AddManagerState.waiting_for_position)

    @dp.message(AddManagerState.waiting_for_position)
    async def add_manager_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        create_user(
            data.get('telegram_id'),
            data.get('username'),
            data['name'] + f" ({message.text})",
            role="manager",
            supervisor_id=get_user_by_telegram_id(message.from_user.id)['id']
        )
        await message.answer("✅ مدیر میانی با موفقیت افزوده شد.", reply_markup=admin_menu())
        await state.clear()

    # --- افزودن کاربر توسط مدیر میانی
    @dp.message(F.text == "➕ افزودن کاربر")
    async def add_user_start(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if not user or user['role'] != 'manager':
            await message.answer("دسترسی فقط برای مدیر میانی!", reply_markup=manager_menu())
            return
        await message.answer("آیدی عددی یا یوزرنیم کاربر را وارد کنید (مثلاً: @user یا 123456789):", reply_markup=cancel_menu())
        await state.set_state(AddUserState.waiting_for_id)

    @dp.message(AddUserState.waiting_for_id)
    async def add_user_name(message: types.Message, state: FSMContext):
        text = message.text.strip()
        telegram_id = None
        username = None
        if text.startswith('@'):
            username = text[1:]
        elif text.isdigit():
            telegram_id = int(text)
        else:
            await message.answer("فرمت آیدی/یوزرنیم اشتباه است.", reply_markup=cancel_menu())
            return
        await state.update_data(telegram_id=telegram_id, username=username)
        await message.answer("نام کامل کاربر را وارد کنید:", reply_markup=cancel_menu())
        await state.set_state(AddUserState.waiting_for_name)

    @dp.message(AddUserState.waiting_for_name)
    async def add_user_position(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer("سمت کاربر را وارد کنید (مثلاً: کارشناس پشتیبانی):", reply_markup=cancel_menu())
        await state.set_state(AddUserState.waiting_for_position)

    @dp.message(AddUserState.waiting_for_position)
    async def add_user_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        create_user(
            data.get('telegram_id'),
            data.get('username'),
            data['name'] + f" ({message.text})",
            role="member",
            supervisor_id=get_user_by_telegram_id(message.from_user.id)['id']
        )
        await message.answer("✅ کاربر با موفقیت افزوده شد.", reply_markup=manager_menu())
        await state.clear()

    # --- تعریف تسک
    @dp.message(F.text == "➕ تعریف تسک")
    async def start_task_creation(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if user['role'] not in ['admin', 'manager']:
            await message.answer("دسترسی فقط برای مدیران!", reply_markup=admin_menu())
            return
        await message.answer("عنوان تسک را وارد کنید:", reply_markup=cancel_menu())
        await state.set_state(TaskCreation.waiting_for_title)

    @dp.message(TaskCreation.waiting_for_title)
    async def get_task_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text)
        await message.answer("توضیح تسک را وارد کنید (یا بنویسید ندارد):", reply_markup=cancel_menu())
        await state.set_state(TaskCreation.waiting_for_description)

    @dp.message(TaskCreation.waiting_for_description)
    async def get_task_description(message: types.Message, state: FSMContext):
        desc = message.text if message.text.lower() != 'ندارد' else ''
        await state.update_data(description=desc)
        await message.answer("ددلاین را به شمسی وارد کنید (مثال: 26 خرداد 1404):", reply_markup=cancel_menu())
        await state.set_state(TaskCreation.waiting_for_deadline)

    @dp.message(TaskCreation.waiting_for_deadline)
    async def get_task_deadline(message: types.Message, state: FSMContext):
        date_str = message.text.strip()
        try:
            months = {
                "فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4, "مرداد": 5, "شهریور": 6,
                "مهر": 7, "آبان": 8, "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12
            }
            parts = date_str.split()
            if len(parts) != 3 or parts[1] not in months:
                raise ValueError
            day = int(parts[0])
            month = months[parts[1]]
            year = int(parts[2])
            jalali = jdatetime.date(year, month, day)
            miladi = jalali.togregorian().isoformat()
            await state.update_data(deadline=miladi)
            await message.answer(
                "چه بازه‌ای برای یادآوری تنظیم کنم؟\n"
                "نمونه:\n6 ساعت\nیا\n3 روز\nیا بنویسید: فقط روز ددلاین",
                reply_markup=cancel_menu()
            )
            await state.set_state(TaskCreation.waiting_for_reminder)
        except Exception:
            await message.answer("فرمت ددلاین نادرست است. مثال درست: 26 خرداد 1404")

    @dp.message(TaskCreation.waiting_for_reminder)
    async def get_reminder(message: types.Message, state: FSMContext):
        text = message.text.strip()
        if "ساعت" in text:
            try:
                value = int(text.replace("ساعت", "").strip())
                if not (1 <= value <= 48):
                    raise ValueError
                await state.update_data(reminder_type="hour", reminder_value=value)
            except Exception:
                await message.answer("عدد ساعت باید بین 1 تا 48 باشد.")
                return
        elif "روز" in text:
            try:
                value = int(text.replace("روز", "").strip())
                if not (1 <= value <= 30):
                    raise ValueError
                await state.update_data(reminder_type="day", reminder_value=value)
            except Exception:
                await message.answer("عدد روز باید بین 1 تا 30 باشد.")
                return
        else:
            await state.update_data(reminder_type="none", reminder_value=None)

        user = get_user_by_telegram_id(message.from_user.id)
        if user['role'] == 'admin':
            managers = get_all_users_by_role("manager")
            if not managers:
                await message.answer("مدیر میانی ثبت نشده است.")
                await state.clear()
                return
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"{mgr['name']}", callback_data=f"assign_mgr_{mgr['id']}")]
                    for mgr in managers
                ]
            )
            await message.answer("کدام مدیر میانی دریافت‌کننده تسک باشد؟", reply_markup=kb)
        elif user['role'] == 'manager':
            team = get_team_users(user['id'])
            if not team:
                await message.answer("هیچ عضوی برای تیم شما ثبت نشده.", reply_markup=manager_menu())
                await state.clear()
                return
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"{member['name']}", callback_data=f"assign_mem_{member['id']}")]
                    for member in team
                ]
            )
            await message.answer("کدام عضو تیم دریافت‌کننده تسک باشد؟", reply_markup=kb)
        await state.set_state(TaskCreation.waiting_for_assignee)

    @dp.callback_query(TaskCreation.waiting_for_assignee)
    async def assign_task_callback(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        user = get_user_by_telegram_id(call.from_user.id)
        if user['role'] == 'admin' and call.data.startswith("assign_mgr_"):
            assignee_id = int(call.data.replace("assign_mgr_", ""))
        elif user['role'] == 'manager' and call.data.startswith("assign_mem_"):
            assignee_id = int(call.data.replace("assign_mem_", ""))
        else:
            await call.answer("خطا در انتخاب دریافت‌کننده.")
            return
        assigner = user
        create_task(
            title=data['title'],
            description=data['description'],
            assigned_by=assigner['id'],
            assigned_to=assignee_id,
            deadline=data['deadline'],
            reminder_type=data['reminder_type'],
            reminder_value=data['reminder_value'],
            is_urgent=0,
            created_at=datetime.now().isoformat()
        )
        await call.message.answer("✅ تسک با موفقیت ثبت شد.", reply_markup=manager_menu() if assigner['role']=='manager' else admin_menu())
        await state.clear()
        await call.answer()

    # --- مشاهده تسک‌های فعال
    @dp.message(F.text == "🗂 مشاهده تسک‌های فعال")
    async def handle_tasks(message: types.Message, state: FSMContext):
        telegram_id = message.from_user.id
        tasks = get_tasks_for_user(telegram_id)
        if not tasks:
            await message.answer("شما هیچ تسک فعالی ندارید.")
            return
        response = "📋 تسک‌های شما:\n\n"
        for task in tasks:
            rem = ""
            if task.get("reminder_type") == "hour":
                rem = f"یادآوری هر {task['reminder_value']} ساعت"
            elif task.get("reminder_type") == "day":
                rem = f"یادآوری هر {task['reminder_value']} روز"
            else:
                rem = "یادآوری فقط روز ددلاین"
            response += (
                f"📌 {task['title']}\n"
                f"📝 {task['description']}\n"
                f"⏰ مهلت: {task['deadline']}\n"
                f"⏱ {rem}\n\n"
            )
        await message.answer(response)

    # --- گزارش اعضا
    @dp.message(F.text == "📝 ارسال گزارش")
    async def handle_report_start(message: types.Message, state: FSMContext):
        await message.answer("لطفاً متن گزارش خود را ارسال کنید:", reply_markup=cancel_menu())
        await state.set_state(ReportState.waiting_for_report)

    @dp.message(ReportState.waiting_for_report)
    async def handle_report_save(message: types.Message, state: FSMContext):
        telegram_id = message.from_user.id
        user = get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("ابتدا با دستور /start ثبت‌نام کن.")
            await state.clear()
            return
        content = message.text
        timestamp = datetime.now().isoformat()
        create_report(task_id=None, user_id=user['id'], content=content, timestamp=timestamp)
        await message.answer("✅ گزارش شما با موفقیت ثبت شد.", reply_markup=member_menu())
        await state.clear()

    # --- گزارش مدیر میانی برای مدیر اصلی
    @dp.message(F.text == "📝 ثبت گزارش برای مدیر")
    async def handle_manager_report_start(message: types.Message, state: FSMContext):
        await message.answer("متن گزارش برای مدیر اصلی را وارد کنید:", reply_markup=cancel_menu())
        await state.set_state(ManagerReportState.waiting_for_report)

    @dp.message(ManagerReportState.waiting_for_report)
    async def handle_manager_report_save(message: types.Message, state: FSMContext):
        telegram_id = message.from_user.id
        user = get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("ابتدا با دستور /start ثبت‌نام کن.")
            await state.clear()
            return
        content = "[گزارش مدیر میانی]\n" + message.text
        timestamp = datetime.now().isoformat()
        create_report(task_id=None, user_id=user['id'], content=content, timestamp=timestamp)
        await message.answer("✅ گزارش برای مدیر اصلی ثبت شد.", reply_markup=manager_menu())
        await state.clear()

    # --- مشاهده گزارش‌ها
    @dp.message(F.text == "📥 مشاهده گزارش‌ها")
    async def show_reports(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if user['role'] == 'admin':
            reports = get_reports_for_supervisor(None, all_admin=True)
        elif user['role'] == 'manager':
            reports = get_reports_for_supervisor(user['id'])
        else:
            await message.answer("این بخش فقط برای مدیران است.", reply_markup=member_menu())
            return
        if not reports:
            await message.answer("هیچ گزارشی برای نمایش وجود ندارد.")
            return
        response = "📊 لیست گزارش‌ها:\n\n"
        for rep in reports:
            response += (
                f"🆔 Report ID: {rep['id']}\n"
                f"👤 کاربر: {rep['name']}\n"
                f"📝 {rep['content']}\n"
                f"📅 {rep['timestamp']}\n"
                f"⭐ امتیاز: {rep['score'] or 'ندارد'}\n\n"
            )
        response += "برای امتیاز دادن، دستور زیر را وارد کنید:\n/score <report_id>"
        await message.answer(response)

    # --- مشاهده گزارش‌های من (کاربر)
    @dp.message(F.text == "📥 مشاهده گزارش‌های من")
    async def show_my_reports(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("ابتدا با دستور /start ثبت‌نام کن.")
            return
        reports = get_reports_for_user(user['id'])
        if not reports:
            await message.answer("گزارشی برای شما ثبت نشده است.")
            return
        response = "📥 گزارش‌های ثبت‌شده شما:\n\n"
        for rep in reports:
            response += (
                f"📝 {rep['content']}\n"
                f"📅 {rep['timestamp']}\n"
                f"⭐ امتیاز: {rep['score'] or 'ندارد'}\n\n"
            )
        await message.answer(response)

    # --- امتیازدهی به گزارش‌ها
    @dp.message(Command("score"))
    async def score_start(message: types.Message, state: FSMContext):
        args = message.text.strip().split()
        if len(args) != 2 or not args[1].isdigit():
            await message.answer("فرمت صحیح:\n/score <report_id>")
            return
        await state.update_data(report_id=int(args[1]))
        await message.answer("لطفاً امتیاز را وارد کنید (۱ تا ۵):", reply_markup=cancel_menu())
        await state.set_state(ScoreState.waiting_for_score)

    @dp.message(ScoreState.waiting_for_score)
    async def score_submit(message: types.Message, state: FSMContext):
        if message.text not in ['1', '2', '3', '4', '5']:
            await message.answer("فقط یک عدد بین ۱ تا ۵ وارد کنید.")
            return
        data = await state.get_data()
        report_id = data['report_id']
        score = int(message.text)
        rate_report(report_id, score)
        await message.answer("✅ امتیاز ثبت شد.", reply_markup=admin_menu())
        await state.clear()

    # --- لیست کاربران (درختی برای admin، تیمی برای manager)
    @dp.message(F.text == "👥 لیست کاربران")
    async def list_users_admin(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if user['role'] != 'admin':
            await message.answer("دسترسی فقط برای مدیر اصلی!", reply_markup=member_menu())
            return
        managers = get_all_users_by_role("manager")
        msg = "👥 لیست مدیرهای میانی و اعضای تیم‌ها:\n"
        for manager in managers:
            msg += f"\n🟦 مدیر: {manager['name']} (ID:{manager['telegram_id']})\n"
            team = get_team_users(manager['id'])
            for member in team:
                msg += f"    └ 🟩 {member['name']} (ID:{member['telegram_id']})\n"
        await message.answer(msg)

    @dp.message(F.text == "👥 لیست اعضای تیم")
    async def list_users_manager(message: types.Message, state: FSMContext):
        user = get_user_by_telegram_id(message.from_user.id)
        if user['role'] != 'manager':
            await message.answer("این بخش فقط برای مدیرهای میانی است!", reply_markup=member_menu())
            return
        team = get_team_users(user['id'])
        if not team:
            await message.answer("تیمی ثبت نشده است.")
            return
        msg = "👥 لیست اعضای تیم:\n"
        for member in team:
            msg += f"🟩 {member['name']} (ID:{member['telegram_id']})\n"
        await message.answer(msg)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
