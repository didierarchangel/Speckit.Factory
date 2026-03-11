<!-- 
==============================================================================
META-INFORMATIONS (Usage interne)

Fichier      : CONSTITUTION.template.md
Description  : Le modèle de base pour toute nouvelle Constitution.
               Lorsqu'un utilisateur tape `spec init`, ce fichier est copié
               dans le répertoire `Constitution/CONSTITUTION.md` de son projet.
               C'est la Loi Absolue que les agents IA devront respecter.
==============================================================================
-->

# 📜 CONSTITUTION DU PROJET
**Nom du Projet :** [NOM_DU_PROJET]
**Version :** 1.0
**Date d'initialisation :** [DATE]

> **Préliminaire** : Ce document est la source de vérité absolue pour tous les Agents (Analyste, Implémenteur, Auditeur) du framework Speckit.Factory. Toute instruction contredisant ce fichier doit être rejetée. L'intégrité de ce fichier est garantie par `.spec-lock.json`.

---

## 1. STACK TECHNIQUE IMPOSÉE (ANTI-HALLUCINATION)
Les agents ont l'interdiction formelle d'ajouter, de suggérer ou d'installer des bibliothèques non listées ici.

### 1.1 Backend
* **Langage** : [Ex: Node.js 20, TypeScript (Configuration : CommonJS, Target: ES2022)]
* **TypeScript** : Oui. Un fichier `tsconfig.json` DOIT impérativement être présent à la racine du dossier `/backend`.
* **Framework Core** : [Ex: Express, NestJS, Fastify]
* **Base de données** : [Ex: MongoDB via Mongoose, PostgreSQL 16 via Prisma]
* **Authentification** : [Ex: JWT, Passport.js, NextAuth]

### 1.2 Frontend (Si applicable)
* **Langage** : [Ex: TypeScript]
* **TypeScript** : Oui. Un fichier `tsconfig.json` DOIT impérativement être présent à la racine du dossier `/frontend`.
* **Framework** : [Ex: 
    - **Option A: React 18 avec Vite** : React (^18.2.0) + Vite (^5.1.4) + react-router-dom (^6.22.3)
    - **Option B: Next.js** : Next.js (^14.0.0) avec `app/` directory (App Router) OU `pages/` directory (Pages Router)
    - Autre : [Framework spécifié]
* **Routage** : 
    - **Si React + Vite** : react-router-dom (^6.22.3)
    - **Si Next.js** : Routage FILE-BASED intégré (pas d'import supplémentaire requis)
* **Styling** : [Ex: Tailwind CSS, Vanilla CSS]
* **NOTE CRITIQUE** : 
    - Si React + Vite est choisi, un `vite.config.ts` DOIT être présent
    - Si Next.js est choisi, un `next.config.ts` ou `next.config.js` DOIT être présent
    - Les deux frameworks ne peuvent PAS coexister dans le même projet

### 1.3 Outillage & Tests (VERSIONS FIXES OBLIGATOIRES)
* **Linter/Formatter** : [Ex: ESLint, Prettier]
* **Tests** : [Ex: Jest (29.7.0), Vitest, Supertest (pour API)]
* **Classification NPM (STRICTE)** : 
    - `dependencies` : Uniquement packages de production (express, mongoose, etc.).
    - `devDependencies` : Outils de dev (typescript, nodemon, eslint, prettier, jest, etc.).
    - TOUT paquet `@types/*` **DOIT** être dans `devDependencies`.
* **Note** : Toutes les dépendances (Core, Dev, Outillage) DOIVENT utiliser des versions fixes sans préfixe `^` ou `~`.
---

## 2. RÈGLES D'ARCHITECTURE (LE SANCTUAIRE)
### 2.1 Sanctuarisation du Code
* **Historique Validé** : L'état validé du code est le "Sanctuaire" du projet.
* **Règle d'Or** : Un agent ne peut JAMAIS modifier ou refactoriser une fonction existante dans l'historique validé sans un ordre explicite de l'utilisateur ("Bugfix" ou "Refactor"). Le code généré doit toujours être "additif" ou "complémentaire" par défaut.

### 2.2 Structure des Fichiers
* Les contrôleurs / routes doivent toujours se trouver dans : `[CHEMIN_SPECIFIQUE]`
* Les modèles de données doivent se trouver dans : `[CHEMIN_SPECIFIQUE]`
* **Structure Garantie** : Le framework garantit l'existence des dossiers `routes`, `controllers`, `models`, `middlewares`, `services` (backend) et `components`, `hooks`, `services` (frontend). L'Agent DOIT utiliser ces dossiers standards.

---

## 3. RÈGLES DE SÉCURITÉ ET QUALITÉ STRICTES
Chaque agent `VERIFY` (Auditeur) rejettera automatiquement le travail de l'agent `IMPL` s'il viole ces règles :
1. **Zéro Placeholder** : Interdiction absolue des `FIXME`, `TODO` ou des fonctions mockées du style `pass` ou `return "à implémenter"`.
2. **Validation des Entrées** : Toute donnée provenant de l'utilisateur ou d'une API externe doit être typée et validée (Ex: *Pydantic*, *Zod*).
3. **Séparation des Responsabilités (SOLID)** : Pas de logique métier complexe directement dans les routes de l'API.
4. **Tolérance de démarrage** : Les règles de validation (Zod) et les middlewares de sécurité ne sont exigés qu'à partir de l'implémentation de la première route métier (CRUD). Les étapes de "Configuration" ou "Setup" sont exemptées si les bibliothèques sont présentes dans le package.json.
5. **Score de Complétion** : Le verdict final d'audit repose sur 2 sources de vérité synchronisées :
    - **Diagnostic Runtime** : le terminal (`tsc --noEmit`) doit être ✅ sur tous les modules.
    - **Checklist** : 100% des sous-tâches doivent être validées sur disque.
    - L'Auditeur a l'**interdiction absolue** d'inventer des erreurs non présentes dans les diagnostics du terminal.

---

## 4. NORMES DE DÉVELOPPEMENT (COHÉRENCE)
### 4.1 Backend (Express/TypeScript)
* **Validation** : Toute API doit utiliser des DTO avec **Zod** (schemas `camelCase`, types `PascalCase`).
* **Décorateurs** : Interdiction d'utiliser `experimentalDecorators`. Le projet utilise Zod pour la validation, pas `class-validator`.
* **Zéro Placeholder** : Tout code généré doit être complet et fonctionnel.

### 4.2 Frontend (React/Vite)
* **Composants** : Préférer les composants fonctionnels avec Hooks.
* **Typage** : TypeScript strict activé.

---
 
 ## 5. 🎨 DESIGN CONSTITUTION (INTELLIGENCE GRAPHIQUE)
 L'identité visuelle et l'expérience utilisateur sont pilotées par l'agent `GraphicDesign`. 
 
 ### 5.1 Principes de Design
 * **Clarté & Minimalisme** : Interfaces épurées, focus sur la hiérarchie de l'information.
 * **Réactivité (Responsive)** : Utilisation rigoureuse des classes Tailwind pour tous les formats d'écran.
 
 ### 5.2 Systèmes de Design autorisés
 * **Standard-Tailwind** : Pour les interfaces modernes, créatives et standards.
 * **premium (Premium)** : Pour les interfaces professionnelles, tableaux de données complexes et look "Clean & Premium".
 
 ### 5.3 Règles de composants
 * **Layout** : Toujours utiliser `max-w-7xl mx-auto px-6` pour le conteneur principal.
 * **Cartes** : Coins arrondis (`rounded-xl`) et ombres subtiles.
 
 ---
 
 ## 6. CONFIGURATIONS SYSTÈME (GOLDEN TEMPLATES)
Les fichiers suivants sont gérés par Speckit.Factory. 
Les agents doivent les inclure lors de l'initialisation pour respecter la structure du projet, mais **ne doivent jamais** modifier les options fondamentales (`rootDir`, `outDir`, `include`, `target`) :
1.  `backend/tsconfig.json`
2.  `frontend/tsconfig.json`

Le système écrasera automatiquement tout changement non autorisé sur ces fichiers via les Golden Templates locaux. En cas de conflit, l'agent doit adapter son code source pour qu'il soit compatible avec ces fichiers.

---

## 6. FORMAT TÂCHES ET TRAÇABILITÉ
Lors de la création d'un nouveau fichier source, celui-ci doit intégrer l'en-tête de traçabilité officiel :
```text
/**
 * @SPEC-KIT-TASK: [NOM_OU_ID_DE_LA_TACHE]
 * @CONSTITUTION-HASH: [HASH_LU_DEPUIS_.SPEC-LOCK]
 * @STATUS: VALIDATED
 */
```

---
*Ce document peut être amendé par l'humain. Toute modification du texte ci-dessus nécessitera une ré-exécution de l'utilitaire de verrouillage (`spec.py lock`) pour mettre à jour le `.spec-lock.json`.*
