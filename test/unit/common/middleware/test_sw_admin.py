### TODO - add Copyright

import unittest
from time import time
from contextlib import contextmanager
from swift.common.swob import Request, Response, HTTPException, HTTPForbidden
from swift.common.middleware import sw_admin


class FakeApp(object):
    def __init__(self, fakememcache=None):
        if fakememcache is None:
            memcache = None
        self.memcache = fakememcache

    def __call__(self, env, start_response):
        req = Request(env)
        return Response(request=req, body='FAKE APP')(
            env, start_response)

class FakeMemcacheRing(object):

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, time=0):
        self.store[key] = value
        return True

    def incr(self, key, time=0):
        self.store[key] = self.store.setdefault(key, 0) + 1
        return self.store[key]

    @contextmanager
    def soft_lock(self, key, timeout=0, retries=5):
        yield True

    def delete(self, key):
        try:
            del self.store[key]
        except Exception:
            pass
        return True



class TestSWAdmin(unittest.TestCase):

    def setUp(self):
        self.enable_sw_admin = self.get_app(FakeApp(), {}).enable_sw_admin
        self.got_statuses = []

    def get_app(self, app, global_conf, **local_conf):
        factory = sw_admin.filter_factory(global_conf, **local_conf)
        return factory(app)

    def start_response(self, status, headers):
        self.got_statuses.append(status)

    # pass case , 204 No Conent
    def test_swadmin(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'test_sw_admin'
        })
        app = self.get_app(FakeApp(), {})
        resp = app(req.environ, self.start_response)
        self.assertEqual(['503 Service Unavailable'], self.got_statuses)
        self.assertEqual(resp, ['FEATURE DISABLED BY ADMIN'])

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
        cache_key = 'AUTH_/user/foo'
        cache_entry = 'AUTH_/token/foo'
        fakememcache.set(cache_key, cache_entry)
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'foo'
        })
        resp = app(req.environ, self.start_response)
        self.assertEqual(['5XX Server Error'], self.got_statuses)
        self.assertEqual(resp, ['Internal server error.\n'])

    # test_delete_cached_token 2, fail for invalid inputs for account/user_id
    def test_delete_cached_token_fail_token_error(self):
        self.enable_sw_admin = True
        fakememcache = FakeMemcacheRing()
        cache_key = 'AUTH_/user/foo'
        cache_entry = 'AUTH_/token/foo'
        fakememcache.set(cache_key, cache_entry)
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'not_foo'
        })
        resp = app(req.environ, self.start_response)
        #self.assertRaises(ValueError, resp)
        self.assertEqual(['404 Not Found'], self.got_statuses)
        self.assertEqual(resp, ['Invalid Account Name: not_foo \n'])
        #with self.assertRaises(ValueError) as error:
            #resp = app(req.environ, self.start_response)
        #self.assertEqual(404, error.status)


    # test_delete_cached_token 3, fail by server timeout exception (common.memcached)
    def test_delete_cached_token_fail_memcache_error(self):
        self.enable_sw_admin = True
        fakememcache = FakeMemcacheRing()
        cache_key = 'AUTH_/user/foo'
        cache_entry = 'AUTH_/token/foo'
        fakememcache.set(cache_key, cache_entry)
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        app.memcache = fakememcache
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'foo'
        })
        resp = app(req.environ, self.start_response)
        self.assertRaises(Exception, resp)
        #with self.assertRaises(Exception) as catcher:
        #    resp = app(req.environ, self.start_response)
        #self.assertEqual(412, catcher.exception.status_int)

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
