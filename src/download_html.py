import requests
import sys

class ScheduleDownloader:
    # Попытаться скачать страницу
    def try_download_page(url: str) -> tuple[str, bool]:
        agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        response = requests.get(url, headers=agent)
        if response.ok: 
            return (response.content.decode(encoding="utf-8"), True)
        return ("", False)
    
    # Попытаться получить недельное расписание в формате json через GET запрос
    def try_get_request(api_url: str, header: dict, week_index: int) -> tuple[str, bool]:
        agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
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

