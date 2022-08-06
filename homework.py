from http import HTTPStatus
from json import JSONDecodeError

from logging.handlers import RotatingFileHandler
import os
import time
import logging
import sys

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(funcName)s, %(lineno)s, %(levelname)s, %(message)s',
    filemode='w'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('my_logger.log',
                              encoding='UTF-8',
                              maxBytes=50000000,
                              backupCount=5
                              )
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class APIUnexpectedHTTPStatus(Exception):
    """Исключение при ответе сервера отличным от 200."""

    pass


class SendMessageError(Exception):
    """Исключение в отправке сообщения в ТГ."""

    pass


class PageRequestError(Exception):
    """Исключение в запросе страницы."""
    
    pass


class HomeworkError(Exception):
    """Исключение в списке домашних работ."""

    pass


class HomeworkStatusError(Exception):
    """Исключение в статусе домашних работ."""

    pass


def send_message(bot, message):
    """Отправляет сообщение в телеграм-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в отправлено {TELEGRAM_CHAT_ID}: {message}')
    except SendMessageError:
        logger.critical('Ошибка. Сообщение в ТГ не отправлено')
        raise SendMessageError('Ошибка. Сообщение в ТГ не отправлено')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except PageRequestError as error:
        logging.error(f'Ошибка при запросе: {error}')
        raise PageRequestError(f'Ошибка при запросе: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'ошибка в доуступности {status_code}')
        raise APIUnexpectedHTTPStatus(f'ошибка в доступности {status_code}')
    try:
        return homework_statuses.json()
    except JSONDecodeError:
        logger.error('Ошибка парсинга')
        raise JSONDecodeError('Ошибка парсинга')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    try:
        list_works = response['homeworks']
    except KeyError:
        logger.error('Ошибка словаря по ключу homeworks')
        raise KeyError('Ошибка словаря по ключу homeworks')
    try:
        homework = list_works[0]
    except HomeworkError:
        logger.error('Список домашних работ пуст')
        raise HomeworkError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус."""
    if 'homework_name' not in homework:
        logging.error('нет ключа homework_name')
        raise KeyError('нет ключа homework_name')
    if 'status' not in homework:
        logging.error('нет клююча status')
        raise Exception('нет ключа status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise HomeworkStatusError('неизвестный статус')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет переменные окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = ''
    error_cache_message = ''
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        raise Exception('Отсутствуют одна или несколько переменных окружения')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            message = parse_status(check_response(response))
            if message != status:
                send_message(bot, message)
                status = message
        except Exception as error:
            logger.error(error)
            message_error = str(error)
            if message_error != error_cache_message:
                send_message(bot, message_error)
                error_cache_message = message_error
        except KeyboardInterrupt:
            sys.exit(0)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
