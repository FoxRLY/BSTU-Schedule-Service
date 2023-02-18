from bs4 import BeautifulSoup
import json
import re
import itertools
from download_html import ScheduleDownloader
from dotenv import dotenv_values

'''
Как пользоваться:
    1) Скачиваем html страницу со списком групп/преподов
    2) Парсим с него все ссылки на расписания
    3) Скачиваем все расписания через ссылки
    4) Из каждого расписания выуживаем заголовок: имя препода/название группы, entity, id и strategy
    5) По заголовку делаем GET запрос на сервер и получаем расписание на эту и следующую неделю
    6) Парсим полученные расписания в json

'''

class ScheduleParser:
    # Получить ссылки на все группы из страницы списка групп
    def get_group_urls(self, list_html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(list_html, "lxml")
        group_urls_raw = soup.find_all("a", {"class": "group__item"})
        group_urls: list[str] = []
        for group_url_raw in group_urls_raw:
            group_urls.append(base_url+group_url_raw["href"])
        return group_urls

    # Получить ссылки на всех преподов из страницы списка преподов
    def get_teacher_urls(self, list_html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(list_html, "lxml")
        cab_regexp = r"(Г?УК\d?[ *[a-zA-Z0-9а-яА-Я_\(\)]*]*)|(КБ[ *[a-zA-Z0-9а-яА-Я_]*]*)|([К|к]афедра[\s*ТМН]*)|(ЦВТ[ *[a-zA-Z0-9а-яА-Я_]*]*)|([_|Баз\.]*[К|к]аф\.?[ *[a-zA-Z0-9а-яА-Я_\.]*]*)|(Дист\.)|(Ск\. маст\.)|(УТК)"
        teacher_urls_raw = soup.find_all("a", {"class": "teachers__item"})
        teacher_urls: list[str] = []
        for teacher_url_raw in teacher_urls_raw:
            if not re.search(cab_regexp ,teacher_url_raw.text.strip()):
                print(teacher_url_raw.text.strip())
                teacher_urls.append(base_url + teacher_url_raw["href"])
        return teacher_urls
    
    # Получить заголовок расписания со страницы расписания
    def get_schedule_header(self, schedule_html: str) -> dict:
        header = dict()
        soup = BeautifulSoup(schedule_html, "lxml")
        header["table_name"] = soup.find("h1", {"class": "title"}).text.strip()
        data = soup.find("div", {"class": "_timetable_page offset"})
        header["entity"] = data["data-entity"]
        header["device"] = data["data-strategy"]
        header["id"] = data["data-id"]
        return header
    
    # Спарсить данные с полученного через заголовок расписания в заготовку
    def parse_html_to_raw_data(self, html_text: str, header: dict, is_denominator: bool) -> list[list[str]]:
        soup = BeautifulSoup(html_text, "lxml")
        table_name = header["table_name"]
        week_status = "Знаменатель" if is_denominator else "Числитель"
        days = soup.find_all("div", {"class": "week__day"})
        parsed_days: list[list[str]] = []
        parsed_days.append([table_name, week_status])
        for day in days:
            day_data: list[str] = list(map(str.strip, day.text.split("\n")))
            day_data = list(filter(lambda x: x != "" and x != "\n", day_data))
            parsed_days.append(day_data)
        return parsed_days

    # Используя заготовку, сделать Python объект с расписанием
    def parse_raw_data_to_json(self, raw_data: list[list[str]]) -> dict:
        cab_regexp = r"(Г?УК\d?[ *[a-zA-Z0-9а-яА-Я_\(\)]*]*)|(КБ[ *[a-zA-Z0-9а-яА-Я_]*]*)|([К|к]афедра[\s*ТМН]*)|(ЦВТ[ *[a-zA-Z0-9а-яА-Я_]*]*)|([_|Баз\.]*[К|к]аф\.?[ *[a-zA-Z0-9а-яА-Я_\.]*]*)|(Дист\.)|(Ск\. маст\.)|(УТК)"
        teacher_regexp = r"[a-zA-Zа-яА-я]* [a-zA-Zа-яА-я\.]*"
        group_regexp = r"[а-яА-яa-zA-Z]*-\d*"

        # Заголовок дня
        header = raw_data.pop(0)
        
        # Тип расписания (Препод или Группа)
        schedule_type = {"type": "", "regexp": ""}
        if re.search(group_regexp, header[0]):          # Группа
            schedule_type["type"] = "teacher"
            schedule_type["regexp"] = teacher_regexp
        else:                                           # Препод
            schedule_type["type"] = "group"
            schedule_type["regexp"] = group_regexp

        schedule = dict(week_status=header[1], day=[])
        for day in raw_data:
            # Словарь перевода сокращенного названия дня в нормальное
            day_map = {"Пн": "Понедельник", "Вт": "Вторник",
                       "Ср": "Среда", "Чт": "Четверг",
                       "Пт": "Пятница", "Сб": "Суббота",
                       "Вс": "Воскресенье"}
            
            # Инфа о дне в расписании
            day_dict = dict(day_of_week=day_map[day[0]], date=day[1], subjects=[])
            day.pop(0)
            day.pop(0)
            day_iter = iter(day)
            while (entry := next(day_iter, None)) is not None:
                if entry == "Нет занятий":
                    break
                elif entry == "Перерыв":
                    day_dict["subjects"].append({"name": "Перерыв 1 час"})
                    next(day_iter, None)
                else:
                    subj_dict = dict()
                    subj_dict["number"] = entry                 # Номер пары
                    subj_dict["type"] = next(day_iter, None)    # Тип пары
                    subj_dict["name"] = next(day_iter, None)    # Название предмета
                    subj_dict["start"] = next(day_iter, None)   # Время начала пары
                    next(day_iter, None)                        # Черта
                    subj_dict["end"] = next(day_iter, None)     # Время конца пары

                    # Если нашли аудитории, то вписываем их
                    subj_dict["classroom"] = []
                    while (entry := next(day_iter, None)) and (cab := re.match(cab_regexp, entry)):
                        subj_dict["classroom"].append(str(cab.group(0)))
                    day_iter = itertools.chain([entry], day_iter)

                    # Если нашли учителей, то вписываем их
                    subj_dict[schedule_type["type"]] = []
                    while (entry := next(day_iter, None)) and re.search(schedule_type["regexp"], entry):
                        subj_dict[schedule_type["type"]].append(entry)
                    day_iter = itertools.chain([entry], day_iter)
                    day_dict["subjects"].append(subj_dict)
            schedule["day"].append(day_dict)
        return schedule

    # Парсинг html-строки с расписанием на неделю из GET запроса в Python объект
    def parse(self, html_text: str, header: dict, is_denominator: bool) -> dict:
        return self.parse_raw_data_to_json(self.parse_html_to_raw_data(html_text, header, is_denominator))
    
    # Полный парсинг расписания из GET запросов в Python объект, готовый к вставке в базу данных
    def parse_full(self, html_text: list[str], header: dict, is_denominator: list[bool]) -> dict:
        if len(is_denominator) != len(html_text):
            raise ValueError(f"Количество недель и их типов не совпадает: {len(html_text)} и {len(is_denominator)}")
        full_schedule = dict()
        full_schedule["table_name"] = header["table_name"]
        full_schedule["weeks"] = []
        for text, flag in zip(html_text, is_denominator):
            full_schedule["weeks"].append(self.parse(text, header, flag))
        return full_schedule
        

if __name__ == "__main__":
    env = dotenv_values("../.env")
    base_url = env["SCHEDULE_BASE_URL"]
    teacher_list_url = env["SCHEDULE_TEACHER_LIST"]
    api_url = env["SCHEDULE_API_URL"]
    parser = ScheduleParser()

    # Скачиваем список преподов
    html_text, status = ScheduleDownloader.try_download_page(teacher_list_url)
    if not status:
        print("Не удалось скачать список преподов")
        exit()
    # Парсим с него ссылки на заголовки преподов
    urls = parser.get_teacher_urls(html_text, base_url)

    # Скачиваем заголовочную страницу первого препода
    print(f"Пытаемся скачать заголовок с {urls[0]}")
    html_text, status = ScheduleDownloader.try_download_page(urls[0])
    if not status:
        print("Не удалось скачать заголовок")
        exit()
    # Парсим с него заголовок
    header = parser.get_schedule_header(html_text)
    
    # Скачиваем json-файл с расписанием на текущую неделю
    schedule_week_current_json, status = ScheduleDownloader.try_get_request(api_url, header, 0)
    if not status:
        print("Не удалось скачать расписание через API")
        exit()
    # Парсим расписание из json-файла
    json_schedule_raw = json.loads(schedule_week_current_json)
    if not json_schedule_raw["success"]:
        print("Расписание получено, но ответ отрицательный")
        exit()
    is_denominator = json_schedule_raw["result"]["week"]["is_denominator"]
    schedule_html = json_schedule_raw["result"]["html"]["week"]
    json_schedule_object = parser.parse_full([schedule_html], header, [is_denominator])
    with open("../test_trash/json_schedule.json", "w") as json_file:
        json_file.write(json.dumps(json_schedule_object))
