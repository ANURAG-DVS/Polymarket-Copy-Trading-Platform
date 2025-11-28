module.exports = {
    root: true,
    extends: [
        'next/core-web-vitals',
        'plugin:@typescript-eslint/recommended',
    ],
    parser: '@typescript-eslint/parser',
    plugins: ['@typescript-eslint'],
    rules: {
        '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
        '@typescript-eslint/no-explicit-any': 'warn',
        '@typescript-eslint/explicit-module-boundary-types': 'off',
        'react-hooks/exhaustive-deps': 'warn',
        'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
}
