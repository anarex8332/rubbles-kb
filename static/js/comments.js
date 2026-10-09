document.addEventListener('DOMContentLoaded', () => {
    const stickers = {
        thanks: 'Спасибо!',
        done: 'Готово',
        idea: 'Есть идея',
        agree: 'Согласен',
        question: 'Есть вопрос',
        great: 'Отлично!',
    };
    const emojis = [
        '👍',
        '❤️',
        '😊',
        '😂',
        '🎉',
        '🔥',
        '👏',
        '🙏',
        '🤔',
        '👀',
        '✅',
        '💡',
        '🚀',
        '🙌',
        '😎',
        '💯',
    ];
    function stickerNode(key) {
        const node = document.createElement('span');
        node.className = 'sticker sticker--' + key;
        node.textContent = stickers[key] || '';
        return node;
    }
    document
        .querySelectorAll('[data-sticker]')
        .forEach((node) => node.append(stickerNode(node.dataset.sticker)));
    document.querySelectorAll('.comment-composer').forEach((form) => {
        const editor = form.querySelector('.comment-editor'),
            sticker = form.elements.sticker,
            preview = form.querySelector('.sticker-preview'),
            files = form.elements.files,
            error = form.querySelector('.comment-error');
        let range;
        editor.addEventListener('keyup', saveSelection);
        editor.addEventListener('mouseup', saveSelection);
        editor.addEventListener('input', saveSelection);
        function saveSelection() {
            const selection = getSelection();
            if (selection.rangeCount && editor.contains(selection.anchorNode))
                range = selection.getRangeAt(0).cloneRange();
        }
        function restoreSelection() {
            editor.focus();
            if (range && editor.contains(range.commonAncestorContainer)) {
                const selection = getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
            }
        }
        editor.addEventListener('paste', (event) => {
            event.preventDefault();
            document.execCommand(
                'insertText',
                false,
                event.clipboardData.getData('text/plain'),
            );
        });
        form.querySelectorAll('[data-format]').forEach((button) => {
            button.addEventListener('mousedown', (event) =>
                event.preventDefault(),
            );
            button.addEventListener('click', () => {
                restoreSelection();
                document.execCommand(button.dataset.format);
                saveSelection();
            });
        });
        emojis.forEach((emoji) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = emoji;
            button.setAttribute('aria-label', emoji);
            button.addEventListener('click', () => {
                restoreSelection();
                document.execCommand('insertText', false, emoji);
                saveSelection();
                button.closest('details').open = false;
            });
            form.querySelector('.emoji-options').append(button);
        });
        function showSticker() {
            preview.replaceChildren();
            if (!sticker.value) return;
            preview.append(stickerNode(sticker.value));
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn btn-link btn-sm';
            remove.textContent = 'Убрать стикер';
            remove.onclick = () => {
                sticker.value = '';
                showSticker();
            };
            preview.append(remove);
        }
        Object.entries(stickers).forEach(([key, label]) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.setAttribute('aria-label', label);
            button.append(stickerNode(key));
            button.onclick = () => {
                sticker.value = key;
                showSticker();
                button.closest('details').open = false;
            };
            form.querySelector('.sticker-options').append(button);
        });
        showSticker();
        files.addEventListener('change', () => {
            const selected = form.querySelector('.selected-files');
            selected.replaceChildren();
            [...files.files].forEach((file) => {
                const node = document.createElement('span');
                node.textContent = file.name;
                selected.append(node);
            });
        });
        editor.addEventListener('keydown', (event) => {
            if (
                event.key === 'Enter' &&
                (event.ctrlKey || event.metaKey) &&
                !event.isComposing
            ) {
                event.preventDefault();
                form.requestSubmit();
            }
        });
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            error.hidden = true;
            const submit = form.querySelector('[type="submit"]');
            if (submit.disabled) return;
            const data = new FormData(form);
            data.set('text_html', editor.innerHTML);
            data.set('text', editor.innerText);
            submit.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: data,
                });
                const result = await response.json();
                if (!response.ok)
                    throw new Error(
                        result.error || 'Не удалось сохранить комментарий.',
                    );
                location.hash = 'comment-' + result.id;
                location.reload();
            } catch (failure) {
                error.textContent =
                    failure.message ||
                    'Не удалось сохранить. Попробуйте ещё раз.';
                error.hidden = false;
                submit.disabled = false;
            }
        });
    });
    document.addEventListener('click', (event) =>
        document.querySelectorAll('.comment-picker[open]').forEach((picker) => {
            if (!picker.contains(event.target)) picker.open = false;
        }),
    );
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape')
            document
                .querySelectorAll('.comment-picker[open]')
                .forEach((picker) => {
                    picker.open = false;
                    picker.querySelector('summary').focus();
                });
    });
});
