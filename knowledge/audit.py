from .models import ActionLog


def log_action(user, action, article=None, details=''):
    """Фиксирует основное действие пользователя в журнале (НФТ-08)."""
    ActionLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        action=action, article=article, details=details[:500])
