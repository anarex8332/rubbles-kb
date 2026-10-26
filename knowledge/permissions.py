def can_confirm_fresh(user, article):
    """Регламент 4.4: актуальность подтверждает ответственный (или администратор)."""
    return user.is_authenticated and (user.is_staff or article.responsible_id == user.pk)


def can_resolve_remark(user, remark):
    """Регламент 7.2: замечание разрешает его автор или ответственный за статью."""
    return user.is_authenticated and (
        user.is_staff or remark.author_id == user.pk or remark.article.responsible_id == user.pk)


def can_delete_comment(user, comment):
    """Раздел 3.2: комментарий удаляет его автор (или администратор)."""
    return user.is_authenticated and (user.is_staff or comment.author_id == user.pk)
