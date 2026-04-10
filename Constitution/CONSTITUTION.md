# 📜 CONSTITUTION DU PROJET
**Date d'initialisation :** 2026-04-08

## RÈGLE CRITIQUE - INSTALLATION NPM
1. Ne jamais inventer une version NPM.
2. Pour les outils de tooling sans version confirmée, utiliser `latest`.
3. `vite-plugin-eslint` doit rester en `devDependencies` et en `latest`.
4. Si `react` et/ou `react-dom` sont installés, forcer `@types/react` et `@types/react-dom` en `devDependencies`.
