document.addEventListener('DOMContentLoaded', () => {
    const groups = {
        Смайлы: [
            ['😀', 'улыбка радость'],
            ['😊', 'улыбка'],
            ['😂', 'смех'],
            ['🤣', 'смешно'],
            ['😉', 'подмигивание'],
            ['😍', 'любовь'],
            ['🥰', 'любовь'],
            ['😎', 'круто'],
            ['🤔', 'думаю'],
            ['🤨', 'сомнение'],
            ['😢', 'грусть'],
            ['😭', 'плач'],
            ['😮', 'удивление'],
            ['😴', 'сон'],
            ['🥳', 'праздник'],
            ['😅', 'неловко'],
            ['🙂', 'улыбка'],
            ['🙃', 'улыбка'],
            ['😇', 'ангел'],
            ['🤗', 'обнимаю'],
            ['🤫', 'тихо'],
            ['😐', 'без эмоций'],
            ['😔', 'печаль'],
            ['😤', 'злость'],
        ],
        Жесты: [
            ['👍', 'да отлично'],
            ['👎', 'нет плохо'],
            ['👏', 'аплодисменты'],
            ['🙏', 'спасибо'],
            ['🙌', 'ура'],
            ['🤝', 'согласен договорились'],
            ['👋', 'привет'],
            ['👌', 'ок'],
            ['✌️', 'победа'],
            ['💪', 'сила'],
            ['🤞', 'удача'],
            ['🫶', 'любовь'],
        ],
        Символы: [
            ['❤️', 'сердце любовь'],
            ['🔥', 'огонь'],
            ['🎉', 'праздник'],
            ['✅', 'готово да'],
            ['💡', 'идея'],
            ['🚀', 'ракета запуск'],
            ['👀', 'смотрю'],
            ['💯', 'сто отлично'],
            ['⭐', 'звезда'],
            ['📌', 'важно'],
            ['❓', 'вопрос'],
            ['⚠️', 'внимание'],
            ['💻', 'компьютер'],
            ['📎', 'файл'],
            ['📚', 'книги'],
            ['☕', 'кофе'],
        ],
    };
    document.querySelectorAll('.comment-composer').forEach((form) => {
        const editor = form.querySelector('.comment-editor'),
            fileInput = form.elements.files,
            error = form.querySelector('.comment-error'),
            emojiPanel = form.querySelector('.emoji-panel');
        let range,
            selectedFiles = [],
            previews = [];
        const mentions = form.querySelector('.mention-options');
        let mentionTimer,
            mentionRange,
            mentionTicket = 0,
            mentionActive = -1;
        function hideMentions() {
            mentions.hidden = true;
            mentionActive = -1;
            editor.removeAttribute('aria-activedescendant');
        }
        editor.addEventListener('input', () => {
            clearTimeout(mentionTimer);
            hideMentions();
            const ticket = ++mentionTicket;
            const selection = getSelection();
            if (!selection.rangeCount || !editor.contains(selection.anchorNode))
                return;
            const caret = selection.getRangeAt(0);
            if (
                !caret.collapsed ||
                caret.startContainer.nodeType !== Node.TEXT_NODE
            )
                return;
            const prefix = caret.startContainer.textContent.slice(
                0,
                caret.startOffset,
            );
            const match = prefix.match(/(?:^|\s)@([\wа-яА-ЯёЁ.+-]*)$/u);
            if (!match) return;
            mentionRange = caret.cloneRange();
            mentionRange.setStart(
                caret.startContainer,
                caret.startOffset - match[1].length - 1,
            );
            mentionTimer = setTimeout(async () => {
                try {
                    const response = await fetch(
                        form.dataset.mentionUrl +
                            '?q=' +
                            encodeURIComponent(match[1]),
                    );
                    if (!response.ok) return;
                    const data = await response.json();
                    if (ticket !== mentionTicket) return;
                    mentions.replaceChildren();
                    data.results.forEach((user, i) => {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.id =
                            'mention-' + Math.random().toString(36).slice(2);
                        button.setAttribute('role', 'option');
                        button.setAttribute('aria-selected', 'false');
                        button.textContent = user.name + ' · @' + user.username;
                        button.onmousedown = (e) => e.preventDefault();
                        button.onclick = () => {
                            editor.focus();
                            const selection = getSelection();
                            selection.removeAllRanges();
                            selection.addRange(mentionRange);
                            document.execCommand(
                                'insertText',
                                false,
                                '@' + user.username + ' ',
                            );
                            hideMentions();
                            ++mentionTicket;
                            remember();
                        };
                        mentions.append(button);
                    });
                    mentions.hidden = !data.results.length;
                } catch {
                    hideMentions();
                }
            }, 150);
        });
        editor.addEventListener('keydown', (event) => {
            if (mentions.hidden) return;
            const options = [...mentions.querySelectorAll('button')];
            if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                mentionActive =
                    (mentionActive +
                        (event.key === 'ArrowDown' ? 1 : -1) +
                        options.length) %
                    options.length;
                options.forEach((el, i) =>
                    el.setAttribute(
                        'aria-selected',
                        String(i === mentionActive),
                    ),
                );
                editor.setAttribute(
                    'aria-activedescendant',
                    options[mentionActive].id,
                );
            } else if (event.key === 'Enter') {
                event.preventDefault();
                event.stopImmediatePropagation();
                options[Math.max(0, mentionActive)]?.click();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                hideMentions();
                ++mentionTicket;
            }
        });
        document.addEventListener('pointerdown', (event) => {
            if (!mentions.contains(event.target) && event.target !== editor) {
                hideMentions();
                ++mentionTicket;
            }
        });
        const original = editor.innerHTML;
        function remember() {
            const selection = getSelection();
            if (selection.rangeCount && editor.contains(selection.anchorNode))
                range = selection.getRangeAt(0).cloneRange();
        }
        function focus() {
            editor.focus();
            if (range && editor.contains(range.commonAncestorContainer)) {
                const selection = getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
            }
        }
        ['keyup', 'mouseup', 'input', 'blur'].forEach((event) =>
            editor.addEventListener(event, remember),
        );
        editor.addEventListener('input', () => {
            if (!editor.textContent.trim() && !editor.querySelector('img'))
                editor.replaceChildren();
        });
        function closePanels() {
            form.querySelectorAll('[data-popup]').forEach(
                (el) => (el.hidden = true),
            );
            form.querySelectorAll('[data-panel]').forEach((el) =>
                el.setAttribute('aria-expanded', 'false'),
            );
        }
        form.querySelectorAll('[data-panel]').forEach((button) =>
            button.addEventListener('click', () => {
                const panel = form.querySelector(
                    '[data-popup="' + button.dataset.panel + '"]',
                );
                const open = panel.hidden;
                closePanels();
                panel.hidden = !open;
                button.setAttribute('aria-expanded', String(open));
                if (open && button.dataset.panel === 'emoji') renderEmoji();
            }),
        );
        let category = 'Смайлы';
        const recentKey =
            'rubbles-emoji:' +
            (document.getElementById('sidebar')?.dataset.navUser || 'local');
        function recent() {
            try {
                return JSON.parse(localStorage.getItem(recentKey) || '[]')
                    .filter((x) =>
                        Object.values(groups)
                            .flat()
                            .some((item) => item[0] === x),
                    )
                    .slice(0, 16);
            } catch {
                return [];
            }
        }
        function renderEmoji() {
            const query = form
                .querySelector('.emoji-search')
                .value.trim()
                .toLowerCase();
            const area = form.querySelector('.emoji-options');
            area.replaceChildren();
            let list = query
                ? Object.values(groups)
                      .flat()
                      .filter((item) => item.join(' ').includes(query))
                : category === 'Недавние'
                  ? recent().map((emoji) => [emoji, 'недавний'])
                  : groups[category];
            for (const [emoji, label] of list) {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = emoji;
                button.title = label;
                button.setAttribute('aria-label', emoji + ' ' + label);
                button.onclick = () => {
                    focus();
                    document.execCommand('insertText', false, emoji);
                    remember();
                    try {
                        localStorage.setItem(
                            recentKey,
                            JSON.stringify(
                                [
                                    emoji,
                                    ...recent().filter((x) => x !== emoji),
                                ].slice(0, 16),
                            ),
                        );
                    } catch {}
                    closePanels();
                };
                area.append(button);
            }
            if (!list.length) {
                const empty = document.createElement('p');
                empty.textContent = query
                    ? 'Ничего не найдено'
                    : 'Здесь появятся выбранные эмодзи';
                area.append(empty);
            }
        }
        ['Недавние', ...Object.keys(groups)].forEach((name) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = name;
            button.setAttribute('aria-pressed', String(name === category));
            button.onclick = () => {
                category = name;
                form.querySelector('.emoji-search').value = '';
                form.querySelectorAll('.emoji-categories button').forEach(
                    (el) =>
                        el.setAttribute('aria-pressed', String(el === button)),
                );
                renderEmoji();
            };
            form.querySelector('.emoji-categories').append(button);
        });
        form.querySelector('.emoji-search').addEventListener(
            'input',
            renderEmoji,
        );
        form.querySelectorAll('[data-format]').forEach((button) => {
            button.onmousedown = (e) => e.preventDefault();
            button.onclick = () => {
                focus();
                document.execCommand(button.dataset.format);
                remember();
            };
        });
        form.querySelectorAll('[data-attach]').forEach(
            (button) =>
                (button.onclick = () => {
                    fileInput.accept =
                        button.dataset.attach === 'image'
                            ? '.png,.jpg,.jpeg,.gif,.webp'
                            : '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.odt';
                    fileInput.click();
                    closePanels();
                }),
        );
        function renderFiles() {
            previews.forEach((url) => URL.revokeObjectURL(url));
            previews = [];
            const area = form.querySelector('.selected-files');
            area.replaceChildren();
            selectedFiles.forEach((file, i) => {
                const chip = document.createElement('div');
                chip.className = 'attachment-chip';
                if (file.type.startsWith('image/')) {
                    const img = document.createElement('img');
                    const url = URL.createObjectURL(file);
                    previews.push(url);
                    img.src = url;
                    img.alt = '';
                    chip.append(img);
                }
                const text = document.createElement('span');
                text.textContent = file.name;
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.textContent = '×';
                remove.setAttribute('aria-label', 'Убрать ' + file.name);
                remove.onclick = () => {
                    selectedFiles.splice(i, 1);
                    renderFiles();
                };
                chip.append(text, remove);
                area.append(chip);
            });
        }
        function addFiles(files) {
            if (
                selectedFiles.length + files.length > 5 ||
                files.some((file) => file.size > 10 * 1024 * 1024)
            ) {
                error.textContent = 'Можно прикрепить до 5 файлов по 10 МБ.';
                error.hidden = false;
                return;
            }
            selectedFiles.push(...files);
            error.hidden = true;
            renderFiles();
        }
        fileInput.onchange = () => {
            addFiles([...fileInput.files]);
            fileInput.value = '';
        };
        editor.addEventListener('paste', (event) => {
            event.preventDefault();
            if (event.clipboardData.files.length)
                addFiles([...event.clipboardData.files]);
            else
                document.execCommand(
                    'insertText',
                    false,
                    event.clipboardData.getData('text/plain'),
                );
        });
        form.addEventListener('dragover', (event) => event.preventDefault());
        form.addEventListener('drop', (event) => {
            event.preventDefault();
            addFiles([...event.dataTransfer.files]);
        });
        editor.onkeydown = (event) => {
            if (
                event.key === 'Enter' &&
                !event.shiftKey &&
                !event.isComposing
            ) {
                event.preventDefault();
                form.requestSubmit();
            }
        };
        const details = form.closest('.comment-edit');
        details?.addEventListener('toggle', () => {
            if (details.open) editor.focus();
        });
        form.querySelector('[data-cancel-edit]')?.addEventListener(
            'click',
            () => {
                editor.innerHTML = original;
                selectedFiles = [];
                renderFiles();
                form.querySelectorAll('[name=remove_attachment]').forEach(
                    (el) => (el.checked = false),
                );
                closePanels();
                details.open = false;
                details.querySelector('summary').focus();
            },
        );
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const submit = form.querySelector('[type=submit]');
            if (submit.disabled) return;
            error.hidden = true;
            const data = new FormData(form);
            data.delete('files');
            selectedFiles.forEach((file) => data.append('files', file));
            data.set('text_html', editor.innerHTML);
            data.set('text', editor.innerText);
            data.set('sticker', '');
            form.querySelectorAll('[type=submit]').forEach(
                (button) => (button.disabled = true),
            );
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
                error.textContent = failure.message;
                error.hidden = false;
                form.querySelectorAll('[type=submit]').forEach(
                    (button) => (button.disabled = false),
                );
            }
        });
        document.addEventListener('pointerdown', (e) => {
            if (!form.contains(e.target)) closePanels();
        });
        form.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const trigger = form.querySelector(
                    '[data-panel][aria-expanded=true]',
                );
                closePanels();
                trigger?.focus();
            }
        });
    });
});
