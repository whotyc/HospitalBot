import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '6944366672:AAFEpkBSvudtB7Tij5Se7bn2-SpSrUmV9Zc'
bot = telebot.TeleBot(TOKEN)


def init_db():
    conn = sqlite3.connect('appointment_db.sqlite')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        district TEXT,
        room TEXT
    )
    ''')
    logger.info("Table 'doctors' created or already exists")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS time_slots (
        id INTEGER PRIMARY KEY,
        doctor_id INTEGER,
        day TEXT NOT NULL,
        time TEXT NOT NULL,
        is_available INTEGER DEFAULT 1,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id)
    )
    ''')
    logger.info("Table 'time_slots' created or already exists")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL,
        appointment_date TEXT NOT NULL,
        patient_name TEXT,
        patient_phone TEXT,
        address TEXT,
        symptoms TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id),
        FOREIGN KEY (slot_id) REFERENCES time_slots (id)
    )
    ''')
    logger.info("Table 'appointments' created or already exists")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        phone TEXT,
        address TEXT,
        last_visit TIMESTAMP
    )
    ''')
    logger.info("Table 'users' created or already exists")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS house_calls (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        patient_name TEXT,
        patient_phone TEXT,
        address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    logger.info("Table 'house_calls' created or already exists")

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        logger.info("Populating initial data for doctors")
        populate_initial_data(conn)

    conn.close()


def populate_initial_data(conn):
    cursor = conn.cursor()

    pediatricians = [
        (1, 'Хохлова О.В.', 'Педиатр', '7', '301'),
        (2, 'Баталова И.А.', 'Педиатр', '8', '302'),
        (3, 'Николаева Ю.С.', 'Педиатр', '12', '303'),
        (4, 'Осетрова К.А.', 'Педиатр', '13', '304'),
        (5, 'Ламбина Е.А.', 'Педиатр', '15', '305'),
        (6, 'Быков Е.В.', 'Педиатр', '15', '305'),
    ]

    specialists = [
        (7, 'Иванов А.П.', 'Аллерголог', None, '401'),
        (8, 'Петрова М.С.', 'Кардиолог', None, '402'),
        (9, 'Сидоров И.В.', 'ЛОР', None, '403'),
        (10, 'Кузнецова Е.А.', 'Пульмонолог', None, '404'),
        (11, 'Смирнов Д.Н.', 'Невролог', None, '405'),
        (12, 'Васильева О.И.', 'Гастроэнтеролог', None, '406'),
        (13, 'Морозова А.Е.', 'Дерматолог', None, '407'),
        (14, 'Волков С.Т.', 'Эндокринолог', None, '408'),
        (15, 'Зайцева Н.Ю.', 'Офтальмолог', None, '409'),
    ]

    cursor.executemany("INSERT INTO doctors (id, name, specialty, district, room) VALUES (?, ?, ?, ?, ?)",
                       pediatricians)
    cursor.executemany("INSERT INTO doctors (id, name, specialty, district, room) VALUES (?, ?, ?, ?, ?)", specialists)

    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']
    times = ['8:00', '9:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00']

    slot_id = 1
    time_slots = []

    for doctor_id in range(1, 16):
        for day in days:
            import random
            selected_times = random.sample(times, random.randint(4, 6))
            for time in selected_times:
                time_slots.append((slot_id, doctor_id, day, time))
                slot_id += 1

    cursor.executemany("INSERT INTO time_slots (id, doctor_id, day, time) VALUES (?, ?, ?, ?)", time_slots)
    conn.commit()


def get_db_connection():
    conn = sqlite3.connect('appointment_db.sqlite')
    conn.row_factory = sqlite3.Row
    return conn


def get_doctor_by_specialty(specialty):
    conn = get_db_connection()
    doctors = conn.execute('SELECT * FROM doctors WHERE specialty = ?', (specialty,)).fetchall()
    conn.close()
    return doctors


def get_doctors_by_district(district=None):
    conn = get_db_connection()
    if district:
        doctors = conn.execute('SELECT * FROM doctors WHERE district = ?', (district,)).fetchall()
    else:
        doctors = conn.execute('SELECT * FROM doctors WHERE specialty = "Педиатр"').fetchall()
    conn.close()
    return doctors


def get_available_slots(doctor_id):
    conn = get_db_connection()
    slots = conn.execute('''
    SELECT * FROM time_slots 
    WHERE doctor_id = ? AND is_available = 1
    ORDER BY 
        CASE 
            WHEN day = 'Понедельник' THEN 1
            WHEN day = 'Вторник' THEN 2
            WHEN day = 'Среда' THEN 3
            WHEN day = 'Четверг' THEN 4
            WHEN day = 'Пятница' THEN 5
        END,
        time
    ''', (doctor_id,)).fetchall()
    conn.close()
    return slots


def book_appointment(user_id, doctor_id, slot_id, patient_name=None, patient_phone=None, address=None, symptoms=None):
    conn = get_db_connection()

    today = datetime.now()
    slot = conn.execute('SELECT day FROM time_slots WHERE id = ?', (slot_id,)).fetchone()
    day_of_week = slot['day']

    days = {'Понедельник': 0, 'Вторник': 1, 'Среда': 2, 'Четверг': 3, 'Пятница': 4}
    today_weekday = today.weekday()
    days_until_appointment = (days[day_of_week] - today_weekday) % 7
    if days_until_appointment == 0:
        days_until_appointment = 7
    appointment_date = today + timedelta(days=days_until_appointment)
    appointment_date_str = appointment_date.strftime('%Y-%m-%d')

    conn.execute('UPDATE time_slots SET is_available = 0 WHERE id = ?', (slot_id,))

    conn.execute('''
    INSERT INTO appointments 
    (user_id, doctor_id, slot_id, appointment_date, patient_name, patient_phone, address, symptoms)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, doctor_id, slot_id, appointment_date_str, patient_name, patient_phone, address, symptoms))

    existing_user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if existing_user:
        conn.execute('''
        UPDATE users SET last_visit = CURRENT_TIMESTAMP
        WHERE user_id = ?
        ''', (user_id,))
    else:
        conn.execute('''
        INSERT INTO users (user_id, full_name, phone, address, last_visit)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, patient_name, patient_phone, address))

    conn.commit()

    doctor = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    time_slot = conn.execute('SELECT * FROM time_slots WHERE id = ?', (slot_id,)).fetchone()

    conn.close()

    return {
        'doctor_name': doctor['name'],
        'specialty': doctor['specialty'],
        'day': time_slot['day'],
        'time': time_slot['time'],
        'room': doctor['room'],
        'date': appointment_date_str
    }


def book_house_call(user_id, patient_name, patient_phone, address):
    conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO house_calls (user_id, patient_name, patient_phone, address)
    VALUES (?, ?, ?, ?)
    ''', (user_id, patient_name, patient_phone, address))

    existing_user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if existing_user:
        conn.execute('''
        UPDATE users SET last_visit = CURRENT_TIMESTAMP
        WHERE user_id = ?
        ''', (user_id,))
    else:
        conn.execute('''
        INSERT INTO users (user_id, full_name, phone, address, last_visit)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, patient_name, patient_phone, address))

    conn.commit()
    conn.close()

    return {
        'patient_name': patient_name,
        'patient_phone': patient_phone,
        'address': address,
        'created_at': datetime.now().strftime('%d.%m.%Y %H:%M')
    }


def get_user_appointments(user_id):
    conn = get_db_connection()
    appointments = conn.execute('''
    SELECT a.id, a.appointment_date, t.day, t.time, d.name, d.specialty, d.room
    FROM appointments a
    JOIN doctors d ON a.doctor_id = d.id
    JOIN time_slots t ON a.slot_id = t.id
    WHERE a.user_id = ?
    ORDER BY a.appointment_date DESC, t.time
    ''', (user_id,)).fetchall()

    house_calls = conn.execute('''
    SELECT id, created_at, patient_name, address
    FROM house_calls
    WHERE user_id = ?
    ORDER BY created_at DESC
    ''', (user_id,)).fetchall()

    conn.close()
    return appointments, house_calls


def get_user_info(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user


def update_user_info(user_id, name=None, phone=None, address=None):
    conn = get_db_connection()

    current_data = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    if current_data:
        update_fields = []
        params = []

        if name:
            update_fields.append("full_name = ?")
            params.append(name)
        if phone:
            update_fields.append("phone = ?")
            params.append(phone)
        if address:
            update_fields.append("address = ?")
            params.append(address)

        if update_fields:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
            params.append(user_id)
            conn.execute(query, params)
    else:
        conn.execute('''
        INSERT INTO users (user_id, full_name, phone, address, last_visit)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, name, phone, address))

    conn.commit()
    conn.close()


user_states = {}
user_temp_data = {}


class States:
    START = 'start'
    FEVER_CHOICE = 'fever_choice'
    SPECIALIST_CHOICE = 'specialist_choice'
    PEDIATR_PURPOSE = 'pediatr_purpose'
    SPECIALIST_PURPOSE = 'specialist_purpose'
    DISTRICT_CHOICE = 'district_choice'
    TIME_SELECTION = 'time_selection'
    WAITING_ADDRESS = 'waiting_address'
    WAITING_NAME = 'waiting_name'
    WAITING_PHONE = 'waiting_phone'
    WAITING_SYMPTOMS = 'waiting_symptoms'
    PROFILE_MENU = 'profile_menu'
    EDIT_PROFILE = 'edit_profile'


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_states[user_id] = States.START
    user_temp_data[user_id] = {}
    logger.info(f"User {user_id} started bot, state: {user_states[user_id]}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("Запись к врачу")
    btn2 = types.KeyboardButton("Мои записи")
    btn3 = types.KeyboardButton("Мой профиль")
    btn4 = types.KeyboardButton("Информация о клинике")
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(message.chat.id,
                     "Здравствуйте! Я бот для записи к необходимому врачу в детской поликлинике. "
                     "Выберите нужный вам раздел:", reply_markup=markup)


@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
*Помощь по использованию бота*

Основные команды:
/start - Начать работу с ботом
/help - Показать это сообщение
/profile - Управление личными данными
/appointments - Посмотреть ваши записи к врачам

*Как записаться к врачу:*
1. Нажмите "Запись к врачу"
2. Ответьте на вопрос о температуре
3. Выберите нужного специалиста
4. Выберите удобное время приема
5. Подтвердите запись

*Режим работы поликлиники:*
Пн-Пт: 8:00 - 20:00
Сб: 9:00 - 15:00
Вс: выходной

Контактный телефон: +7 (XXX) XXX-XX-XX
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['profile'])
def profile_command(message):
    show_profile(message)


@bot.message_handler(commands=['appointments'])
def appointments_command(message):
    show_appointments(message)


@bot.message_handler(func=lambda message: message.text == "Запись к врачу")
def start_appointment(message):
    user_id = message.from_user.id
    user_states[user_id] = States.FEVER_CHOICE
    user_temp_data[user_id] = {}
    logger.info(f"User {user_id} started appointment process, state: {user_states[user_id]}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("Да")
    btn2 = types.KeyboardButton("Нет")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Пожалуйста, ответьте на несколько вопросов. \n"
                                      "У вас повышенная температура тела?", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Мои записи")
def show_appointments(message):
    user_id = message.from_user.id
    appointments, house_calls = get_user_appointments(user_id)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Назад в меню"))

    if not appointments and not house_calls:
        bot.send_message(message.chat.id, "У вас пока нет активных записей или вызовов врача на дом.",
                         reply_markup=markup)
        return

    result = "Ваши записи и вызовы:\n\n"

    if appointments:
        result += "*Записи к врачам:*\n\n"
        for app in appointments:
            day_str = app['day']
            date_obj = datetime.strptime(app['appointment_date'], '%Y-%m-%d')
            date_str = date_obj.strftime('%d.%m.%Y')

            result += f"🗓 *{day_str}, {date_str} в {app['time']}*\n"
            result += f"👨‍⚕️ {app['name']} ({app['specialty']})\n"
            result += f"🏥 Кабинет {app['room']}\n\n"

    if house_calls:
        result += "*Вызовы врача на дом:*\n\n"
        for call in house_calls:
            created_at = datetime.strptime(call['created_at'], '%Y-%m-%d %H:%M:%S')
            created_at_str = created_at.strftime('%d.%m.%Y %H:%M')

            result += f"🕒 *Оформлен: {created_at_str}*\n"
            result += f"👤 Пациент: {call['patient_name']}\n"
            result += f"🏠 Адрес: {call['address']}\n\n"

    bot.send_message(message.chat.id, result, parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Мой профиль")
def show_profile(message):
    user_id = message.from_user.id
    user_states[user_id] = States.PROFILE_MENU
    user_data = get_user_info(user_id)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn1 = types.KeyboardButton("Редактировать данные")
    btn2 = types.KeyboardButton("Назад в меню")
    markup.add(btn1, btn2)

    if user_data:
        profile_text = "*Ваш профиль:*\n\n"
        profile_text += f"👤 ФИО: {user_data['full_name'] or 'Не указано'}\n"
        profile_text += f"📱 Телефон: {user_data['phone'] or 'Не указано'}\n"
        profile_text += f"🏠 Адрес: {user_data['address'] or 'Не указано'}\n"

        last_visit = user_data['last_visit']
        if last_visit:
            last_visit_date = datetime.strptime(last_visit, '%Y-%m-%d %H:%M:%S')
            profile_text += f"🕒 Последнее обновление: {last_visit_date.strftime('%d.%m.%Y')}"
    else:
        profile_text = "Ваш профиль пока не заполнен. Вы можете добавить свои данные, нажав кнопку ниже."

    bot.send_message(message.chat.id, profile_text, parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Информация о клинике")
def clinic_info(message):
    info_text = """
*Детская поликлиника №1*

🏥 *Адрес:* ул. Примерная, д. 123

⏰ *Режим работы:*
   Пн-Пт: 8:00 - 20:00
   Сб: 9:00 - 15:00
   Вс: выходной

📞 *Регистратура:* +7 (XXX) XXX-XX-XX

🚑 *Вызов врача на дом:* +7 (XXX) XXX-XX-XX
   Ежедневно с 8:00 до 14:00

⚠️ *Кабинет неотложной помощи:*
   Кабинет №101, 1 этаж
   Время работы: 8:00 - 19:00 без записи

🌡 *Кабинет для температурящих больных:*
   Кабинет №102, 1 этаж (отдельный вход)
   Время работы: 8:00 - 19:00 без записи

🔬 *Лаборатория (анализы):*
   Кабинет №201, 2 этаж
   Пн-Пт: 8:00 - 11:00

💉 *Процедурный кабинет:*
   Кабинет №202, 2 этаж
   Пн-Пт: 8:00 - 15:00
    """

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Назад в меню"))

    bot.send_message(message.chat.id, info_text, parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Назад в меню")
def back_to_menu(message):
    start_command(message)


@bot.message_handler(func=lambda message: message.text == "Редактировать данные")
def edit_profile(message):
    user_id = message.from_user.id
    user_states[user_id] = States.EDIT_PROFILE
    user_temp_data[user_id] = {}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Отмена"))

    bot.send_message(message.chat.id, "Пожалуйста, введите ваше ФИО:", reply_markup=markup)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.FEVER_CHOICE)
def handle_fever_choice(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Да":
        user_states[user_id] = 'temperature_choice'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn1 = types.KeyboardButton("Самостоятельное посещение")
        btn2 = types.KeyboardButton("Вызов врача на дом")
        btn3 = types.KeyboardButton("Назад в меню")
        markup.add(btn1, btn2, btn3)

        bot.send_message(message.chat.id,
                         "Вам необходимо посетить кабинет температурящих или вызвать педиатра на дом.",
                         reply_markup=markup)

    elif text == "Нет":
        user_states[user_id] = States.SPECIALIST_CHOICE
        user_temp_data[user_id] = {}

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton("Педиатр")
        btn2 = types.KeyboardButton("Узкий специалист")
        btn3 = types.KeyboardButton("Назад в меню")
        markup.add(btn1, btn2, btn3)

        bot.send_message(message.chat.id, "Какого специалиста вам нужно посетить?", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Самостоятельное посещение")
def handle_self_visit(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_temp_data:
        del user_temp_data[user_id]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Назад в меню"))

    bot.send_message(message.chat.id,
                     "Кабинет температурящих больных находится на 1 этаже, кабинет №102 (отдельный вход). "
                     "Время работы: с 8:00 до 19:00. Запись не требуется.",
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Вызов врача на дом")
def handle_house_call(message):
    user_id = message.from_user.id
    user_states[user_id] = States.WAITING_ADDRESS
    user_temp_data[user_id] = {}
    logger.info(f"User {user_id} started house call process, state: {user_states[user_id]}")

    user_data = get_user_info(user_id)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Отмена"))

    if user_data and user_data['address']:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn_address = types.KeyboardButton(user_data['address'])
        btn_cancel = types.KeyboardButton("Отмена")
        markup.add(btn_address, btn_cancel)

        bot.send_message(message.chat.id,
                         f"У нас сохранен ваш адрес: {user_data['address']}.\n"
                         "Вы можете использовать его или ввести новый адрес:",
                         reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, введите ваш точный адрес:", reply_markup=markup)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.SPECIALIST_CHOICE)
def handle_specialist_choice(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Педиатр":
        user_states[user_id] = States.PEDIATR_PURPOSE
        user_temp_data[user_id] = {'specialist': "Педиатр"}

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn1 = types.KeyboardButton("Первичное обращение по заболеванию")
        btn2 = types.KeyboardButton("Продление больничного листа")
        btn3 = types.KeyboardButton("Профилактический осмотр")
        btn4 = types.KeyboardButton("Назад")
        markup.add(btn1, btn2, btn3, btn4)

        bot.send_message(message.chat.id, "С какой целью Вы собираетесь посетить педиатра?", reply_markup=markup)

    elif text == "Узкий специалист":
        user_states[user_id] = States.SPECIALIST_PURPOSE
        user_temp_data[user_id] = {'specialist': text}

        conn = get_db_connection()
        specialists = conn.execute('''
        SELECT DISTINCT specialty FROM doctors 
        WHERE specialty != "Педиатр"
        ORDER BY specialty
        ''').fetchall()
        conn.close()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        for spec in specialists:
            markup.add(types.KeyboardButton(spec['specialty']))

        markup.add(types.KeyboardButton("Назад"))

        bot.send_message(message.chat.id, "Выберите необходимого специалиста:", reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.PEDIATR_PURPOSE)
def handle_pediatr_purpose(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Назад":
        user_states[user_id] = States.SPECIALIST_CHOICE
        user_temp_data[user_id] = {}

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton("Педиатр")
        btn2 = types.KeyboardButton("Узкий специалист")
        btn3 = types.KeyboardButton("Назад в меню")
        markup.add(btn1, btn2, btn3)

        bot.send_message(message.chat.id, "Какого специалиста вам нужно посетить?", reply_markup=markup)
        return

    if text == "Продление больничного листа":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("Вернуться к выбору врача"), types.KeyboardButton("Назад в меню"))

        bot.send_message(message.chat.id,
                         "Для продления больничного листа можно посетить любого работающего в удобный Вам день педиатра. "
                         "Приходите в рабочее время с 10:00 до 12:00 или с 15:00 до 17:00 без записи.",
                         reply_markup=markup)
        return

    user_states[user_id] = States.DISTRICT_CHOICE
    user_temp_data[user_id]['purpose'] = text

    conn = get_db_connection()
    districts = conn.execute('''
    SELECT DISTINCT district FROM doctors 
    WHERE specialty = "Педиатр" AND district IS NOT NULL
    ORDER BY district
    ''').fetchall()
    conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)

    for district in districts:
        markup.add(types.KeyboardButton(f"Участок {district['district']}"))

    markup.add(types.KeyboardButton("Любой участок"))
    markup.add(types.KeyboardButton("Назад"))

    bot.send_message(message.chat.id, "Выберите ваш участок:", reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.SPECIALIST_PURPOSE)
def handle_specialist_purpose(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Назад":
        user_states[user_id] = States.SPECIALIST_CHOICE
        user_temp_data[user_id] = {}

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton("Педиатр")
        btn2 = types.KeyboardButton("Узкий специалист")
        btn3 = types.KeyboardButton("Назад в меню")
        markup.add(btn1, btn2, btn3)

        bot.send_message(message.chat.id, "Какого специалиста вам нужно посетить?", reply_markup=markup)
        return

    user_states[user_id] = States.TIME_SELECTION
    user_temp_data[user_id]['specialty'] = text

    conn = get_db_connection()
    doctor = conn.execute('SELECT * FROM doctors WHERE specialty = ? LIMIT 1', (text,)).fetchone()
    conn.close()

    if not doctor:
        bot.send_message(message.chat.id, "Врач данной специальности не найден. Попробуйте позже.")
        return

    user_temp_data[user_id]['doctor_id'] = doctor['id']
    user_temp_data[user_id]['doctor_name'] = doctor['name']

    slots = get_available_slots(doctor['id'])

    if not slots:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("Назад"))

        bot.send_message(message.chat.id,
                         f"К сожалению, у {doctor['name']} нет доступных слотов для записи. "
                         "Пожалуйста, выберите другого врача.",
                         reply_markup=markup)
        return

    slots_by_day = {}
    for slot in slots:
        day = slot['day']
        if day not in slots_by_day:
            slots_by_day[day] = []
        slots_by_day[day].append(slot)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    days_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']

    for day in days_order:
        if day in slots_by_day:
            for slot in slots_by_day[day]:
                markup.add(types.KeyboardButton(f"Время: {day}, {slot['time']}, ID:{slot['id']}"))

    markup.add(types.KeyboardButton("Назад"))

    bot.send_message(message.chat.id,
                     f"Выберите удобное время для приема у врача {doctor['name']} ({doctor['specialty']}):",
                     reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.DISTRICT_CHOICE)
def handle_district_choice(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Назад":
        user_states[user_id] = States.PEDIATR_PURPOSE
        user_temp_data[user_id] = {}

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn1 = types.KeyboardButton("Первичное обращение по заболеванию")
        btn2 = types.KeyboardButton("Продление больничного листа")
        btn3 = types.KeyboardButton("Профилактический осмотр")
        btn4 = types.KeyboardButton("Назад")
        markup.add(btn1, btn2, btn3, btn4)

        bot.send_message(message.chat.id, "С какой целью Вы собираетесь посетить педиатра?", reply_markup=markup)
        return

    district = None
    if text.startswith("Участок "):
        district = text.replace("Участок ", "")

    doctors = get_doctors_by_district(district)

    if not doctors:
        bot.send_message(message.chat.id,
                         "К сожалению, по данному участку нет доступных врачей. Попробуйте выбрать другой участок.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    for doctor in doctors:
        markup.add(types.KeyboardButton(f"{doctor['name']} - Участок {doctor['district'] or 'Не указан'}"))

    markup.add(types.KeyboardButton("Назад"))

    user_states[user_id] = States.TIME_SELECTION
    bot.send_message(message.chat.id, "Выберите врача:", reply_markup=markup)


@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id) == States.TIME_SELECTION and message.text == "Назад")
def back_to_district(message):
    user_id = message.from_user.id
    user_states[user_id] = States.DISTRICT_CHOICE
    user_temp_data[user_id] = {}

    conn = get_db_connection()
    districts = conn.execute('''
        SELECT DISTINCT district FROM doctors 
        WHERE specialty = "Педиатр" AND district IS NOT NULL
        ORDER BY district
        ''').fetchall()
    conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)

    for district in districts:
        markup.add(types.KeyboardButton(f"Участок {district['district']}"))

    markup.add(types.KeyboardButton("Любой участок"))
    markup.add(types.KeyboardButton("Назад"))

    bot.send_message(message.chat.id, "Выберите ваш участок:", reply_markup=markup)


@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id) == States.TIME_SELECTION and not message.text.startswith(
        "Время:"))
def handle_doctor_selection(message):
    user_id = message.from_user.id
    text = message.text

    doctor_name = text.split(" - ")[0]

    conn = get_db_connection()
    doctor = conn.execute('SELECT * FROM doctors WHERE name = ?', (doctor_name,)).fetchone()
    conn.close()

    if not doctor:
        bot.send_message(message.chat.id, "Врач не найден. Пожалуйста, выберите врача из списка.")
        return

    user_temp_data[user_id]['doctor_id'] = doctor['id']
    user_temp_data[user_id]['doctor_name'] = doctor['name']

    slots = get_available_slots(doctor['id'])

    if not slots:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("Назад"))

        bot.send_message(message.chat.id,
                         f"К сожалению, у {doctor['name']} нет доступных слотов для записи. "
                         "Пожалуйста, выберите другого врача.",
                         reply_markup=markup)
        return

    slots_by_day = {}
    for slot in slots:
        day = slot['day']
        if day not in slots_by_day:
            slots_by_day[day] = []
        slots_by_day[day].append(slot)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    days_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']

    for day in days_order:
        if day in slots_by_day:
            for slot in slots_by_day[day]:
                markup.add(types.KeyboardButton(f"Время: {day}, {slot['time']}, ID:{slot['id']}"))

    markup.add(types.KeyboardButton("Назад"))

    bot.send_message(message.chat.id,
                     f"Выберите удобное время для приема у врача {doctor['name']} ({doctor['specialty']}):",
                     reply_markup=markup)


@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id) == States.TIME_SELECTION and message.text.startswith(
        "Время:"))
def handle_time_selection(message):
    user_id = message.from_user.id
    text = message.text

    try:
        slot_id = int(text.split("ID:")[1])
        user_temp_data[user_id]['slot_id'] = slot_id
        logger.info(f"User {user_id} selected slot_id: {slot_id}, user_temp_data: {user_temp_data[user_id]}")
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing slot_id for user {user_id}: {e}")
        bot.send_message(message.chat.id, "Ошибка: неверный формат времени. Пожалуйста, выберите время из списка.")
        return

    user_data = get_user_info(user_id)

    if user_data and user_data['full_name'] and user_data['phone']:
        confirm_appointment(message.chat.id, user_id, user_data['full_name'], user_data['phone'])
    else:
        user_states[user_id] = States.WAITING_NAME

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("Отмена"))

        bot.send_message(message.chat.id, "Пожалуйста, введите ФИО пациента:", reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.WAITING_NAME)
def handle_name_input(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        start_command(message)
        return

    user_temp_data[user_id]['patient_name'] = text
    user_states[user_id] = States.WAITING_PHONE
    logger.info(f"User {user_id} entered name: {text}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Отмена"))

    bot.send_message(message.chat.id, "Пожалуйста, введите номер телефона для связи:", reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.WAITING_PHONE)
def handle_phone_input(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        start_command(message)
        return

    user_temp_data[user_id]['patient_phone'] = text
    logger.info(f"User {user_id} entered phone: {text}")

    if user_states[user_id] == States.WAITING_PHONE and 'address' in user_temp_data[user_id]:
        user_data = get_user_info(user_id)
        confirm_house_call(message.chat.id, user_id,
                           user_temp_data[user_id].get('patient_name', user_data['full_name']),
                           text, user_temp_data[user_id]['address'])
    else:
        if user_temp_data[user_id].get('specialist') in ["Педиатр", None] and user_temp_data[user_id].get(
                'purpose') == "Первичное обращение по заболеванию":
            user_states[user_id] = States.WAITING_SYMPTOMS

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
            markup.add(types.KeyboardButton("Отмена"))

            bot.send_message(message.chat.id, "Кратко опишите симптомы заболевания:", reply_markup=markup)
        else:
            confirm_appointment(message.chat.id, user_id, user_temp_data[user_id]['patient_name'], text)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.WAITING_SYMPTOMS)
def handle_symptoms_input(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        start_command(message)
        return

    user_temp_data[user_id]['symptoms'] = text
    logger.info(f"User {user_id} entered symptoms: {text}")

    confirm_appointment(message.chat.id, user_id, user_temp_data[user_id]['patient_name'],
                        user_temp_data[user_id]['patient_phone'], symptoms=text)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.WAITING_ADDRESS)
def handle_address_input(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        start_command(message)
        return

    user_temp_data[user_id]['address'] = text
    logger.info(f"User {user_id} entered address: {text}")
    update_user_info(user_id, address=text)

    user_data = get_user_info(user_id)

    if user_data and user_data['full_name'] and user_data['phone']:
        confirm_house_call(message.chat.id, user_id, user_data['full_name'], user_data['phone'], text)
    else:
        user_states[user_id] = States.WAITING_NAME

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(types.KeyboardButton("Отмена"))

        bot.send_message(message.chat.id, "Пожалуйста, введите ФИО пациента:", reply_markup=markup)


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == States.EDIT_PROFILE)
def handle_edit_name(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        show_profile(message)
        return

    user_temp_data[user_id] = {'name': text}
    logger.info(f"User {user_id} entered name for edit: {text}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Отмена"))

    bot.send_message(message.chat.id, "Введите ваш номер телефона:", reply_markup=markup)

    user_states[user_id] = 'edit_phone'


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == 'edit_phone')
def handle_edit_phone(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        show_profile(message)
        return

    user_temp_data[user_id]['phone'] = text
    logger.info(f"User {user_id} entered phone for edit: {text}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Отмена"))

    bot.send_message(message.chat.id, "Введите ваш адрес:", reply_markup=markup)

    user_states[user_id] = 'edit_address'


@bot.message_handler(func=lambda message: get_user_state(message.from_user.id) == 'edit_address')
def handle_edit_address(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Отмена":
        show_profile(message)
        return

    update_user_info(
        user_id,
        name=user_temp_data[user_id]['name'],
        phone=user_temp_data[user_id]['phone'],
        address=text
    )
    logger.info(f"User {user_id} updated profile: {user_temp_data[user_id]}")

    bot.send_message(message.chat.id, "Ваш профиль успешно обновлен!")

    show_profile(message)


def get_user_state(user_id):
    return user_states.get(user_id, States.START)


def confirm_appointment(chat_id, user_id, patient_name, patient_phone, symptoms=None):
    if not isinstance(chat_id, int) or not isinstance(user_id, int):
        raise ValueError("Invalid chat_id or user_id type")
    if 'address' in user_temp_data[user_id]:
        logger.warning(f"Redirecting to confirm_house_call for user {user_id} due to address in user_temp_data")
        confirm_house_call(chat_id, user_id, patient_name, patient_phone, user_temp_data[user_id]['address'])
        return

    try:
        doctor_id = user_temp_data[user_id].get('doctor_id')
        slot_id = user_temp_data[user_id].get('slot_id')

        if not doctor_id or not slot_id:
            raise ValueError("Doctor ID or Slot ID is missing in user_temp_data")

        update_user_info(user_id, name=patient_name, phone=patient_phone)

        appointment_info = book_appointment(
            user_id,
            doctor_id,
            slot_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            symptoms=symptoms
        )

        message = f"*Ваша запись успешно оформлена!*\n\n"
        message += f"👨‍⚕️ Врач: {appointment_info['doctor_name']} ({appointment_info['specialty']})\n"
        message += f"🗓 День: {appointment_info['day']}\n"
        message += f"🕒 Время: {appointment_info['time']}\n"
        message += f"📅 Дата: {appointment_info['date']}\n"
        message += f"🏥 Кабинет: {appointment_info['room']}\n\n"

        if symptoms:
            message += f"🤒 Указанные симптомы: {symptoms}\n\n"

        message += "Пожалуйста, приходите за 15 минут до назначенного времени. При себе имейте полис ОМС и паспорт."

        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_temp_data:
            del user_temp_data[user_id]

    except Exception as e:
        logger.error(f"Error in confirm_appointment for user {user_id}: {e}")
        message = f"Ошибка при оформлении записи: {str(e)}. Попробуйте снова."

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Назад в меню"))

    bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=markup)


def confirm_house_call(chat_id, user_id, patient_name, patient_phone, address):
    try:
        logger.info(f"Confirming house call for user {user_id}, data: {patient_name}, {patient_phone}, {address}")
        house_call_info = book_house_call(user_id, patient_name, patient_phone, address)

        message = f"*Вызов врача на дом успешно оформлен*\n\n"
        message += f"👤 Пациент: {house_call_info['patient_name']}\n"
        message += f"📱 Телефон: {house_call_info['patient_phone']}\n"
        message += f"🏠 Адрес: {house_call_info['address']}\n"
        message += f"🕒 Время оформления: {house_call_info['created_at']}\n\n"
        message += "Врач свяжется с вами в ближайшее время для уточнения информации."

        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_temp_data:
            del user_temp_data[user_id]

    except Exception as e:
        logger.error(f"Error in confirm_house_call for user {user_id}: {e}")
        message = f"Ошибка при оформлении вызова: {str(e)}. Попробуйте снова."

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("Назад в меню"))

    bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def default_handler(message):
    if message.from_user.id in user_states and user_states[message.from_user.id] in [States.EDIT_PROFILE, 'edit_phone',
                                                                                     'edit_address']:
        return

    if message.from_user.id in user_states and user_states[message.from_user.id] in [
        States.WAITING_NAME, States.WAITING_PHONE, States.WAITING_ADDRESS, States.WAITING_SYMPTOMS
    ]:
        return

    start_command(message)


if __name__ == '__main__':
    init_db()
    bot.polling(none_stop=True)
