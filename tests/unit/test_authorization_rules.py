from taskmanager.models import Project, Task, User
from taskmanager.services.auth import can_delete_task


def _user(id: int) -> User:
    return User(id=id, email=f"u{id}@example.com", display_name=f"User {id}")


def test_creator_can_delete():
    creator = _user(1)
    task = Task(id=1, project_id=1, created_by_id=1, assignee_id=None)
    project = Project(id=1, owner_id=99)
    assert can_delete_task(creator, task, project) is True


def test_assignee_can_delete():
    assignee = _user(2)
    task = Task(id=1, project_id=1, created_by_id=1, assignee_id=2)
    project = Project(id=1, owner_id=99)
    assert can_delete_task(assignee, task, project) is True


def test_project_owner_can_delete():
    owner = _user(99)
    task = Task(id=1, project_id=1, created_by_id=1, assignee_id=2)
    project = Project(id=1, owner_id=99)
    assert can_delete_task(owner, task, project) is True


def test_unrelated_user_cannot_delete():
    bystander = _user(3)
    task = Task(id=1, project_id=1, created_by_id=1, assignee_id=2)
    project = Project(id=1, owner_id=99)
    assert can_delete_task(bystander, task, project) is False
