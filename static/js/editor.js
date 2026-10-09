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
    function image(file) {
        if (!file || !file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = () => {
            focusSelection();
            document.execCommand('insertImage', false, reader.result);
            changed();
        };
        reader.readAsDataURL(file);
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
    const preview = document.getElementById('preview-toggle');
    preview.addEventListener('click', () => {
        const active = preview.getAttribute('aria-pressed') !== 'true';
        preview.setAttribute('aria-pressed', String(active));
        preview.textContent = active ? 'К редактированию' : 'Предпросмотр';
        editor.contentEditable = String(!active);
        editor.classList.toggle('editor-content--preview', active);
        document
            .querySelectorAll('[data-cmd]')
            .forEach((b) => (b.disabled = active));
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
