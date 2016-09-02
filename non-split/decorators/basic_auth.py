import tornado.ioloop
import tornado.web
import base64

import base64
 
def _checkAuth(login, password):
    ''' Check user can access or not to this element '''
    # TODO: return None if user is refused
    # TODO: do database check here, to get user.
    return {
        'login': 'okay',
        'password': 'okay',
        'role': 'okay'
    }
 
def httpauth(handler_class):
    ''' Handle Tornado HTTP Basic Auth '''
    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):
            auth_header = handler.request.headers.get('Authorization')
 
            if auth_header is None or not auth_header.startswith('Basic '):
                handler.set_status(401)
                handler.set_header('WWW-Authenticate', 'Basic realm=Restricted')
                handler._transforms = []
                handler.finish()
                return False
 
            auth_decoded    = base64.decodestring(auth_header[6:])
            login, password = auth_decoded.split(':', 2)
            auth_found      = _checkAuth(login, password)
 
            if auth_found is None:
                handler.set_status(401)
                handler.set_header('WWW-Authenticate', 'Basic realm=Restricted')
                handler._transforms = []
                handler.finish()
                return False
            else:
                handler.request.headers.add('auth', auth_found)
 
            return True
 
        def _execute(self, transforms, *args, **kwargs):
            if not require_auth(self, kwargs):
                return False
            return handler_execute(self, transforms, *args, **kwargs)
 
        return _execute
 
    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class

@httpauth
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        thi =  self.request.headers.get('auth')
        self.write("%s, ok" % thi)

application = tornado.web.Application([
    (r"/", MainHandler),
])

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()