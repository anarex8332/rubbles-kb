document.addEventListener('DOMContentLoaded', () => {
    const content = document.getElementById('article-content'),
        toc = document.getElementById('article-toc');
    // В оглавлении только разделы второго уровня, иначе в длинной статье блок вытесняет замечания
    const headings = [...content.querySelectorAll('h2')];
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
    const looksLikeCode = (text) =>
        /^\s*(insert\s+into|select|update|delete\s+from|create\s|with\s|alter\s|drop\s|curl\s|\{|\[|<\?|def\s|function\s)/i.test(text) ||
        (text.match(/"[^"]+"\s*:/g) || []).length >= 3;
    content.querySelectorAll('blockquote').forEach((quote) => {
        const text = [...quote.children].length
            ? [...quote.children].map((n) => n.innerText).join('\n')
            : quote.innerText;
        if (!looksLikeCode(text.trim())) return;
        const pre = document.createElement('pre');
        pre.textContent = text.trim();
        quote.replaceWith(pre);
    });
    // Формулы, вынесенные отдельной строкой (например «BIAS = SUM(...) / SUM(...) - 1»),
    // показываются моноширинным шрифтом без отдельного окна.
    const looksLikeFormula = (text) =>
        text.length <= 220 &&
        !/https?:/.test(text) &&
        /^[A-Za-z_][\w.\[\]]*\s*(=(?!=)\s*(?![А-Яа-яЁё])|\(\s*\w+\s*:|:=)/.test(text);
    content.querySelectorAll('p, div').forEach((node) => {
        if (node.closest('pre, .code-block, table') || node.querySelector('p, div, img')) return;
        if (looksLikeFormula(node.textContent.trim())) node.classList.add('formula');
    });
    content.querySelectorAll('blockquote').forEach((quote) => {
        const parts = [...quote.children].filter((n) => n.textContent.trim());
        if (parts.length && parts.every((n) => n.classList.contains('formula')))
            quote.classList.add('formula-group');
    });
    content.querySelectorAll('pre:not(.mermaid)').forEach((pre) => {
        if (pre.closest('.code-block')) return;
        const wrap = document.createElement('div');
        wrap.className = 'code-block';
        const bar = document.createElement('div');
        bar.className = 'code-block__bar';
        const label = document.createElement('span');
        label.textContent = /^\s*(insert|select|update|delete|create|with|alter|drop)\b/i.test(pre.textContent) ? 'SQL' : 'Код';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'code-block__copy';
        button.textContent = 'Копировать';
        button.addEventListener('click', async () => {
            const text = pre.textContent;
            try {
                await navigator.clipboard.writeText(text);
            } catch (e) {
                const area = document.createElement('textarea');
                area.value = text;
                document.body.append(area);
                area.select();
                document.execCommand('copy');
                area.remove();
            }
            button.textContent = 'Скопировано';
            setTimeout(() => (button.textContent = 'Копировать'), 1800);
        });
        bar.append(label, button);
        pre.replaceWith(wrap);
        wrap.append(bar, pre);
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
