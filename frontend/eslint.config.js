import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react },
    settings: { react: { version: 'detect' } },
    rules: { 'react/jsx-uses-vars': 'error' },
  },
  {
    // Build/config files run in Node, not the browser.
    files: ['*.config.js', '*.config.cjs'],
    languageOptions: { globals: globals.node },
  },
]
