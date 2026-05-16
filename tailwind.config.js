/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ['./*.html'],
    theme: {
        extend: {
            colors: {
                daad: {
                    ink: '#fafaf7',
                    night: '#0c0808',
                    panel: 'rgba(12, 8, 8, 0.72)',
                    line: 'rgba(255, 255, 255, 0.18)',
                },
            },
            fontFamily: {
                display: ['"Bebas Neue"', 'sans-serif'],
                sans: ['Barlow', 'system-ui', 'sans-serif'],
            },
            boxShadow: {
                daad: '0 0 0 1px rgba(255, 255, 255, 0.12), 0 22px 48px rgba(0, 0, 0, 0.55)',
            },
        },
    },
    plugins: [],
};
