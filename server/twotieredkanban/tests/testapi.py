from zope.testing import setupstack
import bobo
import json
import os
import pkg_resources
from testvars import Vars
from unittest import mock
import webtest

from ..site import get_site

from . import auth
from .sample import users

demo_db = '''
<zodb>
  <demostorage>
  </demostorage>
</zodb>
'''

here = os.path.dirname(__file__)

def make_app(config=demo_db):
    app = bobo.Application(
        bobo_resources="""
                       twotieredkanban.apibase
                       """,
        bobo_handle_exceptions = False,
    )
    return pkg_resources.load_entry_point(
        'zc.zodbwsgi', 'paste.filter_app_factory', 'main')(
            app, {},
            configuration = config,
            max_connections = '4',
            thread_transaction_manager = 'False'
        )

class APITests(setupstack.TestCase):

    maxDiff = None

    def setUp(self):
        self._app = make_app()
        with self._app.database.transaction() as conn:
            get_site(conn.root, 'localhost', 'Test site').auth = auth.Admin()

        self.app = self._test_app()
        self.vars = Vars()

    def _test_app(self, url=None):
        app = webtest.TestApp(self._app)
        app.extra_environ['HTTP_X_GENERATION'] = '0'
        if url:
            self.update_app(app, app.get(url))
        return app

    def update_app(self, app, resp):
        try:
            json = resp.json
        except Exception:
            pass
        else:
            updates = json.get('updates')
            if updates:
                app.extra_environ['HTTP_X_GENERATION'] = str(
                    updates['generation'])

        return resp

    def reset_generation(self):
        self.app.extra_environ.pop('HTTP_X_GENERATION', None)

    def get(self, *a, **kw):
        app = self.app
        return self.update_app(app, app.get(*a, **kw))

    def post(self, *a, **kw):
        app = self.app
        return self.update_app(app, app.post_json(*a, **kw))

    def put(self, *a, **kw):
        app = self.app
        return self.update_app(app, app.put_json(*a, **kw))

    def test_site_poll(self):
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      site=dict(users=[],
                                boards=[]),
                      user=users[0],
                      zoid=self.vars.zoid,
                      ),
                 ),
            self.get('/site/poll').json)

    def test_add_board(self):
        self.get('/site/poll') # set generation
        data = dict(name='Dev', title='Development',
                    description='Let us develop things')
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      site=dict(users=[],
                                boards=[data])
                      )
                 ),
            self.post('/site/boards', data).json)

        # We can also add a board in the context of a board
        self.app = self._test_app()
        self.get('/board/Dev/poll') # set generation
        data2 = dict(name='Dev2', title='Development 2',
                    description='Let us develop things again')
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation2,
                      board=dict(data, archive_count=0),
                      site=dict(users=[],
                                boards=[data, data2])
                      )
                 ),
            self.post('/board/Dev/boards', data2).json)

    def test_rename_board(self):
        with self._app.database.transaction() as conn:
            site = get_site(conn.root, 'localhost')
            site.add_board('t')
            site.add_board('tt')
        self.get('/board/t/poll')
        site_app = self._test_app('/site/poll')
        tt_app = self._test_app('/site/poll')
        r = self.put('/board/t/', dict(name='t2'))
        vars = Vars()
        self.assertEqual(dict(board=vars.board, site=vars.site,
                              generation=vars.g),
                         r.json['updates'])
        self.assertEqual(['t2', 'tt'],
                         [b['name'] for b in vars.site['boards']])
        self.assertEqual('t2', vars.board['name'])

    def test_add_project(self):
        self.post('/site/boards', dict(name='t', title='t', description=''))
        self.get('/board/t/poll') # set generation
        data = dict(title="do it", description="do the thing", order=42)
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.project])
                      )
                 ),
            self.post('/board/t/projects', data).json)
        for name in data:
            self.assertEqual(data[name], self.vars.project[name])

    def test_update_project(self):
        self.post('/site/boards', dict(name='t', title='t', description=''))
        r = self.post('/board/t/projects',
                      dict(title='t', description='d', order=42))
        id = r.json['updates']['tasks']['adds'][0]['id']

        data = dict(title="do it", description="do the thing")
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.project])
                      )
                 ),
            self.put('/board/t/tasks/' + id, data).json)
        for name in data:
            self.assertEqual(data[name], self.vars.project[name])

    def test_add_task(self):
        self.post('/site/boards', dict(name='t', title='t', description=''))
        r = self.post('/board/t/projects',
                      dict(title='t', description='d', order=42))
        id = r.json['updates']['tasks']['adds'][0]['id']
        data = dict(title="do it", description="do the thing", order=50,
                    size=1, blocked='no can do', assigned='test@example.com')
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.task])
                      )
                 ),
            self.post('/board/t/project/' + id, data).json)
        for name in data:
            self.assertEqual(data[name], self.vars.task[name])

    def get_states(self):
        self.post('/site/boards', dict(name='t', title='t', description=''))
        self.reset_generation()
        return self.get('/board/t/poll').json['updates']['states']['adds']

    def test_move_project_to_new_state(self):
        states = self.get_states()
        [backlog_id] = [s['id'] for s in states if s['title'] == 'Backlog']
        [dev_id] = [s['id'] for s in states if s['title'] == 'Development']
        r = self.post('/board/t/projects',
                      dict(title='t', description='d', order=42))
        id = r.json['updates']['tasks']['adds'][0]['id']
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.task])
                      )
                 ),
            self.put('/board/t/move/' + id,
                     dict(state_id=dev_id, order=7)).json)
        task = self.vars.task
        self.assertEqual(id, task['id'])
        self.assertEqual(dev_id, task['state'])
        self.assertEqual(7, task['order'])
        self.assertEqual(None, task['parent'])

    def test_move_task_to_new_project(self):
        states = self.get_states()
        r = self.post('/board/t/projects',
                      dict(title='p1', description='', order=1))
        p1id = r.json['updates']['tasks']['adds'][0]['id']
        r = self.post('/board/t/project/' + p1id,
                      dict(title='t1', description='', order=2))
        t1 = r.json['updates']['tasks']['adds'][0]
        r = self.post('/board/t/projects',
                      dict(title='p2', description='', order=3))
        p2id = r.json['updates']['tasks']['adds'][0]['id']
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.task])
                      )
                 ),
            self.put('/board/t/move/' + t1['id'], dict(parent_id=p2id)).json)
        task = self.vars.task
        self.assertEqual(t1['id'], task['id'])
        self.assertEqual(t1['state'], task['state'])
        self.assertEqual(t1['order'], task['order'])
        self.assertEqual(p2id, task['parent'])

    def test_move_task_to_new_working_state_gets_assigned(self):
        states = self.get_states()
        r = self.post('/board/t/projects',
                      dict(title='p1', description='', order=1))
        p1id = r.json['updates']['tasks']['adds'][0]['id']
        r = self.post('/board/t/project/' + p1id,
                      dict(title='t1', description='', order=2))
        t1 = r.json['updates']['tasks']['adds'][0]
        self.assertEqual(
            dict(updates=
                 dict(generation=self.vars.generation,
                      tasks=dict(adds=[self.vars.task])
                      )
                 ),
            self.put('/board/t/move/' + t1['id'],
                     dict(parent_id=p1id, state_id='Doing')
                     ).json)
        task = self.vars.task
        self.assertEqual(t1['id'], task['id'])
        self.assertEqual('Doing', task['state'])
        self.assertEqual(t1['order'], task['order'])
        self.assertEqual(p1id, task['parent'])
        self.assertEqual('jaci', task['assigned'])

    def test_auth(self):
        # Note that this test, like the ones above use a very dump
        # auth plugin. We're just testing for proper interaction with
        # the auth plugin.

        # unauthenticated users can't do anything and get redirected
        # to a login page
        with self._app.database.transaction() as conn:
            get_site(conn.root, 'localhost').auth = auth.Bad()
        app = self._test_app()
        r = app.get('/', status=302)
        self.assertEqual(r.headers['location'], 'http://localhost/auth/login')

        # Non admin users can't do admin things
        with self._app.database.transaction() as conn:
            get_site(conn.root, 'localhost').auth = auth.NonAdmin()
        app = self._test_app()
        r = self.app.post('/site/boards',
                          dict(name='test', title='', description=''),
                          status=403)

    def test_no_site(self):
        # When accessing a domain wo a site, we'll get redirected to a
        # route with a message saying that we're not ready.
        r = self.app.get('http://other.domain/', status=302)
        default_url = 'http://other.domain/not-yet'
        self.assertEqual(default_url, r.headers['location'])
        r = self.app.get(default_url, status=200)
        self.assertEqual("This site isn't available yet.", r.text)

        # We can configure a different route
        from ..apibase import config
        url = 'http://example.com'
        config(dict(no_site_url=url))
        r = self.app.get('http://other.domain/', status=302)
        self.assertEqual(url, r.headers['location'])

        # restore default_url
        config(dict(no_site_url=default_url))

    def test_archive_and_restore(self):
        vars = Vars()
        with self._app.database.transaction() as conn:
            site = get_site(conn.root, 'localhost')
            site.add_board('test', '', '')
            board = site.boards['test']
            board.new_project('p1', 0)
            [p1] = board.tasks
            board.new_task(p1.id, 't1', 1)
            board.new_task(p1.id, 't2', 2)
            task_ids = sorted(t.id for t in board.tasks)
            board.new_project('p2', 3)

        self.get('/board/test/poll') # set generation

        r = self.app.post('/board/test/archive/' + p1.id)
        updates = r.json['updates']
        self.assertEqual(dict(archive_count=1,
                              description='', name='test', title=''),
                         updates['board'])
        self.assertEqual(dict(removals=vars.removals), updates['tasks'])
        self.assertEqual(sorted(vars.removals), task_ids)

        r = self.app.delete('/board/test/archive/' + p1.id)
        updates = r.json['updates']
        self.assertEqual(dict(archive_count=0,
                              description='', name='test', title=''),
                         updates['board'])
        self.assertEqual(dict(adds=vars.restores), updates['tasks'])
        self.assertEqual(sorted(t['id'] for t in vars.restores), task_ids)


    def test_remove(self):
        vars = Vars()
        with self._app.database.transaction() as conn:
            site = get_site(conn.root, 'localhost')
            site.add_board('test', '', '')
            board = site.boards['test']
            board.new_project('p1', 0)
            [p1id] = [t.id for t in board.tasks]

        self.get('/board/test/poll') # set generation

        r = self.app.delete('/board/test/tasks/' + p1id)
        updates = r.json['updates']
        self.assertEqual(dict(generation=vars.generation,
                              tasks=dict(removals=[p1id])),
                         r.json['updates'])

        with self._app.database.transaction() as conn:
            site = get_site(conn.root, 'localhost')
            board = site.boards['test']
            self.assertEqual(0, len(board.tasks))

    def load_sample(self, f, nfeatures=None, nusers=None):
        from . import sample
        with self._app.database.transaction() as conn:
            site = get_site(conn.root, 'localhost')
            if nusers:
                site.update_users(sample.users[:nusers])
            else:
                site.update_users(sample.users)
            board = site.add_board(sample.boards[0]['name'])
            feature_ids = {}
            for task in sample.tasks:
                if 'parent' not in task:
                    if nfeatures is not None and len(feature_ids) == nfeatures:
                        continue

                    feature = board.new_feature(
                        task['title'], task['order'], task['description'])
                    feature_ids[task['id']] = feature.id

            for task in sample.tasks:
                if task.get('parent') in feature_ids:
                    board.new_task(
                        feature_ids[task['parent']], task['title'],
                                    task['order'], task['description'],
                        task['size'])

            if f is not None:
                f(board)

    @mock.patch('uuid.uuid1')
    @mock.patch('twotieredkanban.board.now')
    def test_export(self, now, uuid1):
        now.return_value = '2017-06-08T10:02:00.004'
        uuid1.side_effect = FauxUUID()
        def f(board):
            [fid] = [f.id for f in board.tasks if f.title == "Prototype board"]
            board.archive_feature(fid)
        self.load_sample(f, 2, 2)
        with open(os.path.join(here, 'sample-export.json')) as f:
            self.assertEqual(
                json.load(f),
                self.get('/board/sample/export').json)

        # Non admin users can't export
        with self._app.database.transaction() as conn:
            get_site(conn.root, 'localhost').auth = auth.NonAdmin()

        self.get('/board/sample/export', status=403)


class FauxUUID:

    def __init__(self, id=0):
        self.id = id

    def __call__(self):
        self.id += 1
        return self.__class__(self.id)

    @property
    def hex(self):
        return hex(self.id)[2:]
