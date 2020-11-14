import telebot
import sqlite3
import os


TOKEN = '1257721055:AAEuBf8GWu4_3XIteYpKrjgB9Gw1LzAGtkI'

bot = telebot.TeleBot(TOKEN)

DATA_BASE_NAME = 'tasks_db'

# Класс управления базой данных
class DBManager:
    def __init__(self):
        """Если базы данных не существует, её следует создать
             task_id - идентификатор задачи
             user_id - идентификатор пользователя
             text - текст задачи
             photo - прикреплённое изображение в формате blob"""
        if not os.path.isfile(DATA_BASE_NAME):
            conn = sqlite3.connect(DATA_BASE_NAME)
            cursor = conn.cursor()
            cursor.execute("""CREATE TABLE "tasks" ( 
                                "task_id"	INTEGER NOT NULL UNIQUE,
                                "user_id"	INTEGER NOT NULL,
                                "text"	TEXT NOT NULL,
                                "photo"	BLOB,
                                PRIMARY KEY("task_id")
                            );""")
            conn.commit()
            conn.close()

    def add_task_user(self, user_id, task_text, photo=None):
        """Добавляем задачу в базу данных"""
        conn = sqlite3.connect(DATA_BASE_NAME)
        cursor = conn.cursor()

        # определяем id задачи
        cursor.execute("SELECT MAX(task_id) FROM tasks")
        results = cursor.fetchone()[0]
        if results is None:
            task_id = 1
        else:
            task_id = int(results) + 1

        if photo:
            # если в запросе есть фото, до добавляем его в базу
            file_id = photo.file_id
            file_path = bot.get_file(file_id).file_path
            downloaded_file = bot.download_file(file_path)

            params = (task_id, user_id, task_text, downloaded_file)
            cursor.execute("INSERT INTO tasks (task_id, user_id, text, photo) VALUES (?, ?, ?, ?)", params)

        else:
            # иначе не выпендриваемся и записываем в базу только текст
            params = (task_id, user_id, task_text)
            cursor.execute("INSERT INTO tasks (task_id, user_id, text) VALUES (?, ?, ?)", params)

        conn.commit()
        conn.close()

    def delete_task_by_id(self, task_id, user_id):
        """Удаление задачи по id"""
        conn = sqlite3.connect(DATA_BASE_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id=? AND user_id=?", (str(task_id), str(user_id),))
        conn.commit()
        conn.close()

    def get_all_tasks(self, user_id):
        """Получаем ответ на запрос, содержащий список всех задач"""
        conn = sqlite3.connect(DATA_BASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE user_id=?", (str(user_id),))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_task(self, task_id, user_id):
        """Запрашиваем задачу из базы"""
        conn = sqlite3.connect(DATA_BASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id=? AND user_id=?", (str(task_id), str(user_id),))
        results = cursor.fetchall()
        conn.close()
        return results


# Создаём объект управляющего класса
db_manager = DBManager()

"""Методы-обёртки над методами класса-менеджера базы данных"""


def add_task(message):
    user_id = message.from_user.id
    task_text = message.text
    if task_text is None:
        bot.send_message(message.chat.id, "Ошибка: передано пустое текстовое поле")
    else:
        db_manager.add_task_user(user_id, task_text)
        bot.send_message(message.chat.id, "Задача сохранена!")


def add_photo_task(message):
    user_id = message.from_user.id
    task_text = message.caption
    photo = message.photo[-1]
    if task_text is None:
        bot.send_message(message.chat.id, "Пожалуйста, начните заново и добавьте к картинке описание")
    else:
        db_manager.add_task_user(user_id, task_text, photo)
        bot.send_message(message.chat.id, "Задача сохранена!")


def proceeded_db_list(task_list):
    """Причёсываем вывод списка заданий из базы данных"""
    output_info = "ID\tText\tPhoto\n"
    for task in task_list:
        output_info += str(task[0]) + "\t" + str(task[2][:20]) + "\t"
        if task[3] is None:
            output_info += "No" + "\n"
        else:
            output_info += "Yes" + "\n"
    return output_info


def select_task(message):
    task_db = db_manager.get_task(message.text, message.from_user.id)
    if task_db == []:
        bot.send_message(message.chat.id, 'Такой задачи нету. И это замечательно:)')
    else:
        task = task_db[0] # извлекаем кортеж из ответа базы данных
        bot.send_message(message.chat.id, str(task[2]))
        if task[3] is not None:
            bot.send_photo(message.chat.id, task[3])


def delete_task(message):
    db_manager.delete_task_by_id(message.text, message.from_user.id)
    bot.send_message(message.chat.id, 'Удаление выполнено!')


@bot.message_handler(commands=['start', 'help'])
def start_help_handler(message):
    """Создаём клавиатуру, которая будет вызываться командами start и help"""
    bot.send_message(message.from_user.id,  "Привет, это мини-органайзер. Добавь сюда задания, и удаляй выполненные")
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton('Добавить (без фото)', callback_data='add-new-item'),
        telebot.types.InlineKeyboardButton('Добавить (c фото)', callback_data='add-new-photo-item'),
    )
    keyboard.row(
        telebot.types.InlineKeyboardButton('Список дел', callback_data='show-items'),
        telebot.types.InlineKeyboardButton('Удалить', callback_data='delete-item'),
    )
    keyboard.row(
        telebot.types.InlineKeyboardButton('Посмотреть задачу', callback_data='show-item-detailed'),
    )
    bot.send_message(
        message.chat.id,
        'Что вы хотите сделать?',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call:True)
def iq_callback(query):
    """Функция-обработчик нажатий на кнопки клавиатуры"""
    data = query.data
    if data == 'add-new-item':
        msg = bot.send_message(query.message.chat.id, 'Напишите задание')
        bot.register_next_step_handler(msg, add_task)
    elif data == 'add-new-photo-item':
        msg = bot.send_message(query.message.chat.id, 'Загрузите картинку с задачей в описании')
        bot.register_next_step_handler(msg, add_photo_task)
    elif data == 'show-items':
        output_info = proceeded_db_list(db_manager.get_all_tasks(query.from_user.id))
        msg = bot.send_message(query.message.chat.id, output_info)
    elif data == 'show-item-detailed':
        msg = bot.send_message(query.message.chat.id, 'Введите номер задачи')
        bot.register_next_step_handler(msg, select_task)
    elif data == 'delete-item':
        msg = bot.send_message(query.message.chat.id, 'Введите номер удаляемой задачи')
        bot.register_next_step_handler(msg, delete_task)


@bot.message_handler(content_types=['text'])
def text_handler(message):
    """Внеконтестные сообщения с текстом автоматически распознаются как
     новое задание"""
    add_task(message)


@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    """Внеконтестные фото с описаниями автоматически распознаются как
     новое задание"""
    add_photo_task(message)


@bot.message_handler(func=lambda m: True)
def all_handler(message):
    """Все остальные сообщения будут попадать в эту функцию"""
    bot.send_message(message.from_user.id, "Эт чё такое?")


# Запуск бота
bot.polling(none_stop=True, interval=0, timeout=20)
