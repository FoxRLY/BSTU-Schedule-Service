import pymongo
from pymongo.collection import Collection
import json

'''
Обязательно замени все вхождения schedule_test_db на schedule_db

В текущем буфере хранится акутальное расписание, которое отправляется через REST
В следующем буфере хранится подгружаемое расписание, которое затем становится текущим
'''
class DBClient:
    def __init__(self, host: str, port: int, username: str, password: str):
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
        # Принимает только current_buffer и next_buffer
        return self.buffers[key]
    
    # Очищает следующий буфер и заполняет его нужными структурами из шаблона
    def clear_buffer(self, buffer):
        pipeline = [{"$match": {}},
                    {"$out": buffer.name}]
        buffer.delete_many({})
        self["template"].aggregate(pipeline)
    
    # Добавляет в следующий буфер расписание учителя, следует закидывать сразу полное на две недели для одного препода
    def update_teachers_one(self, teacher_schedule: dict):
        teacher_schedule["nameofteacher"] = teacher_schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_one(teacher_schedule)


    def update_teachers_many(self, teacher_schedules: list[dict]):
        for schedule in teacher_schedules:
            schedule["nameofteacher"] = schedule.pop("table_name")
        self["next_buffer"]["teachers"].insert_many(teacher_schedules)
   
    # Добавляет в следующий буфер расписание группы, следует закидывать сразу полное на две недели для одной группы
    def update_groups_one(self, group_schedule: dict):
        group_schedule["nameofgroup"] = group_schedule.pop("table_name")
        self["next_buffer"]["groups"].insert_one(group_schedule)
    
    def update_groups_many(self, group_schedules: list[dict]):
        for schedule in group_schedules:
            schedule["nameofgroup"] = schedule.pop("table_name")
        self["next_buffer"]["groups"].insert_many(group_schedules)

    # Меняем текущий буфер на следующий буфер с актуальными изменениями
    def commit_updates(self):
        self.buffers["next_buffer"], self.buffers["current_buffer"] = self.buffers["current_buffer"], self.buffers["next_buffer"]
        self.clear_buffer(self["next_buffer"])
    
    # Получить список преподов
    def get_teacher_list(self) -> str:
        find_result = self["current_buffer"]["teachers"].find({}, {"_id": 0, "nameofteacher": 1})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)
    
    # Получить список групп
    def get_group_list(self) -> str:
        find_result = self["current_buffer"]["groups"].find({}, {"_id": 0,"nameofgroup": 1})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)

    # Получить полное раписание препода
    def get_teacher_schedule_full(self, teacher_name: str) -> str:
        query = {"nameofteacher": {"$regex": teacher_name, "$options": 'i'}}
        find_result = self["current_buffer"]["teachers"].find(query, {"_id": 0})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)

    # Получить полное расписание группы
    def get_group_schedule_full(self, group_name: str) -> str:
        query = {"nameofteacher": {"$regex": gruop_name, "$options": 'i'}}
        find_result = self["current_buffer"]["groups"].find(query, {"_id": 0})
        find_result_list = list(map(dict, find_result))
        return json.dumps(find_result_list)


    #def get_teacher_schedule_week(self, teacher_name: str, is_denominator: bool) -> str:
    #    return "bruh" 

if __name__ == "__main__":
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

    
