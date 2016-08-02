### TODO - add Copyright


import os
import shutil
import tempfile
import unittest

from swift.common.swob import Request, Response
from swift.common.middleware import sw_admin


class FakeApp(object):
    def __call__(self, env, start_response):
        req = Request(env)
        return Response(request=req, body='FAKE APP')(
            env, start_response)


class TestSWAdmin(unittest.TestCase):

    def setUp(self):
        self.enable_sw_admin = self.get_app(FakeApp(), {}).enable_sw_admin
        self.got_statuses = []

    def get_app(self, app, global_conf, **local_conf):
        factory = sw_admin.filter_factory(global_conf, **local_conf)
        return factory(app)

    def start_response(self, status, headers):
        self.got_statuses.append(status)

    def test_swadmin(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'test_sw_admin'
        })
        app = self.get_app(FakeApp(), {})
        resp = app(req.environ, self.start_response)
        self.assertEqual(['204 No Content'], self.got_statuses)
        self.assertEqual(resp, ['Deleted Tokens'])

    def test_swadmin_pass(self):
        req = Request.blank('/', environ={'REQUEST_METHOD': 'DELETE'})
        app = self.get_app(FakeApp(), {})
        resp = app(req.environ, self.start_response)
        self.assertEqual(['200 OK'], self.got_statuses)
        self.assertEqual(resp, ['FAKE APP'])

    def test_swadmin_pass_not_disabled(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'test_sw_admin'
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['204 No Content'], self.got_statuses)
        self.assertEqual(resp, ['Deleted Tokens'])

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

    def test_delete_cached_token(self):
        self.enable_sw_admin = True
        req = Request.blank('/sw_admin', environ={
            'REQUEST_METHOD': 'DELETE'}, headers={
            'X-DELETE-TOKEN': 'test_sw_admin'
        })
        app = self.get_app(FakeApp(), {}, enable_sw_admin=self.enable_sw_admin)
        resp = app(req.environ, self.start_response)
        self.assertEqual(['204 No Content'], self.got_statuses)
        self.assertEqual(resp, ['Deleted Tokens'])


if __name__ == '__main__':
    unittest.main()
