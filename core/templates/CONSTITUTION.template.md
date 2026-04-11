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

### 1.0 ⚠️ DIRECTIVE ESM OBLIGATOIRE (CRITIQUE)
**TOUS les projets Speckit.Factory DOIVENT être configurés en ES Modules (ESM).** Cette directive surpasse toute autre configuration.

#### Backend ESM Configuration (OBLIGATOIRE)
- **package.json** DOIT contenir : `"type": "module"`
- **tsconfig.json** DOIT contenir :
  ```json
  {
    "compilerOptions": {
      "module": "NodeNext",
      "moduleResolution": "NodeNext",
      "ignoreDeprecations": "6.0",
      "target": "ES2022"
    }
  }
  ```
- **Imports au backend** : TOUS les chemins relatifs DOIVENT inclure l'extension `.js`
  - ✅ `import { User } from "./models/user.js"`
  - ❌ `import { User } from "./models/user"` (INTERDIT)
  - ❌ `import User = require("./models/user")` (CommonJS INTERDIT)
- **Scripts npm** (backend/package.json) :
  ```json
  {
    "scripts": {
      "dev": "cross-env NODE_OPTIONS='--loader ts-node/esm' nodemon --exec ts-node --esm src/app.ts",
      "build": "tsc",
      "start": "node dist/app.js"
    },
    "devDependencies": {
      "ts-node": "^10.9.0",
      "cross-env": "^7.0.0"
    }
  }
  ```

#### Frontend ESM Configuration (OBLIGATOIRE)
- **package.json** DOIT contenir : `"type": "module"`
- Vite gère ESM nativement - aucune configuration supplémentaire requise

**ZÉRO EXCEPTION** : Si ESM n'est pas configuré, le projet est cassé et non-conforme.

---

### 1.1 Backend
* **Langage** : Node.js 20, TypeScript (Configuration : ES Modules, Target: ES2022)
* **TypeScript** : Oui. Un fichier `tsconfig.json` DOIT impérativement être présent à la racine du dossier `/backend`.
* **Framework Core** : [Ex: Express, NestJS, Fastify]
* **Base de données** : (Sélectionner UNE SEULE option, mutuelle exclusion)
    - **Option A: MongoDB (NoSQL)** : MongoDB 6+ via Mongoose (^8.0.0). *Scripts npm* : Aucun script Prisma.
    - **Option B: PostgreSQL Local (SQL)** : PostgreSQL 16+ via Prisma (5.13.0). *Scripts npm requis* : `prisma:generate`, `prisma:migrate`, `prisma:setup` (voir package.json).
    - **Option C: Supabase (PostgreSQL Cloud)** : PostgreSQL 16+ (cloud-managed) via Prisma (5.13.0). *Scripts npm requis* : `prisma:generate`, `prisma:migrate`, `prisma:setup`.
* **Scripts npm (Backend)** :
    ```json
    {
      "scripts": {
        "dev": "cross-env NODE_OPTIONS='--loader ts-node/esm' nodemon --exec ts-node --esm src/app.ts",
        "build": "tsc",
        "start": "node dist/index.js",
        "prisma:generate": "prisma generate",
        "prisma:migrate": "prisma migrate dev",
        "prisma:setup": "prisma generate && prisma migrate dev --name init"
      }
    }
    ```
    **NOTES** :
    - `prisma:setup` **NE DOIT être utilisé que pour la première initialisation** d'une BD PostgreSQL/Supabase.
    - Pour MongoDB, les scripts Prisma ne sont pas applicables.
    - La clé `prisma:*` ne doit exister que si PostgreSQL ou Supabase est sélectionné.
* **Authentification** : [Ex: JWT, Passport.js, NextAuth]
* **Configuration .env (Backend)** :
    - **Si MongoDB** : `MONGODB_URI`, `JWT_SECRET`, `NODE_ENV`, `PORT`
    - **Si PostgreSQL Local** : `DATABASE_URL`, `JWT_SECRET`, `NODE_ENV`, `PORT` (optionnels : `DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`)
    - **Si Supabase** : `DATABASE_URL` (format Supabase), `SUPABASE_PROJECT_ID`, `SUPABASE_API_KEY`, `SUPABASE_URL`, `JWT_SECRET`, `NODE_ENV`, `PORT`

### 1.2 Frontend (Si applicable)
* **Langage** : TypeScript (Configuration : ES Modules, Target: ES2022)
* **TypeScript** : Oui. Un fichier `tsconfig.json` DOIT impérativement être présent à la racine du dossier `/frontend`.
* **Framework** : [Ex: 
    - **Option A: React 18 avec Vite** : React (^18.0.0) + Vite (^5.0.0) + react-router-dom (^6.22.3)
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

### 1.3 Outillage & Tests (VERSIONNING NPM STRICT)
* **Linter/Formatter** : [Ex: ESLint, Prettier]
* **Tests** : [Ex: Jest (29.7.0), Vitest, Supertest (pour API)]
* **Classification NPM (STRICTE)** : 
    - `dependencies` : Uniquement packages de production (express, mongoose, etc.).
    - `devDependencies` : Outils de dev (typescript, nodemon, eslint, prettier, jest, etc.).
    - TOUT paquet `@types/*` **DOIT** être dans `devDependencies`.
* **Note** : Appliquer la Directive de Sécurité NPM (ci-dessous) pour tout ajout/mise à jour de dépendance.

### 1.4 RÈGLE CRITIQUE - INSTALLATION NPM (ANTI-HALLUCINATION)
Lors de l'ajout de dépendances dans `package.json` ou via CLI:
1. Interdiction formelle de générer des numéros de version fixes de mémoire (ex: `1.2.3`).
2. OBLIGATION d'utiliser le tag `@latest` pour toute nouvelle dépendance ajoutée via CLI (ex: `npm install @vitejs/plugin-react@latest`).
3. Si l'IA écrit directement dans `package.json`, utiliser les versions caret standards:
   - `react`: `^18.0.0`
   - `vite`: `^5.0.0`
   - `@vitejs/plugin-react`: `^4.0.0`
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
 L'identité visuelle et l'expérience utilisateur sont pilotées par l'agent `GraphicDesign` et basées sur l'extraction d'intelligence visuelle (Type "Figma Maker"). 
 
 ### 5.1 Principes de Design
 * **Design Cohérent & Sur Mesure** : Le projet suit un pattern unique extrait des références utilisateur (Pinterest, ChatGPT ou image).
 * **Réactivité (Responsive)** : Utilisation rigoureuse des classes Tailwind pour tous les formats d'écran.
 
 ### 5.2 Systèmes de Design
 * **Custom Pattern (Prioritaire)** : Le système de design généré spécifiquement pour ce projet (stocké dans `design/dataset/custom_pattern.json`). TOUS les composants doivent s'y conformer.
 * **Premium** : Style de repli professionnel, minimaliste et moderne.
 
 ### 5.3 Règles de composants
 * **Extraction de Tokens** : Les couleurs, radius et ombres sont définis dynamiquement par la phase de `Vision Pattern`.
 
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
