import os.path
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import json

# Import the engine to bind
from sqlalchemy.orm import scoped_session, sessionmaker
from models import engine, Student, User

from tornado.options import define, options
define("port", default=8000, help="run on the given port", type=int)

# Initialize the Application
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
            (r"/login", LoginHandler),
            (r"/register", RegisterHandler),
            (r"/logout", LogoutHandler),
            (r"/students/add", StudentsAddHandler),
            # (r"/students/edit", StudentsEditHandler),
            (r"/students", StudentShowHandler),
            # (r"/students/remove", StudentsRemoveHandler),
            (r"/token", GetTokenHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret="you will never guess",
            login_url="/login",
            debug=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        self.db = scoped_session(sessionmaker(bind=engine))

# Base class - setring db and gain auth info
class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        user_id = self.get_secure_cookie("user")
        if not user_id: return None
        return self.db.query(User).get(user_id)

    def any_user_exists(self):
        return bool(self.db.query(User).get(user_id))

class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('index.html')

class RegisterHandler(BaseHandler):
    def get(self):
        self.render('register.html', error=None)

    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        user = self.db.query(User).filter_by(username=username).first()
        if user is not None:
            self.render("register.html", error= \
                "This username has been used. PLease try another username.")
        user = User(username=username, password=password)
        self.db.add(user)
        self.db.commit()
        self.set_secure_cookie("user", str(user.id))
        self.redirect(self.get_argument("next", "/"))


class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html', error=None)

    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        user = self.db.query(User).filter_by(username=username).first()
        if not user:
            self.render("login.html", error="This user doesn't exist")
        if user.verify_password(password):
            self.set_secure_cookie("user", str(user.id))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="Incorrect password" )

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))

class StudentsAddHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = self.get_argument('name')
        classes = self.get_argument('classes')
        location = self.get_argument('location')
        student = Student(name=name, classes=classes, \
            location=location, user=self.get_current_user())
        self.db.add(student)
        self.db.commit()
        self.redirect(self.get_argument("next","/"))

class StudentShowHandler(BaseHandler):
    def get(self):
        response = [ student.to_json() for student in students ]
        self.write(json.dumps(response, indent=4))
        

if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
