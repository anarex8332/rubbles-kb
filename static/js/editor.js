document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('article-form');
    if (!form) return;
    const editor = document.getElementById('editor-content'),
        title = document.getElementById('title-input'),
        section = document.getElementById('section-hidden'),
        comments = document.getElementById('settings-comments'),
        content = document.getElementById('content-hidden'),
        status = document.getElementById('status-hidden'),
        indicator = document.getElementById('autosave-indicator'),
        banner = document.getElementById('draft-recovery'),
        key = form.dataset.draftKey;
    let timer,
        selection,
        pendingDraft,
        dirty = false,
        submitted = false;
    const makeToken = () =>
        crypto.randomUUID
            ? crypto.randomUUID()
            : Date.now() + '-' + Math.random();
    function snapshot() {
        return {
            title: title.value,
            content: editor.innerHTML,
            section: section.value,
            allow_comments: comments.checked,
            change_summary: form.elements.change_summary?.value || '',
            status: status.value,
            token: makeToken(),
            savedAt: Date.now(),
        };
    }
    function save() {
        if (pendingDraft) return;
        const draft = snapshot();
        document.getElementById('draft-token').value = draft.token;
        try {
            localStorage.setItem(key, JSON.stringify(draft));
            indicator.textContent = 'Локальная копия сохранена в этом браузере';
        } catch (e) {
            indicator.textContent =
                'Не удалось сохранить локальную копию. Сохраните статью.';
        }
    }
    function changed() {
        dirty = true;
        clearTimeout(timer);
        indicator.textContent = pendingDraft
            ? 'Сначала восстановите или удалите найденную копию'
            : 'Есть несохранённые изменения';
        timer = setTimeout(save, 1500);
    }
    form.addEventListener('input', changed);
    form.addEventListener('change', changed);
    try {
        const draft = JSON.parse(localStorage.getItem(key) || 'null'),
            current = snapshot();
        if (
            draft &&
            typeof draft.content === 'string' &&
            [
                'title',
                'content',
                'section',
                'allow_comments',
                'change_summary',
            ].some((f) => draft[f] !== current[f])
        ) {
            pendingDraft = draft;
            banner.hidden = false;
        }
    } catch (e) {}
    document.getElementById('restore-draft').addEventListener('click', () => {
        if (!pendingDraft) return;
        title.value = pendingDraft.title || '';
        editor.innerHTML = pendingDraft.content;
        section.value = pendingDraft.section || '';
        section.dispatchEvent(new Event('rubbles:refresh'));
        comments.checked = !!pendingDraft.allow_comments;
        if (form.elements.change_summary)
            form.elements.change_summary.value =
                pendingDraft.change_summary || '';
        status.value = ['draft', 'published', 'archived'].includes(
            pendingDraft.status,
        )
            ? pendingDraft.status
            : 'draft';
        pendingDraft = null;
        banner.hidden = true;
        changed();
        editor.focus();
    });
    document.getElementById('discard-draft').addEventListener('click', () => {
        try {
            localStorage.removeItem(key);
        } catch (e) {}
        pendingDraft = null;
        banner.hidden = true;
        if (dirty) save();
    });
    form.addEventListener('submit', (event) => {
        if (pendingDraft) {
            event.preventDefault();
            banner.scrollIntoView({ block: 'center' });
            document.getElementById('restore-draft').focus();
            return;
        }
        content.value = editor.innerHTML;
        if (!editor.textContent.trim() && !editor.querySelector('img,svg,hr')) {
            event.preventDefault();
            indicator.textContent =
                'Добавьте содержание статьи перед сохранением.';
            editor.focus();
            return;
        }
        status.value =
            event.submitter?.value === 'draft' ? 'draft' : 'published';
        clearTimeout(timer);
        save();
        submitted = true;
    });
    window.addEventListener('beforeunload', (event) => {
        if (!dirty || submitted) return;
        save();
        event.preventDefault();
        event.returnValue = '';
    });
    document.addEventListener('selectionchange', () => {
        const current = window.getSelection();
        if (current.rangeCount && editor.contains(current.anchorNode))
            selection = current.getRangeAt(0).cloneRange();
    });
    function focusSelection() {
        editor.focus();
        if (selection && editor.contains(selection.commonAncestorContainer)) {
            const current = window.getSelection();
            current.removeAllRanges();
            current.addRange(selection);
        }
    }
    function csrfToken() {
        const field = document.querySelector('[name=csrfmiddlewaretoken]');
        return field ? field.value : '';
    }
    function image(file) {
        if (!file || !file.type.startsWith('image/')) return;
        const body = new FormData();
        body.append('image', file);
        indicator.textContent = 'Загружаю изображение…';
        fetch('/images/upload/', {
            method: 'POST', body, credentials: 'same-origin',
            headers: {'X-CSRFToken': csrfToken()},
        }).then((response) => response.json().then((data) => ({ok: response.ok, data})))
            .then(({ok, data}) => {
                if (!ok) { indicator.textContent = data.error || 'Не удалось загрузить изображение.'; return; }
                focusSelection();
                document.execCommand('insertImage', false, data.url);
                changed();
            })
            .catch(() => { indicator.textContent = 'Не удалось загрузить изображение.'; });
    }
    const imageInput = document.getElementById('image-input');
    imageInput.addEventListener('change', () => {
        image(imageInput.files[0]);
        imageInput.value = '';
    });
    document.querySelectorAll('[data-cmd]').forEach((button) => {
        button.addEventListener('mousedown', (e) => e.preventDefault());
        button.addEventListener('click', () => {
            focusSelection();
            const cmd = button.dataset.cmd;
            if (cmd === 'insertImage') return imageInput.click();
            if (cmd === 'createLink') {
                const url = prompt('Адрес ссылки', 'https://');
                if (!url) return;
                if (!/^(https?:\/\/|mailto:|\/|#)/i.test(url)) {
                    indicator.textContent =
                        'Используйте ссылку http, https или mailto.';
                    return;
                }
                document.execCommand(cmd, false, url);
            } else if (cmd === 'insertMermaid') {
                document.execCommand(
                    'insertHTML',
                    false,
                    '<pre class="mermaid">graph TD\n    A[Начало] --> B[Следующий шаг]\n    B --> C[Результат]</pre><p><br></p>',
                );
            } else
                document.execCommand(cmd, false, button.dataset.value || null);
            changed();
        });
    });
    document.querySelectorAll('[data-font-size]').forEach((select) => {
        let saved = null;
        select.addEventListener('mousedown', () => {
            const s = window.getSelection();
            if (s.rangeCount && editor.contains(s.anchorNode)) saved = s.getRangeAt(0).cloneRange();
        });
        select.addEventListener('change', () => {
            editor.focus();
            if (saved) { const s = window.getSelection(); s.removeAllRanges(); s.addRange(saved); }
            window.applyFontSize(editor, select.value);
            select.selectedIndex = 0;
            changed();
        });
    });
    const preview = document.getElementById('preview-toggle');
    preview.addEventListener('click', () => {
        const active = preview.getAttribute('aria-pressed') !== 'true';
        preview.setAttribute('aria-pressed', String(active));
        preview.textContent = active ? 'К редактированию' : 'Предпросмотр';
        editor.contentEditable = String(!active);
        editor.classList.toggle('editor-content--preview', active);
        document
            .querySelectorAll('[data-cmd], [data-font-size]')
            .forEach((b) => (b.disabled = active));
    });
    // Ширина столбцов таблицы: потяните за правую границу ячейки.
    const EDGE = 6;
    function edgeCell(e) {
        if (editor.contentEditable !== 'true') return null;
        const cell = e.target.closest?.('td,th');
        if (!cell || !editor.contains(cell)) return null;
        const rect = cell.getBoundingClientRect();
        return rect.right - e.clientX <= EDGE ? cell : null;
    }
    editor.addEventListener('mousemove', (e) => {
        if (!document.body.classList.contains('is-col-resizing'))
            editor.classList.toggle('is-col-resize', !!edgeCell(e));
    });
    editor.addEventListener('mouseleave', () =>
        editor.classList.remove('is-col-resize'),
    );
    editor.addEventListener('mousedown', (e) => {
        const cell = edgeCell(e);
        if (!cell || e.button !== 0) return;
        e.preventDefault();
        const table = cell.closest('table'),
            index = cell.cellIndex,
            startX = e.clientX,
            startWidth = cell.getBoundingClientRect().width;
        const column = [...table.rows]
            .map((row) => row.cells[index])
            .filter((c) => c && c.colSpan === 1);
        document.body.classList.add('is-col-resizing');
        const move = (ev) => {
            const width = Math.round(
                Math.max(40, Math.min(2000, startWidth + ev.clientX - startX)),
            );
            column.forEach((c) => c.setAttribute('width', width));
        };
        const up = () => {
            document.removeEventListener('mousemove', move);
            document.removeEventListener('mouseup', up);
            document.body.classList.remove('is-col-resizing');
            editor.classList.remove('is-col-resize');
            changed();
        };
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', up);
    });
    editor.addEventListener('dragover', (e) => e.preventDefault());
    editor.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length) {
            e.preventDefault();
            image(e.dataTransfer.files[0]);
        }
    });
    editor.addEventListener('paste', (e) => {
        for (const item of e.clipboardData.items)
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                image(item.getAsFile());
                break;
            }
    });
});
