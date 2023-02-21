from db_client import DBClient
from download_html import ScheduleDownloader
from parse_html import ScheduleParser
import asyncio
import time
from os import environ as env
import json
from aiohttp import web
import traceback
from contextlib import suppress
import aiohttp

class ExitFromServiceException(Exception):
    pass

class ScheduleService:
    def __init__(self):
        self.running = True
        self.is_ready = False
        self.schedule_update_period = int(env.get("SERVICE_UPDATE_TIMER_SECS", 10800))
        self.db_client = DBClient(env.get("DB_CONTAINER_NAME"), 27017, env.get("MONGODB_USERNAME", "foxrly"), env.get("MONGODB_PASSWORD", "1001"))
        agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0'}
        self.downloader = ScheduleDownloader(agent)
        self.parser = ScheduleParser()
        print("Service successfully initialized")


    async def update_timer(self, timer_period=100, number_of_tests=None):
        while True:
            print("Update timer went up")
            await self.update_schedule(test_number=number_of_tests)
            await asyncio.sleep(timer_period)
    

    async def _download_html_page(self, url: str, url_name: str, timeout: int) -> str:
        html_page = ""
        for i in range(timeout):
            html_page, status = await self.downloader.try_download_page(url)
            if not status and i >= timeout-1:
                print(f"{url_name} download timeout: error occurred multiple times on downloading")
                raise RuntimeError(f"No internet connection or bad {url_name} URL")
            elif not status and i < timeout-1:
                print(f"{url_name} download error, retrying...")
                #await asyncio.sleep(0.01)
            else:
                print(f"Successfully downloaded {url_name} page")
                break
        #await asyncio.sleep(0.01)
        return html_page

    async def _get_server_response(self, header: dict, week_index: int, timeout: int) -> str:
        response = ""
        for i in range(timeout):
            response, status = await self.downloader.try_get_request(env.get("SCHEDULE_API_URL", "https://t.bstu.ru/web/api/events"), header, week_index)
            if not status and i >= timeout-1:
                print(f"API request timeout: error occurred multiple times on requesting BSTU server")
                raise RuntimeError(f"No internet connection or bad API request with header {header}")
            elif not status and i < timeout-1:
                print(f"API request error, retrying...")
                await asyncio.sleep(0.1)
            else:
                print("Successfully got response from BSTU server")
                break
        await asyncio.sleep(0.1)
        return response


    async def update_schedule(self, test_number=None):

        # 1) Скачать списки преподов и групп
        # Список преподов в виде html
        teacher_list_html = await self._download_html_page(env.get("SCHEDULE_TEACHER_LIST_URL", "https://t.bstu.ru/raspisaniya/prepodavateli"), "Teacher", 3)


        # Список групп в виде html
        group_list_html = await self._download_html_page(env.get("SCHEDULE_GROUP_LIST_URL", "https://t.bstu.ru/raspisaniya/gruppy"), "Group", 3)


        # 2) Спарсить все ссылки преподов и групп из скачанных списков
        # Ссылки на преподов
        teacher_urls = self.parser.get_teacher_urls(teacher_list_html, env.get("SCHEDULE_BASE_URL", "https://t.bstu.ru"))
        # Ссылки на группы
        group_urls = self.parser.get_group_urls(group_list_html, env.get("SCHEDULE_BASE_URL", "https://t.bstu.ru"))
        if test_number is not None:
            teacher_urls = teacher_urls[0:test_number]
            group_urls = group_urls[0:test_number]


        # 3) Скачать все заголовки расписаний преподов и групп с помощью предыдущих ссылок
        # Заголовки перподов

        teacher_headers_html = []
        for index, teacher_url in enumerate(teacher_urls):
            header_html = await self._download_html_page(teacher_url, f"Teacher header {index})", 3)
            teacher_headers_html.append(header_html)
        # Заголовки групп
        group_headers_html = []
        for index, group_url in enumerate(group_urls):
            header_html = await self._download_html_page(group_url, f"Group header {index}", 3)
            group_headers_html.append(header_html)


        # 4) Спарсить заголовки расписаний преподов и групп
        # Нормальные заголовки преподов
        start = time.perf_counter()
        teacher_headers = []
        for header_html in teacher_headers_html:
            header = self.parser.get_schedule_header(header_html)
            teacher_headers.append(header)
        end = time.perf_counter() - start
        print(f"Processed teacher headers in {end} seconds")
        # Нормальные заголовки групп
        start = time.perf_counter()
        group_headers = []
        for header_html in group_headers_html:
            header = self.parser.get_schedule_header(header_html)
            group_headers.append(header)
        end = time.perf_counter() - start
        print(f"Processed group headers in {end} seconds")


        # 5) По заголовкам скачать расписания преподов и групп
        # Скачиваем и форматируем расписания преподов
        teacher_schedules_html = []
        for number, header in enumerate(teacher_headers):
            print(f"Teacher {number}")
            schedule_html = dict(html=[], is_denominator=[])
            for week_index in range(2):
                json_response = await self._get_server_response(header, week_index, 3)
                response = json.loads(json_response)
                if not response["success"]:
                    raise RuntimeError(f"Bad request with header {header}")
                schedule_html["html"].append(response["result"]["html"]["week"])
                schedule_html["is_denominator"].append(response["result"]["week"]["is_denominator"])
            teacher_schedules_html.append(schedule_html)
        # Скачиваем и форматируем расписания групп
        group_schedules_html = []
        for number, header in enumerate(group_headers):
            print(f"Group {number}")
            schedule_html = dict(html=[], is_denominator=[])
            for week_index in range(2):
                json_response = await self._get_server_response(header, week_index, 3)
                response = json.loads(json_response)
                if not response["success"]:
                    raise RuntimeError(f"Bad request with header {header}")
                schedule_html["html"].append(response["result"]["html"]["week"])
                schedule_html["is_denominator"].append(response["result"]["week"]["is_denominator"])
            group_schedules_html.append(schedule_html)
                

        # 6) Спарсить расписания преподов и групп в Python-объекты
        teacher_schedules = []
        for header, schedule_html in zip(teacher_headers, teacher_schedules_html):
            schedule = self.parser.parse_full(schedule_html["html"], header, schedule_html["is_denominator"])
            teacher_schedules.append(schedule)
        group_schedules = []
        for header, schedule_html in zip(group_headers, group_schedules_html):
            schedule = self.parser.parse_full(schedule_html["html"], header, schedule_html["is_denominator"])
            group_schedules.append(schedule)


        # 7) Запихнуть раписания в базу данных
        self.db_client.update_teachers_many(teacher_schedules)
        self.db_client.update_groups_many(group_schedules)
        # 8) Применить изменения базы
        self.is_ready = False
        self.db_client.commit_updates()
        self.is_ready = True
        

    async def run(self):
        tasks = [self.update_timer(timer_period=self.schedule_update_period)]
        for index in range(len(tasks)):
            tasks[index] = asyncio.create_task(tasks[index])
        gather = asyncio.gather(*tasks)
        try:
            await gather
        except ExitFromServiceException:
            print("Service ended successfully!")
        except Exception:
            print(f"Service ended unexpectedly with this error: {traceback.format_exc()}")
        finally:
            for task in tasks:
                task.cancel()

    async def run_test(self):
        tasks = [self.update_timer(timer_period=150, number_of_tests=5)]
        for index in range(len(tasks)):
            tasks[index] = asyncio.create_task(tasks[index])
        gather = asyncio.gather(*tasks)
        try:
            await gather
        except ExitFromServiceException:
            print("Service ended successfully!")
        except Exception:
            print(f"Service ended unexpectedly with this error: {traceback.format_exc()}")
        finally:
            for task in tasks:
                task.cancel()

    async def run_corutine(self, _app):
       task = asyncio.create_task(self.run_test())
       yield
       task.cancel()
       with suppress(asyncio.CancelledError):
           await task

    async def teacher_list_handler(self, request):
        teacher_list_json = self.db_client.get_teacher_list()
        return web.Response(status=200,text=teacher_list_json, content_type="text/json")
    
    async def teacher_schedule_full_handler(self, request):
        teacher_name_json = dict()
        try:
            teacher_name_json = await request.json()
        except:
            raise web.HTTPBadRequest(reason="Bad json formatting")
        if "nameofteacher" not in teacher_name_json.keys():
            raise web.HTTPBadRequest(reason="Bad request")
        teacher_schedule = self.db_client.get_teacher_schedule_full(teacher_name_json["nameofteacher"])
        return web.Response(status=200, text=teacher_schedule, content_type="text/json")

    async def group_list_handler(self, request):
        group_list_json = self.db_client.get_group_list()
        return web.Response(status=200,text=group_list_json, content_type="text/json")

    async def group_schedule_full_handler(self, request):
        group_name_json = dict()
        try:
            group_name_json = await request.json()
        except:
            raise web.HTTPBadRequest(reason="Bad json formatting")
        if "nameofgroup" not in group_name_json.keys():
            raise web.HTTPBadRequest(reason="Bad request")
        group_schedule = self.db_client.get_group_schedule_full(group_name_json["nameofgroup"])
        return web.Response(status=200, text=group_schedule, content_type="text/json")

if __name__ == "__main__":
    # Инициализируем сервис
    service = ScheduleService()
    
    # Инициализируем сервер
    app = web.Application()
    
    # Пихаем сервис в сервер
    app["state"] = {"service": service}
    
    # Запускаем сервис
    app.cleanup_ctx.append(service.run_corutine)

    # Добавляем роуты для сервера
    app.add_routes([web.get("/teacher/list", service.teacher_list_handler),
                    web.get("/teacher/schedule", service.teacher_schedule_full_handler),
                    web.get("/group/list", service.group_list_handler),
                    web.get("/group/schedule", service.group_schedule_full_handler)])
    # Стартуем сервер
    web.run_app(app)
