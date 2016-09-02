from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

# Connection setting
engine = create_engine('postgresql://sqldb:sqldb@localhost/students', echo=False)

# Create Base Class of DB
Base = declarative_base() 

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True)
    password_hash = Column(String(128))
    students = relationship('Student', backref='user')

    def __repr__(self):
        return  "<User %s>" % (self.username)

    @property
    def password(self):
        raise AttributionError('Password is not a readable attribute.')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_auth_token(self, expiration):
        s = Serializer('SECRET_KEY', expires_in=expiration)
        return s.dumps({"id":self.id})

    @staticmethod
    def verify_auth_token(token):
        s = Serializer('SECRET_KEY')
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def to_json(self):
        json_user = {
            "username": self.username
        }

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    name = Column(String(32))
    classes = Column(String(32))
    location = Column(String(32))
    user_id = Column(Integer, ForeignKey('users.id'))

    def __repr__(self):
        return "<Student %s>" % (self.name)

    def to_json(self):
        json_student = {
            "name": self.name,
            "classes": self.classes,
            "location": self.location
        }
        return json_student

# Method to initialize db in shell
# Create new or drop old ones
def create_all():
    Base.metadata.create_all(engine)

def drop_all():
    Base.metadata.drop_all(engine)