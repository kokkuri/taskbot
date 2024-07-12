import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
import logging

API_TOKEN = 'mytoken'

conn = psycopg2.connect(
    dbname='dbname',
    user='user',
    password='password',
    host='host',
    port ="5432"
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

task_cb = CallbackData("task", "action", "value")
user_state = {} #словарь для хранения состояний пользователя
#приветственное сообщение
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(
        "Welcome to the Task Reminder Bot!\n"
        "This bot will help you to schedule all your tasks.\n"
        "Use /help to see all available commands."
    )
#список доступных команд
@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    await message.reply(
        "Here's all of the available commands:\n"
        "/add - Schedule new task\n"
        "/list - List of all of your tasks\n"
        "/delete - Delete task by selecting it from a list\n"
        "/edit - Edit a task by selecting it from a list"
    )

#вызов команды добавления задачи
@dp.message_handler(commands=['add'])
async def add_task(message: types.Message):
    await message.answer("Please provide the description of the task:")
    user_state[message.from_user.id] = {'state': 'awaiting_task_name', 'action': 'add'}

#вызов команды для редактирования задач
@dp.message_handler(commands=['edit'])
async def edit_task(message: types.Message):
    user_id = message.from_user.id

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, task, remind_at FROM tasks WHERE user_id = %s ORDER BY remind_at", (user_id,))
            rows = cursor.fetchall()

        if not rows:
            await message.answer("No tasks found to edit.")
            return

        markup = InlineKeyboardMarkup(row_width=1)
        for row in rows:
            #кнопки с задачами
            task_button = InlineKeyboardButton(f"{row[1]} at {row[2]}", callback_data=task_cb.new(action='select_edit', value=row[0]))
            markup.add(task_button)
        await message.answer("Please select the task to edit:", reply_markup=markup)
    except Exception as e:
        await message.answer(f"Failed to retrieve tasks: {e}")


@dp.callback_query_handler(task_cb.filter(action='select_edit'))
async def process_edit_selection(callback_query: types.CallbackQuery, callback_data: dict):
    user_id = callback_query.from_user.id
    task_id = callback_data['value']
    user_state[user_id] = {'state': 'awaiting_task_name', 'task_id': task_id, 'action': 'edit'}

    await bot.send_message(user_id, "Please provide the new name of the task:")


@dp.message_handler(lambda message: user_state.get(message.from_user.id, {}).get('state') == 'awaiting_task_name')
async def process_task_name(message: types.Message):
    user_state[message.from_user.id]['task_name'] = message.text
    user_state[message.from_user.id]['state'] = 'awaiting_date_selection'
    await send_date_selection_markup(message.from_user.id)


async def send_date_selection_markup(user_id):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("Today", callback_data=task_cb.new(action='set_date', value='today')),
        InlineKeyboardButton("Tomorrow", callback_data=task_cb.new(action='set_date', value='tomorrow')),
        InlineKeyboardButton("Custom Date", callback_data=task_cb.new(action='set_date', value='custom'))
    )
    for i in range(7):
        day_name = (datetime.now() + timedelta(days=i)).strftime('%A')
        markup.add(InlineKeyboardButton(day_name, callback_data=task_cb.new(action='set_date', value=day_name.lower())))

    await bot.send_message(user_id, "Please select the date for the reminder:", reply_markup=markup)

#кнопки выбора даты задачи
@dp.callback_query_handler(task_cb.filter(action='set_date'))
async def process_date_selection(callback_query: types.CallbackQuery, callback_data: dict):
    user_id = callback_query.from_user.id
    action = callback_data['value']

    if action == 'today':
        selected_date = datetime.now()
    elif action == 'tomorrow':
        selected_date = datetime.now() + timedelta(days=1)
    elif action == 'custom':
        user_state[user_id]['state'] = 'awaiting_custom_date'
        await bot.send_message(user_id, "Please provide the custom date for the reminder (DD.MM.YYYY):")
        return
    else:
        weekdays = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
        today = datetime.now().weekday()
        day_diff = (weekdays[action] - today + 7) % 7
        selected_date = datetime.now() + timedelta(days=day_diff)

    user_state[user_id]['remind_at'] = selected_date.strftime('%Y-%m-%d')
    user_state[user_id]['state'] = 'awaiting_time_selection'

    await bot.send_message(user_id, "Please provide the time for the reminder (HH:MM):")

#на случай если пользователь хочет выбрать удаленную дату
@dp.message_handler(lambda message: user_state.get(message.from_user.id, {}).get('state') == 'awaiting_custom_date')
async def process_custom_date(message: types.Message):
    try:
        selected_date = datetime.strptime(message.text, '%d.%m.%Y')
        user_id = message.from_user.id
        user_state[user_id]['remind_at'] = selected_date.strftime('%Y-%m-%d')
        user_state[user_id]['state'] = 'awaiting_time_selection'
        await message.answer("Please provide the time for the reminder (HH:MM):")
    except ValueError:
        await message.answer("Invalid date format. Please provide the date in DD.MM.YYYY format.")

#выбор времени напоминания
@dp.message_handler(lambda message: user_state.get(message.from_user.id, {}).get('state') == 'awaiting_time_selection')
async def process_time_selection(message: types.Message):
    try:
        remind_at_time = datetime.strptime(message.text, '%H:%M').time()
        user_id = message.from_user.id
        remind_at_date = datetime.strptime(user_state[user_id]['remind_at'], '%Y-%m-%d').date()
        remind_at = datetime.combine(remind_at_date, remind_at_time)

        user_state[user_id]['remind_at'] = remind_at
        user_state[user_id]['state'] = 'awaiting_repeat_selection'
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("No Repeat", callback_data=task_cb.new(action='set_repeat', value='no_repeat')),
            InlineKeyboardButton("Everyday", callback_data=task_cb.new(action='set_repeat', value='everyday')),
            InlineKeyboardButton("Every Week", callback_data=task_cb.new(action='set_repeat', value='every_week')),
            InlineKeyboardButton("Every Month", callback_data=task_cb.new(action='set_repeat', value='every_month')),
            InlineKeyboardButton("Every Year", callback_data=task_cb.new(action='set_repeat', value='every_year'))
        )

        await message.answer("Would you like to set a repeat for this task?", reply_markup=markup)
    except ValueError:
        await message.answer("Invalid time format. Please provide the time in HH:MM format.")

@dp.callback_query_handler(task_cb.filter(action='set_repeat'))
async def process_repeat_selection(callback_query: types.CallbackQuery, callback_data: dict):
    user_id = callback_query.from_user.id
    repeat = callback_data['value']
    user_state[user_id]['repeat'] = repeat

    action = user_state[user_id]['action']
    if action == 'add':
        await save_task(user_id)
    elif action == 'edit':
        await update_task(user_id)


async def save_task(user_id):
    task_name = user_state[user_id]['task_name']
    remind_at = user_state[user_id]['remind_at']
    repeat_interval = user_state[user_id].get('repeat', 'no_repeat')

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tasks (user_id, task, remind_at, repeat_interval) VALUES (%s, %s, %s, %s)",
                (user_id, task_name, remind_at, repeat_interval)
            )
            conn.commit()
        await bot.send_message(user_id, "Task added.")
    except Exception as e:
        await bot.send_message(user_id, f"Failed to add task: {e}")
    finally:
        user_state.pop(user_id, None)

async def update_task(user_id):
    task_id = user_state[user_id]['task_id']
    task_name = user_state[user_id]['task_name']
    remind_at = user_state[user_id]['remind_at']
    repeat_interval = user_state[user_id].get('repeat', 'no_repeat')

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET task = %s, remind_at = %s, repeat_interval = %s WHERE id = %s",
                (task_name, remind_at, repeat_interval, task_id)
            )
            conn.commit()
        await bot.send_message(user_id, "Task edited.")
    except Exception as e:
        await bot.send_message(user_id, f"Failed to edit task: {e}")
    finally:
        user_state.pop(user_id, None)
#список доступных задач
@dp.message_handler(commands=['list'])
async def list_tasks(message: types.Message):
    user_id = message.from_user.id

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT task, remind_at, repeat_interval FROM tasks WHERE user_id = %s ORDER BY remind_at", (user_id,))
            rows = cursor.fetchall()

        if not rows:
            await message.answer("No tasks found.")
            return

        response = "Here are your tasks:\n"
        for index, row in enumerate(rows, start=1):
            remind_at_str = row[1].strftime('%Y-%m-%d %H:%M')
            task_info = f"{index}. {row[0]} at {remind_at_str}"
            if row[2] != 'no_repeat':
                task_info += f", Repeat: {row[2]}"
            response += task_info + "\n"

        await message.answer(response)
    except Exception as e:
        await message.answer(f"Failed to retrieve tasks: {e}")
#удаление задач
@dp.message_handler(commands=['delete'])
async def delete_task(message: types.Message):
    user_id = message.from_user.id

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, task, remind_at FROM tasks WHERE user_id = %s ORDER BY remind_at", (user_id,))
            rows = cursor.fetchall()

        if not rows:
            await message.answer("No tasks found to delete.")
            return

        markup = InlineKeyboardMarkup(row_width=1)
        for row in rows:
            task_button = InlineKeyboardButton(f"{row[1]} at {row[2]}", callback_data=task_cb.new(action='delete_task', value=row[0]))
            markup.add(task_button)
        await message.answer("Please select the task to delete:", reply_markup=markup)
    except Exception as e:
        await message.answer(f"Failed to retrieve tasks: {e}")


@dp.callback_query_handler(task_cb.filter(action='delete_task'))
async def process_delete_task(callback_query: types.CallbackQuery, callback_data: dict):
    user_id = callback_query.from_user.id
    task_id = callback_data['value']

    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            conn.commit()

        await bot.send_message(user_id, "Task deleted.")
    except Exception as e:
        await bot.send_message(user_id, f"Failed to delete task: {e}")

#для отправки уведомлений
async def send_notifications():
    while True:
        now = datetime.now()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, task, repeat_interval FROM tasks WHERE remind_at <= %s", (now,))
            rows = cursor.fetchall()

            for row in rows:
                user_id, task, repeat_interval = row
                await bot.send_message(user_id, f"Task reminder: {task}")

                if repeat_interval == 'no_repeat':
                    cursor.execute("DELETE FROM tasks WHERE user_id = %s AND task = %s", (user_id, task))
                else:
                    if repeat_interval == 'everyday':
                        new_remind_at = now + timedelta(days=1)
                    elif repeat_interval == 'every_week':
                        new_remind_at = now + timedelta(weeks=1)
                    elif repeat_interval == 'every_month':
                        new_remind_at = now + timedelta(days=30)
                    elif repeat_interval == 'every_year':
                        new_remind_at = now + timedelta(days=365)
                    else:
                        new_remind_at = now

                    cursor.execute("UPDATE tasks SET remind_at = %s WHERE user_id = %s AND task = %s", (new_remind_at, user_id, task))

                conn.commit()

        await asyncio.sleep(60)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(send_notifications())
    executor.start_polling(dp, skip_updates=True)
