import persistent
import zc.generationalset

from .board import Board

class Site(persistent.Persistent):

    id = 'site'

    # List of users as seen by the client.  This is a view on actial
    # user data managed by the auth plugin.  It's assumed that the
    # number of users is limited.
    users = ()

    def __init__(self):
        from BTrees.OOBTree import BTree
        self.boards = BTree()
        self.changes = changes = zc.generationalset.GSet()
        self.changes.add(self)

    def json_reduce(self):
        return dict(
            users=self.users,
            boards=[dict(name=board.name,
                         title=board.title,
                         description=board.description)
                    for board in self.boards.values()],
            )

    def update_users(self, users):
        self.users = list(users)
        self.changes.add(self)
        for board in self.boards.values():
            board.site_changed()

    def add_board(self, name, title, description):
        for board in self.boards.values():
            board.site_changed()
        self.boards[name] = Board(self, name, title, description)
        self.changes.add(self)

    def updates(self, generation):
        updates = self.changes.generational_updates(generation)
        if len(updates) > 1:
            [site] = updates['adds']
            return dict(site=site, generation=updates['generation'])
        return updates

    @property
    def generation(self):
        return self.changes.generation
