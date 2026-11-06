from django.db import transaction
from django.utils import timezone

from notifications.services import notify
from wallet import services as wallet
from wallet.models import Transaction

from .models import Submission, SubmissionFile, Task

MAX_FILES = 5
MAX_FILE_SIZE = 10 * 1024 * 1024


class TaskError(Exception):
    pass


def _award(sub, amount):
    task = sub.task
    with transaction.atomic():
        Task.objects.select_for_update().get(pk=task.pk)
        left = task.rewards_left()
        if left == 0:
            amount = 0
        sub.awarded = amount
        sub.status = Submission.Status.APPROVED
        sub.save()
    if amount:
        wallet.reward(sub.user, amount, Transaction.Kind.TASK, f"Задание: {task.title}", ("task", task.pk))
    return amount


def submit_manual(task, user, text, link, files):
    if not task.is_open:
        raise TaskError("Приём ответов закрыт")
    if not (text.strip() or link.strip() or files):
        raise TaskError("Ответ пустой")
    if len(files) > MAX_FILES:
        raise TaskError(f"Не больше {MAX_FILES} файлов")
    for f in files:
        if f.size > MAX_FILE_SIZE:
            raise TaskError(f"Файл «{f.name}» больше 10 МБ")
    sub = Submission.objects.filter(task=task, user=user).first()
    if sub and sub.status not in (Submission.Status.REVISION,):
        raise TaskError("Ответ уже отправлен")
    sub = sub or Submission(task=task, user=user)
    sub.text, sub.link = text.strip() if task.allow_text else "", link.strip() if task.allow_link else ""
    sub.status = Submission.Status.SUBMITTED
    sub.submitted_at = timezone.now()
    sub.save()
    if task.allow_files and files:
        sub.files.all().delete()
        for f in files:
            sf = SubmissionFile(submission=sub, file=f)
            sf.full_clean(exclude=["submission"])
            sf.save()
    return sub


def review(sub, decision, reviewer, comment="", amount=None):
    if sub.status != Submission.Status.SUBMITTED:
        raise TaskError("Ответ уже проверен")
    if decision in ("reject", "revision") and not comment.strip():
        raise TaskError("Укажите комментарий для студента")
    sub.reviewed_by, sub.reviewed_at, sub.comment = reviewer, timezone.now(), comment.strip()
    title = sub.task.title
    if decision == "approve":
        amount = sub.task.reward if amount is None else max(0, min(int(amount), sub.task.reward))
        got = _award(sub, amount)
        notify(sub.user, f"Задание «{title}» принято" + (f", +{got}" if got else ""), f"/tasks/{sub.task_id}/", "task")
    else:
        sub.status = Submission.Status.REJECTED if decision == "reject" else Submission.Status.REVISION
        sub.save()
        verb = "отклонено" if decision == "reject" else "возвращено на доработку"
        notify(sub.user, f"Задание «{title}» {verb}: {comment[:200]}", f"/tasks/{sub.task_id}/", "task")
    return sub


def submit_quiz(task, user, answers):
    """answers: {question_id: str | [str]}. Возвращает (sub, percent, награда)."""
    if not task.is_open:
        raise TaskError("Задание закрыто")
    with transaction.atomic():
        sub, _ = Submission.objects.select_for_update().get_or_create(
            task=task, user=user, defaults={"status": Submission.Status.IN_PROGRESS}
        )
        if sub.status == Submission.Status.APPROVED:
            raise TaskError("Задание уже выполнено")
        if sub.attempts_used >= task.attempts:
            raise TaskError("Попытки закончились")
        questions = list(task.questions.all())
        if not questions:
            raise TaskError("В задании нет вопросов")
        right = sum(1 for q in questions if q.is_correct(answers.get(q.pk)))
        percent = round(right * 100 / len(questions))
        sub.attempts_used += 1
        sub.best_percent = max(sub.best_percent, percent)
        sub.submitted_at = timezone.now()
        passed = percent >= task.pass_percent
        if not passed:
            sub.status = Submission.Status.FAILED if sub.attempts_used >= task.attempts else Submission.Status.IN_PROGRESS
            sub.save()
            return sub, percent, 0
        sub.save()
    amount = round(task.reward * percent / 100) if task.proportional else task.reward
    return sub, percent, _award(sub, amount)


def quest_answer(task, user, answer):
    """Квест: следующий вопрос открывается после правильного ответа. Возвращает (sub, верно?, завершён?)."""
    if not task.is_open:
        raise TaskError("Задание закрыто")
    questions = list(task.questions.all())
    with transaction.atomic():
        sub, _ = Submission.objects.select_for_update().get_or_create(
            task=task, user=user, defaults={"status": Submission.Status.IN_PROGRESS}
        )
        if sub.status == Submission.Status.APPROVED:
            raise TaskError("Квест уже пройден")
        q = questions[sub.quest_step]
        if not q.is_correct(answer):
            return sub, False, False
        sub.quest_step += 1
        sub.save()
        done = sub.quest_step >= len(questions)
    if done:
        _award(sub, task.reward)
    return sub, True, done
