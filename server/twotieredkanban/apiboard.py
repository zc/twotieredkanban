import bobo
import datetime
import json
import logging
import time
import webob

from . import email
from .apiutil import Sync, get, post, put

logger = logging.getLogger(__name__)

@bobo.scan_class
class Board(Sync):

    @post("/releases")
    def add_release(self, name, description, order):
        self.context.new_release(name, description=description, order=order)
        return self.response()

    @put("/releases/:release_id")
    def update_release(self, release_id, name=None, description=''):
        self.context.update_task(release_id, name, description)
        return self.response()

    @put("/move/:task_id")
    def move(self, task_id, parent_id, state, order):
        self.context.transition(task_id, parent_id, state, order)
        return self.response()

    @post("/releases/:release_id")
    def add_task(self, release_id, name, order,
                 description='', size=1, blocked='', assigned=None):
        task = self.context.new_task(
            release_id, name, description=description,
            size=size, blocked=blocked, assigned=assigned,
            order=order,
            )
        if assigned:
            email.sent(self.connection.transaction_manager.get(),
                       assigned, task_id=task.id)
        return self.response()

    @put("/tasks/:task_id")
    def update_task(self, task_id, name=None,
                    description=None, size=None, blocked=None, assigned=None,
                    ):
        self.context.update_task(
            task_id, name=name, description=description,
            size=size, blocked=blocked, assigned=assigned)
        return self.response()

    # @delete("/tasks/:task_id")
    # def delete_task(self, request, task_id):
    #     self.context.archive_task(task_id)
    #     return self.response()