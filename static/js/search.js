document.addEventListener('DOMContentLoaded', () => {
    document
        .querySelectorAll('form[role="search"],.search-form')
        .forEach((form, index) => {
            const input = form.querySelector('input[name="q"]');
            if (!input) return;
            const panel = document.createElement('div');
            panel.className = 'search-suggestions';
            panel.id = 'search-suggestions-' + index;
            panel.hidden = true;
            panel.setAttribute('role', 'listbox');
            panel.setAttribute('aria-label', 'Лучшие результаты');
            document.body.append(panel);
            input.autocomplete = 'off';
            input.setAttribute('role', 'combobox');
            input.setAttribute('aria-controls', panel.id);
            input.setAttribute('aria-expanded', 'false');
            input.setAttribute('aria-autocomplete', 'list');
            let timer,
                controller,
                serial = 0,
                active = -1;
            function position() {
                const rect = form.getBoundingClientRect();
                const width = Math.min(
                    Math.max(rect.width, 300),
                    innerWidth - 24,
                );
                panel.style.width = width + 'px';
                panel.style.left =
                    Math.max(12, Math.min(rect.left, innerWidth - width - 12)) +
                    'px';
                panel.style.top = rect.bottom + 6 + 'px';
                panel.style.maxHeight =
                    Math.max(80, innerHeight - rect.bottom - 18) + 'px';
            }
            function close() {
                panel.hidden = true;
                input.setAttribute('aria-expanded', 'false');
                input.removeAttribute('aria-activedescendant');
                active = -1;
            }
            input.addEventListener('input', () => {
                clearTimeout(timer);
                controller?.abort();
                close();
                const ticket = ++serial;
                const query = input.value.trim();
                if (query.length < 2) return;
                timer = setTimeout(async () => {
                    controller = new AbortController();
                    try {
                        const response = await fetch(
                            document.body.dataset.searchUrl +
                                '?q=' +
                                encodeURIComponent(query),
                            { signal: controller.signal },
                        );
                        if (!response.ok) return;
                        const data = await response.json();
                        if (
                            ticket !== serial ||
                            document.activeElement !== input
                        )
                            return;
                        panel.replaceChildren();
                        data.results.slice(0, 5).forEach((item, i) => {
                            const link = document.createElement('a');
                            link.id = panel.id + '-' + i;
                            link.href = item.url;
                            link.setAttribute('role', 'option');
                            link.setAttribute('aria-selected', 'false');
                            const title = document.createElement('span');
                            title.className = 'suggestion-title';
                            title.textContent = item.title;
                            const section = document.createElement('small');
                            section.textContent = item.section;
                            link.append(title, section);
                            panel.append(link);
                        });
                        if (!data.results.length) {
                            const empty = document.createElement('p');
                            empty.textContent = 'Статьи не найдены';
                            panel.append(empty);
                        }
                        position();
                        panel.hidden = false;
                        input.setAttribute('aria-expanded', 'true');
                    } catch (e) {
                        if (e.name !== 'AbortError') close();
                    }
                }, 180);
            });
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    ++serial;
                    clearTimeout(timer);
                    controller?.abort();
                    close();
                    return;
                }
                if (panel.hidden) return;
                const items = [...panel.querySelectorAll('a')];
                if (['ArrowDown', 'ArrowUp'].includes(e.key) && items.length) {
                    e.preventDefault();
                    active =
                        (active +
                            (e.key === 'ArrowDown' ? 1 : -1) +
                            items.length) %
                        items.length;
                    items.forEach((el, i) =>
                        el.setAttribute('aria-selected', String(i === active)),
                    );
                    input.setAttribute(
                        'aria-activedescendant',
                        items[active].id,
                    );
                    items[active].scrollIntoView({ block: 'nearest' });
                } else if (e.key === 'Enter' && active >= 0) {
                    e.preventDefault();
                    location.href = items[active].href;
                }
            });
            document.addEventListener('pointerdown', (e) => {
                if (!form.contains(e.target) && !panel.contains(e.target)) {
                    ++serial;
                    close();
                }
            });
            document.addEventListener('focusin', (e) => {
                if (!form.contains(e.target) && !panel.contains(e.target))
                    close();
            });
            window.addEventListener('resize', () => {
                if (!panel.hidden) position();
            });
            window.addEventListener(
                'scroll',
                () => {
                    if (!panel.hidden) position();
                },
                true,
            );
        });
});
