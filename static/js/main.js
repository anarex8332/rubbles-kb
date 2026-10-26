document.addEventListener('DOMContentLoaded', () => {
    function syncTheme() {
        const dark = document.documentElement.dataset.theme === 'dark';
        document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
            const use = button.querySelector('use');
            use.setAttribute(
                'href',
                use.getAttribute('href').split('#')[0] +
                    '#' +
                    (dark ? 'moon' : 'sun'),
            );
            button.setAttribute(
                'aria-label',
                dark ? 'Включить светлую тему' : 'Включить тёмную тему',
            );
            button.title = button.getAttribute('aria-label');
        });
    }
    document
        .querySelectorAll('[data-theme-toggle]')
        .forEach((button) =>
            button.addEventListener('click', () =>
                RubblesTheme.set(
                    document.documentElement.dataset.theme === 'dark'
                        ? 'light'
                        : 'dark',
                ),
            ),
        );
    document.addEventListener('rubbles:theme', syncTheme);
    syncTheme();
    const receipt = document.getElementById('editor-save-receipt');
    if (receipt)
        try {
            const saved = JSON.parse(receipt.textContent),
                draft = JSON.parse(localStorage.getItem(saved.key) || 'null');
            if (draft && draft.token === saved.token)
                localStorage.removeItem(saved.key);
        } catch (e) {}
    initNavigationTree();
    initSidebar();
    initSelects();
    initFontSizeMenus();
    initMessages();
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            const input = document.getElementById('global-search');
            if (input) {
                e.preventDefault();
                input.focus();
                input.select();
            }
        }
        if (e.key === 'Escape')
            document
                .querySelectorAll('details.action-menu[open],details.byline-responsible[open]')
                .forEach((menu) => {
                    menu.open = false;
                    menu.querySelector('summary').focus();
                });
    });
    document.addEventListener('click', (e) =>
        document
            .querySelectorAll('details.action-menu[open],details.byline-responsible[open]')
            .forEach((menu) => {
                // Пункт выпадающего списка после выбора перерисовывается и уже не в документе: такой клик не считаем внешним
                if (e.target.isConnected && !menu.contains(e.target)) menu.open = false;
            }),
    );
    document.querySelectorAll('input,textarea,select').forEach((field) => {
        const errors = field
            .closest('.form-group')
            ?.querySelector('.errorlist,.field-error');
        if (errors) {
            errors.id = errors.id || field.id + '-error';
            field.setAttribute('aria-invalid', 'true');
            field.setAttribute('aria-describedby', errors.id);
        }
    });
});
function initNavigationTree() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    const branches = [...sidebar.querySelectorAll('details[data-nav-key]')],
        key = 'rubbles-nav-open:' + sidebar.dataset.navUser;
    let saved = [];
    try {
        const value = JSON.parse(localStorage.getItem(key) || '[]');
        if (Array.isArray(value)) saved = value;
    } catch (e) {}
    branches.forEach(
        (branch) => (branch.open = saved.includes(branch.dataset.navKey)),
    );
    sidebar.querySelectorAll('a[href]').forEach((link) => {
        if (
            !link.classList.contains('nav-link') ||
            new URL(link.href).pathname !== location.pathname
        )
            return;
        link.classList.add('nav-link--active');
        link.setAttribute('aria-current', 'page');
        if (!link.closest('#sidebar-sections')) return;
        let branch = link.closest('details[data-nav-key]');
        while (branch) {
            branch.open = true;
            branch = branch.parentElement.closest('details[data-nav-key]');
        }
    });
    function save() {
        try {
            localStorage.setItem(
                key,
                JSON.stringify(
                    branches.filter((b) => b.open).map((b) => b.dataset.navKey),
                ),
            );
        } catch (e) {}
    }
    branches.forEach((branch) => branch.addEventListener('toggle', save));
    save();
}
function initSidebar() {
    const sidebar = document.getElementById('sidebar'),
        menu = document.querySelector('.header-menu'),
        collapse = document.querySelector('.sidebar-collapse'),
        backdrop = document.querySelector('.sidebar-backdrop');
    if (!sidebar || !menu || !collapse) return;
    const mobile = matchMedia('(max-width:768px)'),
        parts = [
            ...sidebar.querySelectorAll(
                '.sidebar__nav',
            ),
        ];
    let previousFocus;
    function open(value, restore = true) {
        if (value) previousFocus = document.activeElement;
        document.body.classList.toggle('sidebar-is-open', value);
        backdrop.hidden = !value;
        menu.setAttribute('aria-expanded', String(value));
        sidebar.inert = mobile.matches && !value;
        if (value) sidebar.querySelector('a,button').focus();
        else if (restore && previousFocus) previousFocus.focus();
    }
    function setCollapsed(collapsed) {
        document.body.classList.toggle('sidebar-is-collapsed', collapsed);
        parts.forEach((part) => (part.inert = collapsed));
        collapse.setAttribute('aria-expanded', String(!collapsed));
        collapse.setAttribute(
            'aria-label',
            collapsed ? 'Развернуть панель' : 'Свернуть панель',
        );
    }
    menu.addEventListener('click', () =>
        open(!document.body.classList.contains('sidebar-is-open')),
    );
    collapse.addEventListener('click', () => {
        const collapsed = !document.body.classList.contains(
            'sidebar-is-collapsed',
        );
        setCollapsed(collapsed);
        try {
            localStorage.setItem('kb_sidebar_collapsed', collapsed ? '1' : '0');
        } catch (e) {}
    });
    backdrop.addEventListener('click', () => open(false));
    document
        .querySelector('.sidebar-close')
        .addEventListener('click', () => open(false));
    document.addEventListener('keydown', (e) => {
        if (
            !mobile.matches ||
            !document.body.classList.contains('sidebar-is-open')
        )
            return;
        if (e.key === 'Escape') {
            e.preventDefault();
            open(false);
        }
        if (e.key === 'Tab') {
            const items = [
                    ...sidebar.querySelectorAll(
                        'a,button,summary,input,select',
                    ),
                ].filter((el) => el.getClientRects().length),
                first = items[0],
                last = items[items.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });
    function resize() {
        open(false, false);
        let collapsed = false;
        try {
            collapsed =
                !mobile.matches &&
                localStorage.getItem('kb_sidebar_collapsed') === '1';
        } catch (e) {}
        setCollapsed(collapsed);
        sidebar.inert = mobile.matches;
    }
    mobile.addEventListener('change', resize);
    resize();
}

function initSelects() {
    const chevron =
        '<svg class="kb-select__chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    let openSelect = null;
    document.querySelectorAll('select:not([multiple])').forEach((select, index) => {
        if (select.closest('.theme-control') || select.dataset.native !== undefined) return;
        const wrap = document.createElement('div');
        wrap.className = 'kb-select';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'kb-select__button';
        button.setAttribute('aria-haspopup', 'listbox');
        button.setAttribute('aria-expanded', 'false');
        if (select.id) {
            const label = document.querySelector(`label[for="${select.id}"]`);
            if (label) {
                label.htmlFor = '';
                label.addEventListener('click', () => button.focus());
                button.setAttribute('aria-label', label.textContent.trim());
            }
        }
        const value = document.createElement('span');
        value.className = 'kb-select__value';
        button.append(value);
        button.insertAdjacentHTML('beforeend', chevron);
        const panel = document.createElement('div');
        panel.className = 'kb-select__panel';
        panel.hidden = true;
        const list = document.createElement('ul');
        list.className = 'kb-select__list';
        list.setAttribute('role', 'listbox');
        list.id = 'kb-select-list-' + index;
        button.setAttribute('aria-controls', list.id);
        let search = null;
        if (select.options.length > 10) {
            search = document.createElement('input');
            search.type = 'search';
            search.className = 'kb-select__search';
            search.placeholder = 'Поиск…';
            search.setAttribute('aria-label', 'Поиск по списку');
            panel.append(search);
        }
        panel.append(list);
        select.parentNode.insertBefore(wrap, select);
        wrap.append(select, button, panel);
        select.classList.add('kb-select__native');
        select.tabIndex = -1;
        select.setAttribute('aria-hidden', 'true');

        let active = -1;
        const items = () => [...list.querySelectorAll('li:not([hidden])')];
        function render() {
            list.innerHTML = '';
            [...select.options].forEach((option, i) => {
                const li = document.createElement('li');
                li.setAttribute('role', 'option');
                li.dataset.index = i;
                li.textContent = option.textContent.trim();
                if (option.value === '') li.classList.add('is-placeholder');
                if (option.disabled) li.setAttribute('aria-disabled', 'true');
                li.setAttribute('aria-selected', String(option.selected));
                list.append(li);
            });
            const current = select.options[select.selectedIndex];
            value.textContent = current ? current.textContent.trim() : '';
            wrap.classList.toggle('is-empty', !current || current.value === '');
        }
        function highlight(i) {
            const visible = items();
            visible.forEach((li) => li.classList.remove('is-active'));
            active = Math.max(0, Math.min(i, visible.length - 1));
            const li = visible[active];
            if (li) {
                li.classList.add('is-active');
                li.scrollIntoView({ block: 'nearest' });
            }
        }
        function open() {
            if (openSelect && openSelect !== close) openSelect();
            render();
            panel.hidden = false;
            wrap.classList.add('is-open');
            button.setAttribute('aria-expanded', 'true');
            const rect = button.getBoundingClientRect();
            wrap.classList.toggle(
                'opens-up',
                window.innerHeight - rect.bottom < 300 && rect.top > window.innerHeight - rect.bottom,
            );
            const selected = items().findIndex((li) => li.getAttribute('aria-selected') === 'true');
            highlight(selected < 0 ? 0 : selected);
            openSelect = close;
            if (search) {
                search.value = '';
                search.focus();
            }
        }
        function close(focusButton) {
            panel.hidden = true;
            wrap.classList.remove('is-open');
            button.setAttribute('aria-expanded', 'false');
            if (openSelect === close) openSelect = null;
            if (focusButton) button.focus();
        }
        function choose(li) {
            if (!li || li.getAttribute('aria-disabled') === 'true') return;
            select.selectedIndex = Number(li.dataset.index);
            select.dispatchEvent(new Event('input', { bubbles: true }));
            select.dispatchEvent(new Event('change', { bubbles: true }));
            render();
            close(true);
        }
        function onKey(event) {
            if (panel.hidden) {
                if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
                    event.preventDefault();
                    open();
                }
                return;
            }
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                highlight(active + 1);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                highlight(active - 1);
            } else if (event.key === 'Enter') {
                event.preventDefault();
                choose(items()[active]);
            } else if (event.key === 'Escape') {
                event.preventDefault();
                close(true);
            } else if (event.key === 'Tab') {
                close();
            }
        }
        button.addEventListener('click', () => (panel.hidden ? open() : close(true)));
        button.addEventListener('keydown', onKey);
        search?.addEventListener('keydown', onKey);
        search?.addEventListener('input', () => {
            const query = search.value.trim().toLowerCase();
            list.querySelectorAll('li').forEach((li) => {
                li.hidden = !!query && !li.textContent.toLowerCase().includes(query);
            });
            highlight(0);
        });
        list.addEventListener('mousedown', (event) => event.preventDefault());
        list.addEventListener('click', (event) => choose(event.target.closest('li')));
        list.addEventListener('mousemove', (event) => {
            const li = event.target.closest('li');
            if (li) highlight(items().indexOf(li));
        });
        select.addEventListener('change', render);
        select.addEventListener('rubbles:refresh', render);
        select.addEventListener('invalid', () => {
            wrap.classList.add('is-invalid');
            button.focus();
        });
        select.addEventListener('change', () => wrap.classList.remove('is-invalid'));
        select.form?.addEventListener('reset', () => setTimeout(render));
        render();
    });
    document.addEventListener('click', (event) => {
        if (openSelect && !event.target.closest('.kb-select.is-open')) openSelect();
    });
}

// Уведомления страницы: окно справа снизу с крестиком; успешные скрываются сами.
function initMessages() {
    document.querySelectorAll('.messages .msg').forEach((msg) => {
        const hide = () => {
            if (msg.classList.contains('is-leaving')) return;
            msg.classList.add('is-leaving');
            setTimeout(() => {
                const box = msg.parentElement;
                msg.remove();
                if (box && !box.children.length) box.remove();
            }, 250);
        };
        msg.querySelector('.msg-close')?.addEventListener('click', hide);
        if (!msg.classList.contains('msg-error')) {
            let timer = setTimeout(hide, 6000);
            msg.addEventListener('mouseenter', () => clearTimeout(timer));
            msg.addEventListener('mouseleave', () => {
                timer = setTimeout(hide, 3000);
            });
        }
    });
}

// Размер шрифта выделенного текста: браузер ставит <font size="7">, заменяем его на <span class="fs-…">.
window.applyFontSize = function (root, cls) {
    document.execCommand('styleWithCSS', false, false);
    document.execCommand('fontSize', false, '7');
    root.querySelectorAll('font[size="7"]').forEach((font) => {
        font.querySelectorAll('span[class^="fs-"]').forEach((inner) => inner.replaceWith(...inner.childNodes));
        if (cls) {
            const span = document.createElement('span');
            span.className = cls;
            span.append(...font.childNodes);
            font.replaceWith(span);
        } else font.replaceWith(...font.childNodes);
    });
};

// Список размеров шрифта в стиле базы: кнопка и панель вместо системного select.
// Нажатия не забирают фокус у редактора, поэтому выделенный текст сохраняется.
function initFontSizeMenus() {
    document.querySelectorAll('select[data-font-size]').forEach((select) => {
        const wrap = document.createElement('div');
        wrap.className = 'fs-menu';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'fs-menu__button';
        button.title = 'Размер шрифта';
        button.setAttribute('aria-haspopup', 'listbox');
        button.setAttribute('aria-expanded', 'false');
        button.innerHTML = '<span>Размер</span><svg class="kb-select__chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        const panel = document.createElement('div');
        panel.className = 'kb-select__panel fs-menu__panel';
        panel.hidden = true;
        const list = document.createElement('ul');
        list.className = 'kb-select__list';
        list.setAttribute('role', 'listbox');
        [...select.options].forEach((option) => {
            if (option.disabled) return;
            const item = document.createElement('li');
            item.setAttribute('role', 'option');
            item.textContent = option.textContent;
            item.addEventListener('mousedown', (e) => e.preventDefault());
            item.addEventListener('click', () => {
                select.value = option.value;
                select.dispatchEvent(new Event('change'));
                close();
            });
            list.append(item);
        });
        panel.append(list);
        const close = () => {
            panel.hidden = true;
            button.setAttribute('aria-expanded', 'false');
        };
        button.addEventListener('mousedown', (e) => e.preventDefault());
        button.addEventListener('click', () => {
            if (!panel.hidden) return close();
            const below = window.innerHeight - button.getBoundingClientRect().bottom;
            wrap.classList.toggle('opens-up', below < 300);
            panel.hidden = false;
            button.setAttribute('aria-expanded', 'true');
        });
        document.addEventListener('click', (e) => {
            if (!wrap.contains(e.target)) close();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });
        select.hidden = true;
        select.before(wrap);
        wrap.append(button, panel, select);
    });
}

