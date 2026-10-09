(() => {
    const system = matchMedia('(prefers-color-scheme: dark)');
    let preference = 'system';
    try {
        preference = localStorage.getItem('rubbles-theme') || 'system';
    } catch (e) {}
    if (!['light', 'dark', 'system'].includes(preference))
        preference = 'system';
    function apply() {
        const theme =
            preference === 'system'
                ? system.matches
                    ? 'dark'
                    : 'light'
                : preference;
        document.documentElement.dataset.theme = theme;
        document.documentElement.style.colorScheme = theme;
        document.dispatchEvent(
            new CustomEvent('rubbles:theme', { detail: theme }),
        );
    }
    window.RubblesTheme = {
        get preference() {
            return preference;
        },
        set(value) {
            preference = ['light', 'dark', 'system'].includes(value)
                ? value
                : 'system';
            try {
                localStorage.setItem('rubbles-theme', preference);
            } catch (e) {}
            apply();
        },
    };
    system.addEventListener('change', () => {
        if (preference === 'system') apply();
    });
    apply();
})();
