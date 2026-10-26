// Замечания к фрагментам текста: выделить текст → кнопка замечания → форма справа.
// Фрагмент хранится как цитата, соседний текст и позиция; по нажатию на замечание он подсвечивается в статье.
document.addEventListener('DOMContentLoaded', () => {
    const content = document.getElementById('article-content'),
        bar = document.getElementById('article-bar'),
        button = document.getElementById('remark-add'),
        form = document.getElementById('remark-form'),
        hint = document.getElementById('remark-hint');
    if (!content || !bar) return;

    // Высота закреплённой строки нужна правой колонке, чтобы та не уезжала под неё
    const syncBar = () => {
        document.documentElement.style.setProperty('--article-bar-h', bar.offsetHeight + 'px');
        const top = parseFloat(getComputedStyle(bar).top) || 0;
        bar.classList.toggle('is-stuck', bar.getBoundingClientRect().top <= top + 0.5 && window.scrollY > 0);
    };
    window.addEventListener('scroll', syncBar, { passive: true });
    window.addEventListener('resize', syncBar);
    syncBar();

    const CONTEXT = 60;
    const fullText = () => {
        const range = document.createRange();
        range.selectNodeContents(content);
        return range.toString();
    };
    const offsetOf = (node, offset) => {
        const range = document.createRange();
        range.selectNodeContents(content);
        range.setEnd(node, offset);
        return range.toString().length;
    };

    if (button && form) {
        button.addEventListener('mousedown', (e) => e.preventDefault());
        button.addEventListener('click', () => {
            const selection = window.getSelection();
            const range = selection.rangeCount ? selection.getRangeAt(0) : null;
            const quote = range ? range.toString().trim() : '';
            if (!range || !quote || !content.contains(range.commonAncestorContainer)) {
                hint.hidden = false;
                form.hidden = true;
                clearTimeout(hint.timer);
                hint.timer = setTimeout(() => (hint.hidden = true), 4000);
                hint.scrollIntoView({ block: 'nearest' });
                return;
            }
            const text = fullText();
            const raw = range.toString();
            const start = offsetOf(range.startContainer, range.startOffset) + (raw.length - raw.trimStart().length);
            const end = start + quote.length;
            form.elements.quote.value = quote;
            form.elements.prefix.value = text.slice(Math.max(0, start - CONTEXT), start);
            form.elements.suffix.value = text.slice(end, end + CONTEXT);
            form.elements.position.value = start;
            form.querySelector('.remark-form__quote').textContent = quote.length > 200 ? quote.slice(0, 200) + '…' : quote;
            hint.hidden = true;
            form.hidden = false;
            clearMarks();
            mark(start, end, 'is-active');
            selection.removeAllRanges();
            form.elements.text.focus();
        });
        form.querySelector('[data-remark-cancel]').addEventListener('click', () => {
            form.hidden = true;
            form.reset();
            clearMarks();
        });
    }

    // Поиск фрагмента: все вхождения цитаты, лучшее — с совпадающим соседним текстом и ближе к прежней позиции
    function locate(card) {
        const text = fullText(),
            quote = card.dataset.quote;
        if (!quote) return null;
        const prefix = card.dataset.prefix || '',
            suffix = card.dataset.suffix || '',
            position = Number(card.dataset.position) || 0;
        let best = null;
        for (let i = text.indexOf(quote); i !== -1; i = text.indexOf(quote, i + 1)) {
            let score = -Math.abs(i - position) / 10000;
            if (prefix && text.slice(Math.max(0, i - prefix.length), i) === prefix) score += 2;
            if (suffix && text.slice(i + quote.length, i + quote.length + suffix.length) === suffix) score += 2;
            if (!best || score > best.score) best = { start: i, end: i + quote.length, score };
        }
        return best;
    }

    function clearMarks() {
        content.querySelectorAll('mark.remark-mark').forEach((m) => {
            const parent = m.parentNode;
            m.replaceWith(...m.childNodes);
            parent.normalize();
        });
    }

    // Оборачиваем каждый текстовый узел внутри [start, end) отдельно, чтобы не ломать разметку
    function mark(start, end, cls) {
        const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
        const parts = [];
        let pos = 0;
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const len = node.data.length;
            const from = Math.max(start, pos),
                to = Math.min(end, pos + len);
            if (from < to) parts.push([node, from - pos, to - pos]);
            pos += len;
            if (pos >= end) break;
        }
        const marks = [];
        parts.forEach(([node, from, to]) => {
            if (!node.data.slice(from, to).trim()) return;
            const range = document.createRange();
            range.setStart(node, from);
            range.setEnd(node, to);
            const el = document.createElement('mark');
            el.className = 'remark-mark ' + (cls || '');
            range.surroundContents(el);
            marks.push(el);
        });
        return marks;
    }

    const cards = [...document.querySelectorAll('.remark[data-quote]')];
    function activate(card, scroll) {
        cards.forEach((c) => c.classList.toggle('is-active', c === card));
        clearMarks();
        const found = locate(card);
        card.querySelector('.remark__lost').hidden = !!found;
        if (!found) return;
        const marks = mark(found.start, found.end, 'is-active');
        marks.forEach((m) => (m.dataset.remark = card.id));
        if (scroll && marks[0]) marks[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    // Нажатие на замечание разворачивает его (ответы и форма ответа) и подсвечивает фрагмент; повторное — сворачивает
    function toggle(card) {
        const open = !card.classList.contains('is-open');
        cards.forEach((c) => {
            c.classList.remove('is-open');
            c.querySelector('.remark__summary').setAttribute('aria-expanded', 'false');
        });
        if (!open) {
            card.classList.remove('is-active');
            clearMarks();
            return;
        }
        card.classList.add('is-open');
        card.querySelector('.remark__summary').setAttribute('aria-expanded', 'true');
        activate(card, true);
    }
    cards.forEach((card) => {
        const summary = card.querySelector('.remark__summary');
        summary.addEventListener('click', () => toggle(card));
        summary.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggle(card);
            }
        });
    });
    // Enter отправляет замечание или ответ, Shift+Enter переносит строку
    document.querySelectorAll('#remark-form textarea, .remark-reply-form textarea').forEach((field) => {
        field.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
            e.preventDefault();
            if (field.value.trim()) field.form.requestSubmit();
        });
    });
    // Щелчок в любом месте вне замечания сворачивает открытое замечание и снимает подсветку
    document.addEventListener('click', (e) => {
        const open = cards.find((c) => c.classList.contains('is-open'));
        if (!open || open.contains(e.target) || !e.target.isConnected) return;
        if (e.target.closest('#remark-add, #remark-form, mark.remark-mark')) return;
        open.classList.remove('is-open', 'is-active');
        open.querySelector('.remark__summary').setAttribute('aria-expanded', 'false');
        clearMarks();
    });
    const target = location.hash && document.querySelector(location.hash);
    if (target && target.classList.contains('remark')) {
        target.closest('details')?.setAttribute('open', '');
        target.scrollIntoView({ block: 'nearest' });
        toggle(target);
    }
});
