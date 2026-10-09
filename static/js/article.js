document.addEventListener('DOMContentLoaded', () => {
    const content = document.getElementById('article-content'),
        toc = document.getElementById('article-toc');
    const headings = [...content.querySelectorAll('h2,h3')];
    if (headings.length) {
        toc.hidden = false;
        const nav = toc.querySelector('nav');
        headings.forEach((heading, index) => {
            if (!heading.id || document.getElementById(heading.id) !== heading)
                heading.id = 'article-heading-' + index;
            const link = document.createElement('a');
            link.href = '#' + encodeURIComponent(heading.id);
            link.textContent = heading.textContent;
            link.className = heading.tagName === 'H3' ? 'toc-child' : '';
            nav.append(link);
        });
        const media = matchMedia('(max-width:1100px)');
        const sync = () => (toc.querySelector('details').open = !media.matches);
        media.addEventListener('change', sync);
        sync();
    }
    document
        .querySelector('[data-copy-link]')
        ?.addEventListener('click', async () => {
            const label = document.getElementById('copy-feedback');
            try {
                await navigator.clipboard.writeText(location.href);
                label.textContent = 'Ссылка скопирована';
            } catch (e) {
                label.textContent = 'Скопируйте адрес из строки браузера.';
            }
        });
    const form = document.getElementById('comment-form'),
        field = document.getElementById('comment-text');
    field?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            if (field.value.trim()) form.requestSubmit();
        }
    });
    const diagrams = [...content.querySelectorAll('.mermaid')].map((node) => ({
        node,
        source: node.textContent,
    }));
    let rendering = Promise.resolve();
    function renderDiagrams() {
        rendering = rendering.then(async () => {
            if (!window.mermaid || !diagrams.length) return;
            const dark = document.documentElement.dataset.theme === 'dark';
            mermaid.initialize({
                startOnLoad: false,
                securityLevel: 'strict',
                theme: dark ? 'dark' : 'neutral',
                fontFamily: 'Manrope, sans-serif',
            });
            for (const item of diagrams) {
                item.node.removeAttribute('data-processed');
                item.node.textContent = item.source;
            }
            try {
                await mermaid.run({ nodes: diagrams.map((item) => item.node) });
            } catch (e) {
                for (const item of diagrams) {
                    item.node.textContent = item.source;
                    item.node.setAttribute(
                        'aria-label',
                        'Исходный код диаграммы',
                    );
                }
            }
        });
    }
    document.addEventListener('rubbles:theme', renderDiagrams);
    renderDiagrams();
});
