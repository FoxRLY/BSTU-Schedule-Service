"""Вспомогательный модуль для скачивания расписания

Удобная обертка над библиотекой aiohttp для легкого использования 
ее функций в контексте сервиса "Расписание".

Пример использования:
    agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0'}
    url = "https://google.com"
    downloader = ScheduleDownloader(agent)
    text, status = await downloader.try_download(url)
    if status:
        print(text)
    else:
        print("Ошибка скачивания")
"""

import aiohttp
import sys

class ScheduleDownloader:
    """Класс для скачивания html страниц и получения ответов с API запросов

    Удобная обертка над библиотекой aiohttp для легкого использования 
    ее функций в контексте сервиса "Расписание".

    Поля:
    - headers: dict - Юзер-агент для получения корректного контента с сервера

    Методы:
    - try_download_page(url) -> tuple[str, bool]: 
        Попытаться скачать страницу

    - try_get_request(api_url, header, week_index) -> tuple[str, bool]:
        Попытаться получить ответ с сервера
    """
    
    def __init__(self, headers: dict):
        """Конструктор загрузчика 
        
        Настраивает заголовки, которые помогут получать корректные данные с серверов
        
        Аргументы:
        - headers: dict - заголовки для HTTP запроса
        """

        self.headers = headers

    async def try_download_page(self, url: str) -> tuple[str, bool]:
        """Попытаться скачать страницу

        Скачивает html-страницу по указанному адресу и возвращает результат
        с возможностью проверки на успех. Если второй элемент результата равен True,
        то это победа, иначе скачать не вышло.

        Аргументы:
        - url: str - адрес html страницы для скачивания
        """

        async with aiohttp.ClientSession() as client:
            response = await client.get(url, headers=self.headers)
            if response.status == 200:
                return (response.text(), True)
            return ("", False)


    def try_get_request(self, api_url: str, header: dict, week_index: int) -> tuple[str, bool]:
        """Попытаться получить расписание с сервера БГТУ
        
        Делает GET запрос на сервер БГТУ через специальный api_url и возвращает
        результат с возможностью проверки на успех. Если второй элемент результата
        равен True, то это победа, иначе запрос не удался.

        Аргументы:
        - api_url: str - специальный API-URL, который использует сервер БГТУ

        - header: dict - заголовок для БГТУ API, по которому делается GET запрос (Смотри в парсер)

        - week_index: int - индекс недели. 0 - текущая, -1 - предыдущая, 1 и далее - следующие
        """

        async with aiohttp.ClientSession() as client:
            response = await client.get(api_url 
                                + "?entity=" + header["entity"] 
                                + "&id=" + header["id"]
                                + "&week=" + str(week_index)
                                + "&device=" + header["device"], headers=self.headers) 
            if response.status == 200:
                return (response.text(), True)
            return ("", False)

