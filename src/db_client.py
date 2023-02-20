"""Модуль клиента базы данных

Обертка над клиентом pymongo для удобного использования в 
контексте сервиса "Расписание".

Клиент держит в себе два буфера для расписания: текущий и следующий. Все изменения 
применяются к следующему буферу, чтобы пользователь не видел полуобновленного расписания.
Чтобы применить изменения, текущий буфер меняется местами со следующим.

Пример использования:
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

    Поля:
    - host: str - ip или алиас, к которому будет подключаться клиент
    - port: int - номер порта, на котором развернут сервер mongo
    - username: str - имя пользователя mongodb
    - password: str - пароль пользователя mongodb

    Методы:
    - update_teachers_one(teacher_schedule) - обновить одного учителя
    - update_teachers_many(teacher_schedules) - обновить список учителей
    - update_groups_one(group_schedule) - обновить одну группу
    - update_groups_many(group_schedules) - обновить список групп
    - commit_updates() - применить обновления
    - get_group_list() - получить список групп
    - get_teacher_list() - получить список учителей
    - get_group_schedule_full(group_name) - получить полное расписание группы
    - get_teacher_schedule_full(teacher_name) - получить полное расписание учителя
    """

    def __init__(self, host: str, port: int, username: str, password: str):
        """Конструктор клиента БД
        
        Внутри себя использует pymongo с двумя одинаковыми буферами.
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

        Аргументы:
        - buffer: Collection - буфер, который будет очищен
        """

        pipeline = [{"$match": {}},
                    {"$out": buffer.name}]
        buffer.delete_many({})
        self["template"].aggregate(pipeline)
    

    def update_teachers_one(self, teacher_schedule: dict):
        """Обновить одно расписание препода

        Добавляет в следующий буфер запись об одном преподе

        Аргументы:
        - teacher_schedule: dict - новое расписание препода
        """

        teacher_schedule["nameofteacher"] = teacher_schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_one(teacher_schedule)


    def update_teachers_many(self, teacher_schedules: list[dict]):
        """Обновить много расписаний преподов
        
        Добавляет в следующий буфер много расписаний преподов

        Аргументы:
        - teacher_schedule: list[dict] - список расписаний преподов
        """

        for schedule in teacher_schedules:
            schedule["nameofteacher"] = schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_many(teacher_schedules)
   

    def update_groups_one(self, group_schedule: dict):
        """Обновить расписание одной группы

        Добавляет расписание одной группы в следующий буфер
        
        Аргументы:
        - group_schedule: dict - новое расписание одной группы
        """

        group_schedule["nameofgroup"] = group_schedule.pop("table_name")
        self["next_buffer"]["groups"].insert_one(group_schedule)
    
    def update_groups_many(self, group_schedules: list[dict]):
        """Обновить расписание нескольких групп

        Добавляет расписание нескольких групп в следующий буфер

        Аргументы:
        - group_schedules: list[dict] - новые расписания нескольких групп
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
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)
    
    def get_group_list(self) -> str:
        """Получить список групп

        Возвращает список групп в виде JSON документа
        """

        find_result = self["current_buffer"]["groups"].find({}, {"_id": 0,"nameofgroup": 1})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)

    def get_teacher_schedule_full(self, teacher_name: str) -> str:
        """Получить полное расписание препода

        Возвращает JSON с расписанием препода на две недели: эту и следующую

        Аргументы:
        - teacher_name: str - имя препода
        """

        query = {"nameofteacher": {"$regex": teacher_name, "$options": 'i'}}
        find_result = self["current_buffer"]["teachers"].find(query, {"_id": 0})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)

    def get_group_schedule_full(self, group_name: str) -> str:
        """Получить полное расписание группы

        Возвращает JSON с расписанием группы на две недели: эту и следующую

        Аргументы:
        - group_name: str - имя группы
        """

        query = {"nameofteacher": {"$regex": gruop_name, "$options": 'i'}}
        find_result = self["current_buffer"]["groups"].find(query, {"_id": 0})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)
    
