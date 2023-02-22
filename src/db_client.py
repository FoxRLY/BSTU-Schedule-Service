"""Модуль клиента базы данных

Обертка над клиентом pymongo для удобного использования в 
контексте сервиса "Расписание".

Клиент держит в себе два буфера для расписания: текущий и следующий. Все изменения 
применяются к следующему буферу, чтобы пользователь не видел полуобновленного расписания.
Чтобы применить изменения, текущий буфер меняется местами со следующим.

Example:
    from os import environ as env
    client = DBClient("localhost", 27017, env.get("MONGODB_USERNAME"), env.get("MONGODB_PASSWORD"))

    prepod = dict()
    with open("../test_trash/json_schedule.json") as json_file:
        prepod = json.load(json_file)
    client.update_teachers_one(prepod)
    client.commit_updates()
    teacher_schedule = client.get_teacher_schedule_full("Абакумов Роман Григорьевич")
    print(teacher_schedule)
    with open("../test_trash/db_dump_schedule.json", "w") as json_file:
        json_file.write(teacher_schedule)
"""

import pymongo
from pymongo.collection import Collection
import json

class DBClient:
    """Класс клиента базы данных
    
    Обертка над pymongo клиентом с возможностью атомарного обновления расписания.

    Attributes:
        client (pymongo.MongoClient):
            Клиента для MongoDB
        db (pymongo.Database):
            База данных, в которой хранятся буферы
        buffers (dict):
            Буферы с расписанием

    """

    def __init__(self, host: str, port: int, username: str, password: str):
        """Конструктор

        Args:
            host (str):
                Ip или алиас, к которому будет подключаться клиент
            port (int):
                Номер порта, на котором развернут сервер mongo
            username (str):
                Имя пользователя mongodb
            password (str):
                Пароль пользователя mongodb
        
        """

        pymongo.MongoClient()
        self.client = pymongo.MongoClient(host, port,
                                          username=username,
                                          password=password)
        for i in range(timeout_counter:=3):
            try:
                print("Trying to connect to database...")
                self.client.list_database_names()
                print("Successfully connected to database")
                break
            except pymongo.errors.ConnectionFailure as e:
                print("Database connection failed")
                if i == timeout_counter-1:
                    print("Database connection counter exceeded. Closing service")
                    raise e
                
        self.client.drop_database("schedule_db")
        self.db = self.client["schedule_db"]

        self.buffers = dict(current_buffer = self.db["buffer_1"], next_buffer = self.db["buffer_2"], template = self.db["template"])
        self.buffers["template"].insert_one({"teachers": [], "groups": []})


    def __getitem__(self, key: str) -> Collection:
        return self.buffers[key]
    

    def _clear_buffer(self, buffer: Collection):
        """Очищает указанный буфер
        
        Приводит буфер к первоначальному состоянию с помощью шаблона

        Args:
            buffer (Collection):
                Буфер, который будет очищен

        """

        buffer["teachers"].delete_many({})
        buffer["groups"].delete_many({})
        pipeline = [{"$match": {}},
                    {"$out": buffer.full_name}]
        self["template"].aggregate(pipeline)
    

    def update_teachers_one(self, teacher_schedule: dict):
        """Обновить одно расписание препода

        Добавляет в следующий буфер запись об одном преподе

        Args:
            teacher_schedule (dict):
                Новое расписание препода

        """

        teacher_schedule["nameofteacher"] = teacher_schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_one(teacher_schedule)


    def update_teachers_many(self, teacher_schedules: list[dict]):
        """Обновить много расписаний преподов
        
        Добавляет в следующий буфер много расписаний преподов

        Args:
            teacher_schedule (list[dict]):
                Список расписаний преподов

        """

        for schedule in teacher_schedules:
            schedule["nameofteacher"] = schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_many(teacher_schedules)
   

    def update_groups_one(self, group_schedule: dict):
        """Обновить расписание одной группы

        Добавляет расписание одной группы в следующий буфер
        
        Args:
            group_schedule (dict):
                Новое расписание одной группы
        
        """

        group_schedule["nameofgroup"] = group_schedule.pop("table_name")
        self["next_buffer"]["groups"].insert_one(group_schedule)
    
    def update_groups_many(self, group_schedules: list[dict]):
        """Обновить расписание нескольких групп

        Добавляет расписание нескольких групп в следующий буфер

        Args:
            group_schedules (list[dict]):
                Новые расписания нескольких групп
        
        """

        for schedule in group_schedules:
            schedule["nameofgroup"] = schedule.pop("table_name")
        self["next_buffer"]["groups"].insert_many(group_schedules)

    def commit_updates(self):
        """Применить обновления
        
        Меняет местами текущий и следующий буфер, предоставляя пользователю
        доступ к обновлениям
        
        """

        self.buffers["next_buffer"], self.buffers["current_buffer"] = self.buffers["current_buffer"], self.buffers["next_buffer"]
        self._clear_buffer(self["next_buffer"])
    
    def get_teacher_list(self) -> str:
        """Получить список преподов

        Возвращает список преподов в виде JSON документа
        
        """

        find_result = self["current_buffer"]["teachers"].find({}, {"_id": 0, "nameofteacher": 1})
        find_result_raw = list(map(dict, find_result))
        find_result_list = dict(teacher_names = [name["nameofteacher"] for name in find_result_raw])
        return json.dumps(find_result_list)
    
    def get_group_list(self) -> str:
        """Получить список групп

        Возвращает список групп в виде JSON документа
        
        """

        find_result = self["current_buffer"]["groups"].find({}, {"_id": 0,"nameofgroup": 1})
        find_result_raw = list(map(dict, find_result))
        find_result_list = dict(group_names = [name["nameofgroup"] for name in find_result_raw])
        return json.dumps(find_result_list)

    def get_teacher_schedule_full(self, teacher_name: str) -> str:
        """Получить полное расписание препода

        Возвращает JSON с расписанием препода на две недели: эту и следующую

        Args:
            teacher_name (str):
                Имя препода
        
        """

        query = {"nameofteacher": {"$regex": teacher_name, "$options": 'i'}}
        find_result = self["current_buffer"]["teachers"].find_one(query, {"_id": 0})
        if find_result:
            find_result_list = dict(find_result)
            return json.dumps(find_result_list)
        return ""

    def get_group_schedule_full(self, group_name: str) -> str:
        """Получить полное расписание группы

        Возвращает JSON с расписанием группы на две недели: эту и следующую

        Args:
            group_name (str):
                Имя группы
        
        """

        query = {"nameofgroup": {"$regex": group_name, "$options": 'i'}}
        find_result = self["current_buffer"]["groups"].find_one(query, {"_id": 0})
        if find_result:
            find_result_list = dict(find_result)
            return json.dumps(find_result_list)
        return ""
    
