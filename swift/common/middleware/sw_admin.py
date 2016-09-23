# Author: Shashirekha Gundur <shashirekha.j.gundur@intel.com>
# Copyright (c) 2016 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from swift.common.swob import Request, Response
from swift.common.utils import config_true_value
from swift.common.swob import HTTPBadRequest, HTTPMethodNotAllowed, HTTPUnauthorized
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
        if 'swift.authorize' in env and 'swift_owner' in env:
            response = env['swift.authorize'](req)
            #Unauthorized, exit
            if response:
                return HTTPUnauthorized(str(response))(env, start_response)
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
        else:
            return HTTPUnauthorized(req)(env, start_response)

    def get_request_handler(self, req):
        """
        :param req: swob.Request object
        :return: request handler
        """
        if self.enable_sw_admin:
            if req.method == "DELETE":
                if req.headers.get('X-DELETE-TOKEN'):
                    handler = self.DELETE_CACHE  # handler set to delete the cached tokens
                else:
                    raise ValueError(
                        'Request method DELETE is missing Headers/Header values.\n')
            else:
                raise NotImplementedError(
                    'Request method %s is not supported.\n' % (req.method))
            return handler
        # else:
        #     return Response(request=req, status=503, body="FEATURE DISABLED BY ADMIN",
        #                                             content_type="text/plain")

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
        if config_true_value(conf.get('enable_sw_admin', 'False')):
            return SWAdminMiddleware(app, conf)
        else:
            return app
    return swadmin_filter
