## TODO, add copyright later ..

from swift.common.swob import Request, Response
from swift.common.utils import config_true_value
from swift.common.swob import HTTPBadRequest, HTTPMethodNotAllowed
import swift.common.memcached as memcached


class SWAdminMiddleware(object):
    """
    SW-Admin middleware used for deleting cached tokens.

    Admin/Op use only :
    If the path is /sw_admin, and  'enable_sw_admin' in the proxy-server.conf is set to 'false'
    it will respond with 503 "FEATURE DISABLED BY ADMIN" as the body.

    To invalidate/delete cached auth tokens, set 'enable_sw_admin' to 'true' and use below command

    e.g. $ curl http://127.0.0.1:8080/sw_admin -X DELETE -H 'X-DELETE-TOKEN: test:tester'

    where value for 'X-DELETE-TOKEN' will be the 'account:user' for which tokens need to be deleted

    e.g. changes to proxy-server.conf to add/enable sw-admin middleware-
    [pipeline:main]
    pipeline = catch_errors gatekeeper healthcheck sw_admin proxy-logging ...

    [filter:sw_admin]
    use = egg:swift#sw_admin
    enable_sw_admin = true

    """

    def __init__(self, app, conf):
        self.app = app
        self.enable_sw_admin = config_true_value(conf.get('enable_sw_admin', 'False'))
        self.memcache = memcached.MemcacheRing(['127.0.0.1:11211'])

    def DISABLED(self, req):
        """
        Returns a 503 response with "DISABLED BY ADMIN" in the body.
        :param req: swob.Request object
        """
        return Response(request=req, status=503, body="FEATURE DISABLED BY ADMIN",
                        content_type="text/plain")

    def DELETE_CACHE(self, req):
        """
        Deletes the cached auth tokens from memcached
        :param req: swob.Request object
        """
        user_id = req.headers.get('X-DELETE-TOKEN')
        try:
            if self.delete_cached_token(user_id):
                return Response(request=req, status=204, body="Deleted Tokens",
                            content_type="text/plain")
        except ValueError as error:
            return Response(request=req, status=404, body=error.message,
                            content_type="text/plain")

    def __call__(self, env, start_response):
        """
        WSGI entry point.
        Wraps env in swob.Request object and passes it down.

        :param env: WSGI environment dictionary
        :param start_response: WSGI callable
        """
        req = Request(env)
        try:
            if req.path == '/sw_admin':
                handler = self.get_request_handler(req)
                return handler(req)(env, start_response)
            return self.app(env, start_response)
        except ValueError as error:
            return HTTPBadRequest(str(error))(env, start_response)
        except NotImplementedError as error:
            return HTTPMethodNotAllowed(str(error),
                req=req, headers={"Allowed": "DELETE"})(env, start_response)
        except (Exception):
            start_response('5XX Server Error',
                           [('Content-Type', 'text/plain')])
            return ['Internal server error.\n']

    def get_request_handler(self, req):
        """
        :param req: swob.Request object
        :return: request handler
        """
        handler = self.DISABLED

        if self.enable_sw_admin:
            if req.method == "DELETE":
                if req.headers.get('X-DELETE-TOKEN'):
                    print("Shashi req.method DELETE")
                    handler = self.DELETE_CACHE  # handler set to delete the cached tokens
                else:
                    print("Shashi req.method DELETE , missing Headers/Header values")
                    raise ValueError(
                        'Request method DELETE is missing Headers/Header values.\n')
            else:
                print("Shashi , sw_admin %s request method not supported" % (req.method))
                raise NotImplementedError(
                    'Request method %s is not supported.\n' % (req.method))
        else:
            print("Shashi, swift_admin middleware not enabled; enable_sw_admin = %s" % (self.enable_sw_admin))
            handler = self.DISABLED
        return handler

    def delete_cached_token(self, user_id):
        """ To delete cached tokens from memcache, for users who are no longer valid
        :param user_id:
        :return: boolean status
        """
        token = self.memcache.get('AUTH_/user/%s' % (user_id))
        if token is None:
            raise ValueError(
                'Invalid Account Name: %s \n' % (user_id))

        result1 = self.memcache.delete('AUTH_/user/%s' % (user_id))
        result2 = self.memcache.delete('AUTH_/token/%s' % (token))
        if result1 == None and result2 == None:
            return True
        else:
            return False

def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def swadmin_filter(app):
        return SWAdminMiddleware(app, conf)
    return swadmin_filter
