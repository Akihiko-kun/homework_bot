import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class APIError(Exception):
    """Если API не захочет работать."""

    pass


class message_API_Error(Exception):
    """Исключение для send_massage."""

    pass


def check_tokens():
    """проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logger.error('Ошибка отправки сообщения в телеграм')
        raise message_API_Error('Ошибка отправки сообщения в телеграм')
    else:
        logging.debug(f'Сообщение отправлено {message}')


def get_api_answer(timestamp):
    """делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise APIError(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise APIError(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """роверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка, возращает не список.')
    if 'homeworks' not in response:
        raise KeyError('Homeworks не найден.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Запрос возвращает не словарь.')
    if homeworks:
        return homeworks
    return None


def parse_status(homework):
    """извлекает из информации о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if not check_tokens():
        msg = 'Отсутствует одна или несколько переменных окружения'
        logging.critical(msg)
        sys.exit(msg)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            logging.info('Список работ получен')
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
                timestamp = response['current_date']
            else:
                logging.info('Новых заданий нет')
        except message_API_Error as error:
            logger.error(error)
            error_message = f'Ошибка: {error}'
            send_message(bot, error_message)
        except Exception as error:
            logger.error(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
