import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import react from "eslint-plugin-react";

export default [
  { ignores: ["dist"] },
  js.configs.recommended,
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: { ecmaVersion: 2023, sourceType: "module", globals: { ...globals.browser, ...globals.node, ...globals.vitest }, parserOptions: { ecmaFeatures: { jsx: true } } },
    plugins: { "react-hooks": reactHooks, react },
    rules: { ...reactHooks.configs.recommended.rules, "react/jsx-uses-vars": "error", "react/jsx-uses-react": "error", "no-unused-vars": ["error", { varsIgnorePattern: "^_" }] },
  },
];
