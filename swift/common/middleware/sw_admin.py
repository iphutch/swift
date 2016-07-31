## TODO, add copyright later ..

import os

from swift.common.swob import Request, Response
import swift.common.memcached as memcached


class SWAdminMiddleware(object):
    """
    SW-Admin middleware used for deleting cached tokens.

    If the path is /sw_admin, it will respond 200 with "OK" as the body.

    To invalidate/delete cached auth tokens.

    """

    def __init__(self, app, conf):
        self.app = app
        self.disable_path = conf.get('disable_path', '')

    def GET(self, req):
        """Returns a 200 response with "OK" in the body."""
        return Response(request=req, body="OK", content_type="text/plain")

    def DISABLED(self, req):
        """Returns a 503 response with "DISABLED BY FILE" in the body."""
        return Response(request=req, status=503, body="DISABLED BY FILE",
                        content_type="text/plain")

    def DELETE_CACHE(self, req):
        """ Deletes the cached auth tokens from memcached"""
        user_id = req.headers.get('X-DELETE-TOKEN')
        if self.delete_cached_token(user_id):
            return Response(request=req, status=204, body="Deleted Tokens",
                            content_type="text/plain")

    def __call__(self, env, start_response):
        req = Request(env)
        if req.path == '/sw_admin':
            if req.method == "DELETE" and req.headers.get('X-DELETE-TOKEN'):
                print("Shashi req.method DELETE")
                handler = self.DELETE_CACHE  # handler set to delete the cached tokens
            if self.disable_path and os.path.exists(self.disable_path):
                print("Shashi self.disable = %s" % (self.disable_path))
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
