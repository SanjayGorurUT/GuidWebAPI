import tornado.web
import tornado.ioloop
import certifi
from pymongo import MongoClient
import secrets
import json
import redis
import datetime

ca = certifi.where()
client = MongoClient("mongodb+srv://tornado:cache@swelab-project.uvpgv47.mongodb.net/?retryWrites=true&w=majority", tlsCAFile = ca)
cache = redis.Redis(host='localhost', port=6379, db=0)

class basicRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Get Request: currently not being used")
    
    def post(self):
        args = self.request.arguments
        user = None
        expire = None

        if 'user' in args:
            user = self.get_argument('user')
        if 'expire' in args:
            expire = self.get_argument('expire')

        if user == None:
            self.set_status(400)
            self.write("Error: Missing 'user' field in request data")
            return
        
        newGuid = ""
        while True:
            newGuid = secrets.token_hex(16)
            if(client.access.guids.find_one({"guid": newGuid})) == None:
                break

        if expire == None:
            expire = 1427736345
        expire = int(expire)
        if expire <= 0:
            self.set_status(400)
            self.write("Error: expire time limit should be a number greater than 0")
            return

        userDoc = {
            "guid": newGuid,
            "expire": expire,
            "user": user
        }

        self.set_status(200)
        self.write(userDoc)
        cache.setex(newGuid, datetime.timedelta(10), json.dumps(userDoc))
        client.access.guids.insert_one(userDoc)
        

    def delete(self):
        self.set_status(400)
        self.write("Please specify the guid to delete as part of the request")

class betterRequestHandler(tornado.web.RequestHandler):
    def update_guids():
        guids = client.access.guids.find()
        for guid in guids:
            new_expire = guid["expire"] - 1
            if new_expire > 0:
                client.access.guids.update_one({"guid": guid["guid"]}, {"$set": {"expire": new_expire}}, upsert = True)
                cleanGuid = client.access.guids.find_one({"guid": guid["guid"]})
                userDoc = {
                    "guid": cleanGuid["guid"],
                    "expire": cleanGuid["expire"],
                    "user": cleanGuid["user"]
                }
                if cache.exists(guid["guid"]):
                    cache.set(guid["guid"], json.dumps(userDoc))
            else:
                client.access.guids.delete_one({"guid": guid["guid"]})
                if cache.exists(guid["guid"]):
                    cache.delete(guid["guid"])
    def post(self, uid):
        foundGuid = json.loads(cache.get(uid))
        if foundGuid == None:
            foundGuid = client.access.guids.find_one({"guid": uid})
        if foundGuid == None:
            uid = str(uid)
            if len(uid) != 32:
                self.set_status(400)
                self.write("Error: The guid should be 32 characters in length")
                return
            
            args = self.request.arguments
            user = None
            expire = None

            if 'user' in args:
                user = self.get_argument('user')
            if 'expire' in args:
                expire = self.get_argument('expire')

            if user == None:
                self.set_status(400)
                self.write("Error: Missing 'user' field in request data")
                return

            if expire == None:
                expire = 1427736345
            expire = int(expire)
            if expire <= 0:
                self.set_status(400)
                self.write("Error: expire time limit should be a number greater than 0")
                return

            userDoc = {
                "guid": uid,
                "expire": expire,
                "user": user
            }

            self.set_status(200)
            self.write(userDoc)
            cache.setex(uid, datetime.timedelta(10), json.dumps(userDoc))
            client.access.guids.insert_one(userDoc)
        else:
            args = self.request.arguments
            guid = foundGuid["guid"]
            expire = foundGuid["expire"]
            user = foundGuid["user"]
            if 'user' in args:
                user = self.get_argument('user')
                client.access.guids.update_one({"guid": uid}, {"$set": {"user": user}}, upsert = True)
            if 'expire' in args:
                expire = int(self.get_argument('expire'))
                client.access.guids.update_one({"guid": uid}, {"$set": {"expire": expire}}, upsert = True)
            userDoc = {
                "guid": guid,
                "expire": expire,
                "user": user
            }
            cache.setex(uid, datetime.timedelta(10), json.dumps(userDoc))
            self.set_status(200)
            self.write(userDoc)

        
    def delete(self, uid):
        findGuid = json.loads(cache.get(uid))
        if findGuid == None:
            findGuid = client.access.guids.find_one({"guid": uid})
        if findGuid == None:
            self.set_status(400)
            self.write("The given guid cannot be found in the database")
        else:
            if cache.exists(uid):
                cache.delete(uid)
            client.access.guids.delete_one({"guid": uid})
            self.set_status(200)
            self.write("The associated guid and its metadata has been removed from the system")

if __name__ == "__main__":
    app = tornado.web.Application([
        (r"/guid", basicRequestHandler),
        (r"/guid/([\w]+)?", betterRequestHandler)
    ])

    app.listen(8080)
    callback = tornado.ioloop.PeriodicCallback(betterRequestHandler.update_guids, 1000)
    callback.start()
    tornado.ioloop.IOLoop.current().start()