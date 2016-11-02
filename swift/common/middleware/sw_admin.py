# Copyright (c) 2016 Intel Corporation
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
from swift.common.utils import config_read_reseller_options, get_logger
from swift.common.swob import HTTPBadRequest, HTTPMethodNotAllowed, \
    HTTPUnauthorized, HTTPForbidden
import swift.common.memcached as memcached


class SWAdminMiddleware(object):
    """
    SW-Admin middleware used for Admin/Ops functions -
    e.g. deleting cached tokens.

    Admin/Ops use only :
    If the request path is /sw_admin, and 'sw_admin' in the pipeline
    is not set then it will respond with 412 "Bad URL" as the body.

    e.g. $ curl http://127.0.0.1:8080/sw_admin -X DELETE -H 'X-DELETE-TOKEN: \
    test:tester' -H 'x-auth-token: AUTH_tk90701b3135704effbab7d1438e2ed649'

    where value for 'X-DELETE-TOKEN' will be the 'account:user' for which
    tokens need to be deleted and 'X-AUTH-TOKEN' will have valid auth token
    for the op/admin making this delete request.

    e.g. changes to proxy-server.conf to add/enable sw_admin middleware-
    [pipeline:main]
    pipeline = catch_errors gatekeeper ...tempauth sw_admin ...

    [filter:sw_admin]
    use = egg:swift#sw_admin

    """

    def __init__(self, app, conf):
        self.app = app
        self.memcache_servers = conf.get('memcache_servers', '127.0.0.1:11211')
        self.memcache = memcached.MemcacheRing(
            [s.strip() for s in self.memcache_servers.split(',') if s.strip()])
        self.reseller_prefixes, self.account_rules = \
            config_read_reseller_options(conf, dict(require_group=''))
        self.logger = get_logger(conf, log_route='sw_admin')

    def delete_cache(self, req):
        """
        Deletes the cached auth token from memcached
        :param req: swob.Request object
        """
        user_id = req.headers.get('X-Delete-Token')
        try:
            if self.delete_cached_token(user_id):
                self.logger.info("Successfully Deleted Tokens")
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
        if req.path != '/sw_admin':
            return self.app(env, start_response)
        if 'swift.authorize' in env and env.get('reseller_request'):
            auth_response = env['swift.authorize'].__name__
            # Unauthorized, exit
            if auth_response.strip().lower() == 'denied_response':
                self.logger.error('Access was denied to this resource.')
                return HTTPForbidden(str('Access was denied to this '
                                         'resource.'))(env, start_response)
            try:
                handler = self.get_request_handler(req)
                return handler(req)(env, start_response)
            except ValueError as error:
                self.logger.error(str(error))
                return HTTPBadRequest(str(error))(env, start_response)
            except NotImplementedError as error:
                self.logger.error(str(error))
                return HTTPMethodNotAllowed(str(error), req=req, headers={
                    "Allowed": "DELETE"})(env, start_response)
            except (Exception):
                self.logger.exception('5XX Internal server error.')
                start_response('5XX Server Error',
                               [('Content-Type', 'text/plain')])
                return ['Internal server error.\n']
        else:
            self.logger.error('Denied Request, Unauthorized Access.')
            return HTTPUnauthorized(str("Denied Request, Unauthorized Access."
                                        "\n"))(env, start_response)

    def get_request_handler(self, req):
        """
        :param req: swob.Request object
        :return: request handler
        """
        if req.method == "DELETE":
            if req.headers.get('X-Delete-Token'):
                handler = self.delete_cache  # to delete cached tokens
            else:
                raise ValueError('DELETE request is missing '
                                 'X-Delete-Token header/value.\n')
        else:
            raise NotImplementedError(
                'Request method %s is not supported.\n' % (req.method))
        return handler

    def delete_cached_token(self, user_id):
        """ To delete cached token from memcache, for users who are no
        longer valid
        :param user_id:
        :return: boolean status
        """
        userid_key = '%s/user/%s' % (self.reseller_prefixes[0], user_id)
        token = self.memcache.get(userid_key)
        if token is None:
            raise ValueError(
                'Invalid Name/User does not exist: %s \n' % (user_id))
        result1 = self.memcache.delete(userid_key)
        result2 = self.memcache.delete('%s/token/%s' %
                                       (self.reseller_prefixes[0], token))
        return not result1 and not result2


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def swadmin_filter(app):
        return SWAdminMiddleware(app, conf)
    return swadmin_filter