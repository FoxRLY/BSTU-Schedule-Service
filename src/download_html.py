import requests
import sys

class ScheduleDownloader:
    """Модуль скачивания html страниц и получения ответов с API запросов

    Удобная обертка над библиотекой requests для легкого использования 
    ее функций в контексте сервиса "Расписание".

    Поля: нет

    Методы:
    - try_download_page(url) -> tuple[str, bool]: 
        Попытаться скачать страницу

    - try_get_request(api_url, header, week_index) -> tuple[str, bool]:
        Попытаться получить ответ с сервера
    """

    def try_download_page(self, url: str) -> tuple[str, bool]:
        """Попытаться скачать страницу

        Скачивает html-страницу по указанному адресу и возвращает результат
        с возможностью проверки на успех. Если второй элемент результата равен True,
        то это победа, иначе скачать не вышло.

        Аргументы:
        - url: str - адрес html страницы для скачивания
        """

        agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0'}
        response = requests.get(url, headers=agent)
        if response.ok: 
            return (response.content.decode(encoding="utf-8"), True)
        return ("", False)
    

    def try_get_request(self, api_url: str, header: dict, week_index: int) -> tuple[str, bool]:
        """Попытаться получить расписание с сервера БГТУ
        
        Делает GET запрос на сервер БГТУ через специальный api_url и возвращает
        результат с возможностью проверки на успех. Если второй элемент результата
        равен True, то это победа, иначе запрос не удался.

        Аргументы:
        - api_url: str - специальный API-URL, который использует сервер БГТУ

        - header: dict - заголовок, по которому делается GET запрос

        - week_index: int - индекс недели. 0 - текущая, -1 - предыдущая, 1 и далее - следующие
        """

        agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0'}
        response = requests.get(api_url 
                                + "?entity=" + header["entity"] 
                                + "&id=" + header["id"]
                                + "&week=" + str(week_index)
                                + "&device=" + header["device"], agent)
        
        if response.ok:
            return (response.content.decode(encoding="utf-8"), True)
        return ("", False)


if __name__ == "__main__":
    # Выходим, если нет аргументов
    if len(sys.argv) < 2:
        print("Ошибка: недостаточно аргументов")
        exit()
    url = sys.argv[1]
    text, status = ScheduleDownloader.try_download(url)
    if status:
        print(text)
    else:
        print("Ошибка скачивания")

