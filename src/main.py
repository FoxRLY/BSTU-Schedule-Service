from db_client import DBClient
from download_html import ScheduleDownloader
from parse_html import ScheduleParser
import asyncio
import time
import random
from dotenv import dotenv_values
import json

class ExitFromServiceException(Exception):
    pass

class ScheduleService:
    def __init__(self, env: dict):
        self.env = env
        self.running = True
        self.is_ready = False
        self.schedule_update_period = self.env["SERVICE_UPDATE_TIMER_SECS"]
        self.db_client = DBClient(self.env["MONGODB_USERNAME"], self.env["MONGODB_PASSWORD"])
        self.downloader = ScheduleDownloader()
        self.parser = ScheduleParser()
        print("Service successfully initialized")
    
    async def change_ready_state(self, new_state: bool):
        self.is_ready = new_state

    async def exit_timer(self):
        await asyncio.sleep(10)
        print("Exit timer went up")
        raise ExitFromServiceException
     
    async def update_timer(self):
        while True:
            await self.update_schedule()
            print("Update timer wenlist_html")
            await asyncio.sleep(self.schedule_update_period)
    
    async def _download_html_page(self, url: str, url_name: str, timeout: int) -> str:
        html_page = ""
        for i in range(timeout_counter:=3):
            html_page, status = self.downloader.try_download_page(url)
            if not status and i >= timeout_counter-1:
                print(f"{url_name} download timeout: error occurred multiple times on downloading")
                raise RuntimeError(f"No internet connection or bad {url_name} URL")
            elif not status and i < timeout_counter-1:
                print(f"{url_name} download error, retrying...")
                await asyncio.sleep(1)
            else:
                print(f"Successfully downloaded {url_name} page")
                break
        await asyncio.sleep(1)
        return html_page

    async def _get_server_response(self, header: dict, week_index: int, timeout: int) -> str:
        response = ""
        for i in range(timeout_counter:=3):
            response, status = self.downloader.try_get_request(self.env["SCHEDULE_API_URL"], header, week_index)
            if not status and i >= timeout_counter-1:
                print(f"API request timeout: error occurred multiple times on requesting BSTU server")
                raise RuntimeError(f"No internet connection or bad API request with header {header}")
            elif not status and i < timeout_counter-1:
                print(f"API request error, retrying...")
                await asyncio.sleep(1)
            else:
                print("Successfully got response from BSTU server")
                break
        await asyncio.sleep(1)
        return response

    async def update_schedule(self):
        # 1) Скачать списки преподов и групп
        
        # Список преподов в виде html
        teacher_list_html = await self._download_html_page(self.env["SCHEDULE_TEACHER_LIST_URL"], "Teacher", 3)

        # Список групп в виде html
        group_list_html = await self._download_html_page(self.env["SCHEDULE_GROUP_LIST_URL"], "Group", 3)
        

        # 2) Спарсить все ссылки преподов и групп из скачанных списков
        
        # Ссылки на преподов
        teacher_urls = self.parser.get_teacher_urls(teacher_list_html, self.env["SCHEDULE_BASE_URL"])

        # Ссылки на группы
        group_urls = self.parser.get_group_urls(group_list_html, self.env["SCHEDULE_BASE_URL"])
        

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
        for header in teacher_headers:
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
        for header in group_headers:
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
        await self.change_ready_state(False)
        self.db_client.commit_updates()
        await self.change_ready_state(True)
        
        

    async def answer_requests(self):
        while True:
            print("Answering requests")
            await asyncio.sleep(5)

    async def run(self):
        tasks = [self.update_timer(), self.answer_requests()]
        for index in range(len(tasks)):
            tasks[index] = asyncio.create_task(tasks[index])
        gather = asyncio.gather(*tasks)
        try:
            await gather
        except ExitFromServiceException:
            print("Service ended successfully!")
        except Exception as e:
            print(f"Service ended unexpectedly with this error: {e}")
        finally:
            for task in tasks:
                task.cancel()
    
    async def run_test(self):
        tasks = [self.update_timer_test(), self.answer_requests_test()]
        for index in range(len(tasks)):
            tasks[index] = asyncio.create_task(tasks[index])
        gather = asyncio.gather(*tasks)
        try:
            await gather
        except ExitFromServiceException:
            print("Service ended successfully!")
        except Exception as e:
            print(f"Service ended unexpectedly with this error: {e}")
            raise e
        finally:
            for task in tasks:
                task.cancel()

    
    async def update_timer_test(self):
        while True:
            await self.update_schedule_test()
            print("Update timer went up")
            await asyncio.sleep(100)


    async def update_schedule_test(self):
        # 1) Скачать списки преподов и групп
        
        # Список преподов в виде html
        teacher_list_html = await self._download_html_page(self.env["SCHEDULE_TEACHER_LIST_URL"], "Teacher", 3)

        # Список групп в виде html
        group_list_html = await self._download_html_page(self.env["SCHEDULE_GROUP_LIST_URL"], "Group", 3)
        

        # 2) Спарсить все ссылки преподов и групп из скачанных списков
        
        # Ссылки на преподов
        teacher_urls = self.parser.get_teacher_urls(teacher_list_html, self.env["SCHEDULE_BASE_URL"])[0:5]

        # Ссылки на группы
        group_urls = self.parser.get_group_urls(group_list_html, self.env["SCHEDULE_BASE_URL"])[0:5]
        

        # 3) Скачать все заголовки расписаний преподов и групп с помощью предыдущих ссылок
        
        # Заголовки перподов
        teacher_headers_html = []
        for index, teacher_url in enumerate(teacher_urls):
            header_html = await self._download_html_page(teacher_url, f"Teacher header {index}", 3)
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
        for header in teacher_headers:
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
        for header in group_headers:
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
        await self.change_ready_state(False)
        self.db_client.commit_updates()
        await self.change_ready_state(True)

    
    async def answer_requests_test(self):
        while True:
            if self.is_ready:
                teacher_list_json = self.db_client.get_teacher_list()
                teacher_list = json.loads(teacher_list_json)
                for teacher_name in teacher_list:
                    teacher_name = teacher_name["nameofteacher"]
                    teacher_schedule = self.db_client.get_teacher_schedule_full(teacher_name)
                    teacher_schedule = json.loads(teacher_schedule)
                    print(teacher_schedule)
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)



if __name__ == "__main__":
    env = dotenv_values("../.env")
    service = ScheduleService(env)
    start = time.perf_counter()
    asyncio.run(service.run_test())
    result = time.perf_counter() - start
    print(result)