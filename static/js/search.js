document.addEventListener('DOMContentLoaded', () => {
    document
        .querySelectorAll(
            'form[role="search"], form.header-search, form.home-search, form.search-form',
        )
        .forEach((form, index) => {
            const input = form.querySelector('input[name="q"]');
            if (!input) return;
            form.classList.add('search-with-suggestions');
            const panel = document.createElement('div');
            panel.className = 'search-suggestions';
            panel.id = 'search-suggestions-' + index;
            panel.hidden = true;
            panel.setAttribute('role', 'listbox');
            panel.setAttribute('aria-label', 'Подходящие статьи');
            form.append(panel);
            input.autocomplete = 'off';
            input.setAttribute('role', 'combobox');
            input.setAttribute('aria-autocomplete', 'list');
            input.setAttribute('aria-controls', panel.id);
            input.setAttribute('aria-expanded', 'false');
            let timer,
                controller,
                active = -1,
                serial = 0;
            const close = () => {
                panel.hidden = true;
                input.setAttribute('aria-expanded', 'false');
                input.removeAttribute('aria-activedescendant');
                active = -1;
            };
            input.addEventListener('input', () => {
                clearTimeout(timer);
                controller?.abort();
                const current = ++serial;
                close();
                if (input.value.trim().length < 2) return;
                timer = setTimeout(async () => {
                    controller = new AbortController();
                    try {
                        const response = await fetch(
                            document.body.dataset.searchUrl +
                                '?q=' +
                                encodeURIComponent(input.value.trim()),
                            { signal: controller.signal },
                        );
                        if (!response.ok) throw new Error();
                        const data = await response.json();
                        if (
                            current !== serial ||
                            document.activeElement !== input
                        )
                            return;
                        panel.replaceChildren();
                        data.results.forEach((item, number) => {
                            const link = document.createElement('a');
                            link.href = item.url;
                            link.id = panel.id + '-' + number;
                            link.setAttribute('role', 'option');
                            link.setAttribute('aria-selected', 'false');
                            const title = document.createElement('strong');
                            title.textContent = item.title;
                            const section = document.createElement('small');
                            section.textContent = item.section;
                            link.append(title, section);
                            panel.append(link);
                        });
                        if (!data.results.length) {
                            const empty = document.createElement('p');
                            empty.textContent =
                                'Похожих статей пока нет. Попробуйте другие слова.';
                            panel.append(empty);
                        }
                        panel.hidden = false;
                        input.setAttribute('aria-expanded', 'true');
                    } catch (error) {
                        if (error.name !== 'AbortError') close();
                    }
                }, 220);
            });
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    ++serial;
                    clearTimeout(timer);
                    controller?.abort();
                    close();
                    return;
                }
                if (panel.hidden) return;
                const links = [...panel.querySelectorAll('a')];
                if (
                    ['ArrowDown', 'ArrowUp'].includes(event.key) &&
                    links.length
                ) {
                    event.preventDefault();
                    active =
                        (active +
                            (event.key === 'ArrowDown' ? 1 : -1) +
                            links.length) %
                        links.length;
                    links.forEach((link, i) =>
                        link.setAttribute(
                            'aria-selected',
                            String(i === active),
                        ),
                    );
                    input.setAttribute(
                        'aria-activedescendant',
                        links[active].id,
                    );
                    links[active].scrollIntoView({ block: 'nearest' });
                } else if (event.key === 'Enter' && active >= 0) {
                    event.preventDefault();
                    location.href = links[active].href;
                }
            });
            document.addEventListener('click', (event) => {
                if (!form.contains(event.target)) close();
            });
            form.addEventListener('focusout', () =>
                setTimeout(() => {
                    if (!form.contains(document.activeElement)) close();
                }, 0),
            );
        });
});
