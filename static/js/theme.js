document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle');

    if (!themeToggleBtn) return; // Guard clause if missing

    // Toggle theme
    themeToggleBtn.addEventListener('click', () => {
        // Toggle theme class and save preference
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }

        // Dispatch an event so Chart.js or other components can respond
        window.dispatchEvent(new Event('theme-changed'));
    });
});
