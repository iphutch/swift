## TODO, add copyright later ..

import os

from swift.common.swob import Request, Response
from swift.common.utils import config_true_value
import swift.common.memcached as memcached


class SWAdminMiddleware(object):
    """
    SW-Admin middleware used for deleting cached tokens.

    If the path is /sw_admin, it will respond 200 with "OK" as the body.

    To invalidate/delete cached auth tokens.

    """

    def __init__(self, app, conf):
        self.app = app
        self.enable_sw_admin = config_true_value(conf.get('enable_sw_admin', 'False'))

    def GET(self, req):
        """Returns a 200 response with "OK" in the body."""
        return Response(request=req, body="OK", content_type="text/plain")

    def DISABLED(self, req):
        """Returns a 503 response with "DISABLED BY ADMIN" in the body."""
        return Response(request=req, status=503, body="FEATURE DISABLED BY ADMIN",
                        content_type="text/plain")

    def DELETE_CACHE(self, req):
        """ Deletes the cached auth tokens from memcached"""
        user_id = req.headers.get('X-DELETE-TOKEN')
        try:
            if self.delete_cached_token(user_id):
                return Response(request=req, status=204, body="Deleted Tokens",
                            content_type="text/plain")
        except ValueError as error:
            return Response(request=req, status=404, body=error.message,
                            content_type="text/plain")

    def __call__(self, env, start_response):
        req = Request(env)
        print("Shashi enable_sw_admin = %s" % (self.enable_sw_admin))
        handler = self.DISABLED
        if req.path == '/sw_admin':
            if self.enable_sw_admin:
                if req.method == "DELETE" and req.headers.get('X-DELETE_TOKEN'):
                    print("Shashi req.method DELETE")
                    handler = self.DELETE_CACHE # handler set to delete the cached tokens
            else:
                print("Shashi, swift_admin middleware not enabled; enable_sw_admin = %s" % (self.enable_sw_admin))
                handler = self.DISABLED
            return handler(req)(env, start_response)
        return self.app(env, start_response)

    def delete_cached_token(self, user_id):
        """  Admin/Op use only : To delete cached tokens from memcache, for users who are no longer valid
        :param user_id:
        :return:
        """
        memcache = memcached.MemcacheRing(['127.0.0.1:11211'])
        token = memcache.get('AUTH_/user/%s' % (user_id))
        if token is None:
            raise ValueError(
                'Invalid account_name name: %s' % (user_id))
        result1 = memcache.delete('AUTH_/user/%s' % (user_id))
        result2 = memcache.delete('AUTH_/token/%s' % (token))
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
