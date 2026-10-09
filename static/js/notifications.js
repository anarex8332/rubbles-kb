document.addEventListener('DOMContentLoaded', () => {
    const area = document.getElementById('notification-toasts');
    if (!area) return;
    const bell = document.querySelector('.notification-bell');
    const key = 'rubbles-notification-seen:' + area.dataset.user;
    let last = 0,
        busy = false;
    try {
        last = Number(localStorage.getItem(key)) || 0;
    } catch {}
    async function check() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            const response = await fetch(area.dataset.url + '?after=' + last, {
                cache: 'no-store',
            });
            if (!response.ok) return;
            const data = await response.json();
            let dot = bell?.querySelector('.notification-dot');
            if (data.unread && bell && !dot) {
                dot = document.createElement('span');
                dot.className = 'notification-dot';
                bell.append(dot);
            }
            if (!data.unread) dot?.remove();
            bell?.setAttribute(
                'aria-label',
                data.unread
                    ? 'Уведомления: ' + data.unread + ' непрочитанных'
                    : 'Уведомления',
            );
            for (const item of data.items) {
                if (item.id <= last) continue;
                const toast = document.createElement('div');
                toast.className = 'notification-toast';
                const link = document.createElement('a');
                link.href = item.url;
                const chars = Array.from(item.text);
                link.textContent =
                    'Вам уведомление: ' +
                    chars.slice(0, 100).join('') +
                    (chars.length > 100 ? '…' : '');
                const close = document.createElement('button');
                close.type = 'button';
                close.textContent = '×';
                close.setAttribute('aria-label', 'Закрыть уведомление');
                close.onclick = () => toast.remove();
                toast.append(link, close);
                area.append(toast);
                while (area.children.length > 3)
                    area.firstElementChild.remove();
                setTimeout(() => toast.remove(), 12000);
                last = Math.max(last, item.id);
            }
            if (!data.items.length) last = Math.max(last, data.latest);
            try {
                localStorage.setItem(key, String(last));
            } catch {}
        } catch {
        } finally {
            busy = false;
        }
    }
    check();
    setInterval(check, 5000);
    document.addEventListener('visibilitychange', check);
});
