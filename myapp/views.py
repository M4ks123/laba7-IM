import json
import requests
import pymysql
import qrcode
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from myapp.credentials import TELEGRAM_API_URL, URL, HOSTDB, DBNAME, PORTDB, USERDB, PASSDB, TIMEOUT

timeout = TIMEOUT

# Встановлення з'єднання з базою даних
connection = pymysql.connect(
    charset="utf8mb4",
    connect_timeout=timeout,
    cursorclass=pymysql.cursors.DictCursor,
    db=DBNAME,
    host=HOSTDB,
    password=PASSDB,
    read_timeout=timeout,
    port=PORTDB,
    user=USERDB,
    write_timeout=timeout,
)


@csrf_exempt
def setwebhook(request):
    response = requests.post(TELEGRAM_API_URL + "setWebhook?url=" + URL).json()
    return HttpResponse(f"{response}")


@csrf_exempt
def telegram_bot(request):
    if request.method == 'POST':
        update = json.loads(request.body.decode('utf-8'))
        handle_update(update)
        return HttpResponse('ok')
    else:
        return HttpResponseBadRequest('Bad Request')


def handle_update(update):
    chat_id = None

    try:
        if 'message' in update and 'chat' in update['message'] and 'id' in update['message']['chat']:
            chat_id = update['message']['chat']['id']
            telegram_id = update['message']['from']['id']
            text = update['message'].get('text', '')

            if text == '/registr':
                send_message("sendMessage", {
                    'chat_id': chat_id,
                    'text': 'Please send your contact:',
                    'reply_markup': {
                        'keyboard': [
                            [
                                {
                                    'text': 'My phone',
                                    'request_contact': True
                                }
                            ]
                        ],
                        'resize_keyboard': True,
                        'one_time_keyboard': True,

                    }
                })
            elif text == '/getmyid':
                user_id = telegram_id
                qr_data = str(user_id)
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=8,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save("user_qr.png")
                photo = open('user_qr.png', 'rb')
                caption = f"Your ID: {user_id}"
                send_document("sendDocument", chat_id, photo, caption)
            elif text == '/deleteprofile':

                if check_user_existence_by_telegram_id(telegram_id):
                    send_message("sendMessage", {
                        'chat_id': chat_id,
                        'text': 'Ви впевнені що хочете видалити свій профіль?',
                        'reply_markup': {
                            'inline_keyboard': [
                                [{'text': 'Так', 'callback_data': 'delete_yes'}, {'text': 'НІІІІІІІІ', 'callback_data': 'delete_no'}]
                            ]
                        }
                    })
                else:
                    send_message("sendMessage", {
                        'chat_id': chat_id,
                        'text': 'Ваш профіль не знайдено. Спочатку зареєструйтеся, щоб видалити профіль.'
                    })
            elif 'contact' in update['message']:
                contact = update['message']['contact']
                phone_number = contact.get('phone_number', 'Номер телефону відсутній')
                name = contact.get('first_name', 'Ім\'я відсутнє')
                last_name = contact.get('last_name', 'Прізвище відсутнє')

                user_id = check_user_existence(phone_number)

                if user_id:
                    user_info = f'Користувач з номером телефону {phone_number} вже існує.\nID користувача: {user_id}'
                else:
                    user_id = save_user_data(telegram_id, phone_number, name, last_name)
                    user_info = f'Ви успішно зареєструвалися.\nID користувача: {user_id}\nТелефон: {phone_number}\nІм\'я: {name}\nПрізвище: {last_name}'

                send_message("sendMessage", {
                    'chat_id': chat_id,
                    'text': user_info,
                    'reply_markup': {
                        'remove_keyboard': True,
                    }
                })

        elif 'callback_query' in update:
            callback_query = update['callback_query']
            data = callback_query.get('data')
            message = callback_query['message']
            chat_id = message['chat']['id']

            if data == 'delete_yes':
               
                delete_user_data(chat_id)
                send_message("sendMessage", {'chat_id': chat_id, 'text': 'Ваш профіль успішно видалено.'})
            elif data == 'delete_no':
                send_message("sendMessage", {'chat_id': chat_id, 'text': 'Операція видалення профілю скасована.'})

    except Exception as e:
        if chat_id is not None:
            send_message("sendMessage", {
                'chat_id': chat_id,
                'text': 'Щось пішло не так. Спробуйте ще раз.'
            })
        else:
            print("Помилка обробки оновлення:", e)


def check_user_existence_by_telegram_id(telegram_id):
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id FROM customers WHERE telegram_id = %s"
            cursor.execute(sql, (telegram_id,))
            result = cursor.fetchone()
            if result:
                return True
            else:
                return False
    except Exception as e:
        print(f"Помилка при перевірці наявності користувача: {str(e)}")
        return False





def send_message(method, data):
    return requests.post(TELEGRAM_API_URL + method, json=data)


def send_document(method, chat_id, document, caption):
    files = {'document': document}
    data = {'chat_id': chat_id, 'caption': caption}
    requests.post(TELEGRAM_API_URL + method, files=files, data=data)


def check_user_existence(phone_number):
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id FROM customers WHERE phone_number = %s"
            cursor.execute(sql, (phone_number,))
            result = cursor.fetchone()
            if result:
                return result['id']
            else:
                return None
    except Exception as e:
        print(f"Помилка при перевірці наявності користувача: {str(e)}")
        return None


def save_user_data(telegram_id, phone_number, name, last_name):
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO customers (telegram_id, phone_number, name, last_name) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (telegram_id, phone_number, name, last_name))
            connection.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Помилка при збереженні даних користувача: {str(e)}")
        connection.rollback()
        return None


def delete_user_data(telegram_id):
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM customers WHERE telegram_id = %s"
            cursor.execute(sql, (telegram_id,))
            connection.commit()
            return True
    except Exception as e:
        print(f"Помилка при видаленні даних користувача: {str(e)}")
        connection.rollback()
        return False
