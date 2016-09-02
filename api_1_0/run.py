import os.path
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.escape
import tornado.httpclient
import json
from tornado import gen
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
from math import ceil

# PostgreSQL paired with SQLAlchemy
# Import the engine to bind
from sqlalchemy.orm import scoped_session, sessionmaker
from models import engine, Student, User

from tornado.options import define, options
define("port", default=8000, help="run on the given port", type=int)

# Initialize the Application
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/api/v1", IndexHandler),
            (r"/api/v1/login", LoginHandler),
            (r"/api/v1/logout", LogoutHandler),
            (r"/api/v1/token", GetTokenHandler),
            (r"/api/v1/students/(\d+)", GetStudentsHandler),
            (r"/api/v1/students/(\d+)", ManageStudentHandler),
            ('.*', PageNotFoundHandler),
        ]
        settings = dict(
            cookie_secret="SECRET_KEY",
            debug=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        self.db = scoped_session(sessionmaker(bind=engine))

# Base class - setring db and gain auth info
class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    # Tornado's default way cannot receive data in json form
    # So DIY one
    def get_json_argument(self, name, default=None):
        args = tornado.escape.json_decode(self.request.body)
        name = tornado.escape.to_unicode(name)
        if name in args:
            return args[name]
        elif default is not None:
            return default
        else:
            raise MissingArgumentError(name)

    # A way only available for testing
    def get_current_user(self):
        access_token = self.get_secure_cookie("access_token")
        if not access_token: return None
        return User.verify_auth_token(access_token)

    # Acquire and checking an access token in json form
    # Better to wrap auth func into a decorator
    def get_current_user_via_token(self, access_token):
        access_token = get_json_argument(self, access_token)
        if not access_token: return None
        return User.verify_auth_token(access_token)

    def set_default_headers(self):
        self.set_header('Content-type','application/json;charset=utf-8')

# Error - 404 handler
class PageNotFoundHandler(tornado.web.RequestHandler):
    def get(self):
        response = {"error": 404}
        self.write(json.dumps(response, indent=4)) 
        # raise tornado.web.HTTPError(404)

# Return all api
class IndexHandler(BaseHandler):
    def get(self):
        user = self.get_current_user()
        if user:
            response = {"user": user.username}
            self.write(response)
        else:
            self.write(json.dumps(response, indent=4)) 

# Use username and password to login and store access token in cookie
# but wouldn't return an access token
# it's not necessary to keep only one valid access token
# if store it in secure_cookie(assuming it's absolutely safe)
class LoginHandler(BaseHandler):
    def post(self, token=None):
        if self.get_current_user():
            self.write({"failed": "You have loged in already."})
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)
        if username:
            user = self.db.query(User).filter_by(username=username).first()
            if user.verify_password(password):
                token = user.generate_auth_token(3600)
                response = {
                    "success":"You have log in.",
                }
                self.set_secure_cookie("access_token", token)
            else:
                response = {"failed": "Incorrect password"}
        else:
            response = {"failed" : "This user doesn't exist."}
        self.write(json.dumps(response, indent=4)) 

# Log out through clear cookie
# Or clear local storge at frontend
class LogoutHandler(BaseHandler):
    def get(self):
        if (self.get_argument("logout", None)):
            self.clear_cookie("access_token")
            response = {"success": "Log out safely."}
            self.write(json.dumps(response, indent=4)) 

# Use username and password to login and return an access token
# Only one valid access token available for one user at the same time
# Store access token in via Redis TTL, if it's not expired
# then return it back to user
class GetTokenHandler(BaseHandler):
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        user = self.db.query(User).filter_by(username=username).first()
        if not user:
            response = {"failed" : "This user doesn't exist."}
        if user:
            if user.verify_password(password):
                user_token = "user_token."+str(user.id)
                r = redis.StrictRedis()
                if r.ttl(user_token) != -2:
                    response = {
                        "access_token":str(r.get(user_token)),
                    }
                else:    
                    token = user.generate_auth_token(3600)
                    response = {
                        "access_token":str(token),
                    }
                    r.set(user_token, token, 3600)
            else:
                response = {"failed": "Incorrect password"}
        self.write(json.dumps(response, indent=4)) 

class GetStudentsHandler(BaseHandler):
    # Get students' list
    @tornado.gen.coroutine
    def get(self， page=None):
        user = self.get_current_user()
        if user:
            students = user.students
            if page:
                page_num = ceil(len(students)/10.0)
                if page > page_num and len(students)<10:
                    response = {"error": "Requested page index out of range or less than 10 students"}
                    self.write(response)
                else:
                    query = students.ordery_by(Student.id).all()
                    query = query.slice(page*10+1, (page+1)*10)
                    response = {
                        "success": "%s's students' list, page %s" %(user.username, page),
                        "student_list": [ query.to_json() for student in students ]
                    }
            else:
                response = {
                    "success": "%s's students' list" %(user.username),
                    "student_list": [ student.to_json() for student in students ]
                }   
        else:
            response = {"failed": "You have to login first."}
        self.write(json.dumps(response, indent=4))

    # Send new student's info in json form
    def post(self):
        user = self.get_current_user()
        if user:
            name = self.get_json_argument('name')
            classes = self.get_json_argument('classes')
            location = self.get_json_argument('location')
            student = Student(name=name, classes=classes, \
                location=location, user=user)
            self.db.add(student)
            self.db.commit()
            response = {"success": "Add student successful."}
        else:
            response = {"failed": "You have to login first."}
        self.write(json.dumps(response, indent=4))

class ManageStudentHandler(BaseHandler):
    # Delete student's info
    def delete(self, id):
        user = self.get_current_user()
        if user:
            student = self.db.query(Student).filter_by(id=id).first()
            if student.id in [member.id for member in user.students]:
                self.db.delete(student)
                self.db.commit()
                response = {"success": "You have remove this student info."}
            else:
                response = {"failed": "You cannot delete other's student info."}
        else:
            response = {"failed": "You have to login first."}
        self.write(response)

    # Update student's info
    def put(self, id):
        user = self.get_current_user()
        if user:
            student = self.db.query(Student).filter_by(id=id).first()
            if student.id in [member.id for member in user.students]:
                student.name = self.get_json_argument('name')
                student.classes = self.get_json_argument('classes')
                student.location = self.get_json_argument('location')
                self.db.add(student)
                self.db.commit()
                response = {"success": "You have update this student's info."}
            else:
                response = {"failed": "You cannot update other's student info."}
        else:
            response = {"failed": "You have to login first."}
        self.write(response)           


if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
