# add copyright later ..

import os

from swift.common.swob import Request, Response


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
        return Response(request=req, status=204, body="Deleted Tokens",
                        content_type="text/plain")

    def __call__(self, env, start_response):
        req = Request(env)
        if req.path == '/sw_admin':
            print("Shashi request = %s" %(req))
            handler = self.GET
            if self.disable_path and os.path.exists(self.disable_path):
                handler = self.DISABLED
            return handler(req)(env, start_response)
        return self.app(env, start_response)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def swadmin_filter(app):
        return SWAdminMiddleware(app, conf)
    return healthcheck_filter
