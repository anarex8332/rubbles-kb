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
                .querySelectorAll('details.action-menu[open]')
                .forEach((menu) => {
                    menu.open = false;
                    menu.querySelector('summary').focus();
                });
    });
    document.addEventListener('click', (e) =>
        document
            .querySelectorAll('details.action-menu[open]')
            .forEach((menu) => {
                if (!menu.contains(e.target)) menu.open = false;
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
        trigger = document.querySelector('.sidebar-toggle'),
        backdrop = document.querySelector('.sidebar-backdrop');
    if (!sidebar || !trigger) return;
    const mobile = matchMedia('(max-width:768px)');
    let previousFocus;
    function open(value, restore = true) {
        if (value) previousFocus = document.activeElement;
        document.body.classList.toggle('sidebar-is-open', value);
        backdrop.hidden = !value;
        trigger.setAttribute('aria-expanded', String(value));
        sidebar.inert = mobile.matches && !value;
        if (value) sidebar.querySelector('a,button').focus();
        else if (restore && previousFocus) previousFocus.focus();
    }
    trigger.addEventListener('click', () => {
        if (mobile.matches)
            open(!document.body.classList.contains('sidebar-is-open'));
        else {
            const collapsed = document.body.classList.toggle(
                'sidebar-is-collapsed',
            );
            sidebar.inert = collapsed;
            trigger.setAttribute('aria-expanded', String(!collapsed));
            try {
                localStorage.setItem(
                    'kb_sidebar_collapsed',
                    collapsed ? '1' : '0',
                );
            } catch (e) {}
        }
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
        document.body.classList.toggle('sidebar-is-collapsed', collapsed);
        sidebar.inert = mobile.matches || collapsed;
        trigger.setAttribute(
            'aria-expanded',
            String(!mobile.matches && !collapsed),
        );
    }
    mobile.addEventListener('change', resize);
    resize();
}
