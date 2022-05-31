from http import HTTPStatus
from typing import Dict
from urllib.error import HTTPError
from dotenv import load_dotenv
import logging
import time
import requests
import json
from telegram import Bot
import os

logger = logging.getLogger(__name__)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO)

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info('Сообщение успешно отправлено в Telegram')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервеса."""
    timestamp = current_timestamp or int(time.time())
    params: Dict = {'from_date': timestamp}
    homeworks: Dict = {'homeworks': [], 'current_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        logger.error('API недоступно')
        raise SystemExit(f'API недоступно: {error}')
    else:
        if response.status_code == HTTPStatus.OK:
            try:
                homeworks = response.json()
            except json.decoder.JSONDecodeError as error:
                logger.error('Не удалось разобрать овтет от API')
                raise requests.JSONDecodeError(f'Не удается разобрать ответ от'
                                               f'API: {error}')
        elif response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            logger.error('API-сервис не доступен')
            raise HTTPError('API-сервис не доступен')
        else:
            logger.error('Неполадки во время выполнения запроса к API-сервису')
            raise HTTPError('Неполадки во время выполнения запроса к'
                            'API-сервису')
    return homeworks


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        logger.error('Тип данных API не соответствует ожидаемому')
        raise TypeError('Тип данных API не соответствует ожидаемому')
    if len(response) == 0:
        logger.error('API передало пустой словарь')
        raise ValueError('API передало пустой словарь')
    hw_list = response.get('homeworks')
    if hw_list is None:
        logger.error('Ответ API не содержит ключ <homeworks>')
        raise KeyError('Ответ API не содержит ключ <homeworks>')
    if not isinstance(hw_list, list):
        logger.error('Тип данных <homeworks> не соответствует ожидаемому')
        raise TypeError('Тип данных <homeworks> не соответствует ожидаемому')
    return hw_list


def parse_status(homework):
    """Объявление статуса домашней работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    if homework_name is None or homework_status is None:
        logger.error('Неизвестный статус ДР')
        raise KeyError('Неизвестный статус ДР')
    if homework_name is None:
        logger.error('Нет названия ДР')
        raise KeyError('Нет названия ДР')
    return message


def check_tokens():
    """Проверка валидности токена."""
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_CHAT_ID is None
            or TELEGRAM_TOKEN is None):
        logger.critical('отсутствие обязательных переменных окружения')
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Не найдены токены для запуска')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    msg_empt = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Нет обновлений по статусам домашней работы')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            new_error_message = f'Сбой в работе программы: {error}'
            logger.error(new_error_message, exc_info=True)
            if msg_empt != message:
                send_message(bot, new_error_message)
            message = new_error_message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
