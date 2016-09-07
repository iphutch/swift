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

import unittest
from time import time
from eventlet import Timeout
from contextlib import contextmanager
from swift.common.swob import Request, Response, HTTPRequestTimeout
from swift.common.middleware import sw_admin

class FakeApp(object):

    def __init__(self, fakememcache=None):
        self.memcache = fakememcache

    def __call__(self, env, start_response):
        req = Request(env)
        return Response(request=req, body='FAKE APP')(
            env, start_response)

class FakeMemcacheRing(object):

    def __init__(self, io_timeout= 2.0):
        self.store = {}
        self._io_timeout = io_timeout
        self.forceTimeout = False

    def get(self, key):
        return self.store.get(key)

    def set(self, user_id='foo'):
        self.store['AUTH_/user/%s' % user_id] = 'dummy_token'
        self.store['AUTH_/token/dummy_token'] = 'dummy_value'
        return True

    def incr(self, key, time=0):
        self.store[key] = self.store.setdefault(key, 0) + 1
        return self.store[key]

    @contextmanager
    def soft_lock(self, key, timeout=0, retries=5):
        yield True

    def delete(self, key):
        try:
            with Timeout(self._io_timeout):
                if self.forceTimeout:
                    time.sleep(5)
                del self.store[key]
                return
        except (Exception, Timeout) as e:
            raise HTTPRequestTimeout


class TestSWAdmin(unittest.TestCase):

    def setUp(self):
        self.enable_sw_admin = self.get_app(FakeApp(), {}).enable_sw_admin
        self.got_statuses = []

    def get_app(self, app, global_conf, **local_conf):
        factory = sw_admin.filter_factory(global_conf, **local_conf)
        return factory(app)

    def start_response(self, status, headers):
        self.got_statuses.append(status)

    # pass case , 200 OK
    def test_swadmin_pass(self):
        req = Request.blank('/', environ={'REQUEST_METHOD': 'DELETE'})
        app = self.get_app(FakeApp(), {})
        resp = app(req.environ, self.start_response)
        self.assertEqual(['200 OK'], self.got_statuses)
        self.assertEqual(resp, ['FAKE APP'])

    # fail with enable_sw_admin disabled/set to False
    def test_swadmin_pass_disabled(self):
        self.enable_sw_admin = False
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'test_sw_admin'
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['503 Service Unavailable'], self.got_statuses)
        self.assertEqual(resp, ['FEATURE DISABLED BY ADMIN'])

    # test_delete_cached_token 1, pass with valid inputs
    def test_delete_cached_token_pass(self):
        self.enable_sw_admin = True
        fakememcache = FakeMemcacheRing()
        user_id = 'foo'
        fakememcache.set(user_id)
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'foo'
        })
        resp = app(req.environ, self.start_response)
        self.assertEqual(['204 No Content'], self.got_statuses)
        self.assertEqual(resp, ['Deleted Tokens'])

    # test_delete_cached_token 2, fail for invalid inputs for account/user_id
    def test_delete_cached_token_fail_token_error(self):
        self.enable_sw_admin = True
        fakememcache = FakeMemcacheRing()
        user_id = 'foo'
        fakememcache.set(user_id)
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'not_foo'
        })
        resp = app(req.environ, self.start_response)
        self.assertEqual(['404 Not Found'], self.got_statuses)
        self.assertEqual(resp, ['Invalid Account Name: not_foo \n'])

    # test_delete_cached_token 3, fail by server timeout exception
    def test_delete_cached_token_fail_memcache_error(self):
        self.enable_sw_admin = True
        fakememcache = FakeMemcacheRing(io_timeout= 0.0)
        user_id = 'foo'
        fakememcache.set(user_id)
        fakememcache.forceTimeout = True
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'foo'
        })
        resp = app(req.environ, self.start_response)
        self.assertEqual(['5XX Server Error'], self.got_statuses)
        self.assertEqual(resp,['Internal server error.\n'])


    # test_delete_cached_token 4, fail with invalid header inputs
    def test_delete_cached_token_fail_missing_header_value(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': ''
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['400 Bad Request'], self.got_statuses)
        self.assertEqual(resp, ['Request method DELETE is missing Headers/Header values.\n'])

    # test_delete_cached_token 5, fail with missing header input
    def test_delete_cached_token_fail_missing_header(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['400 Bad Request'], self.got_statuses)
        self.assertEqual(resp, ['Request method DELETE is missing Headers/Header values.\n'])

    # test_delete_cached_token 6, fail with incorrect request method
    def test_delete_cached_token_fail_incorrect_method(self):
        self.enable_sw_admin = True
        #allowed_methods = ['DELETE']
        #not_allowed_methods = ['PUT', 'HEAD', 'GET', 'POST']
        method = 'PUT'
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': method
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['405 Method Not Allowed'], self.got_statuses)
        self.assertEqual(resp, ['Request method %s is not supported.\n' % (method)])

if __name__ == '__main__':
    unittest.main()
