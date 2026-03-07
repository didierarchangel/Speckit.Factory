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
* **Langage** : [Ex: Node.js 20, TypeScript]
* **Framework Core** : [Ex: Express, NestJS, Fastify]
* **Base de données** : [Ex: MongoDB via Mongoose, PostgreSQL 16 via Prisma]
* **Authentification** : [Ex: JWT, Passport.js, NextAuth]

### 1.2 Frontend (Si applicable)
* **Langage** : [Ex: TypeScript]
* **Framework** : [Ex: React 18 (^18.2.0) avec Vite (^5.1.4)]
* **Routage** : [Ex: react-router-dom (^6.22.3)]
* **Styling** : [Ex: Tailwind CSS, Vanilla CSS]

### 1.3 Outillage & Tests (Préférer des versions fixes)
* **Linter/Formatter** : [Ex: ESLint, Prettier]
* **Tests** : [Ex: Jest (^29.7.0), Vitest, Supertest (pour API)]

---

## 2. RÈGLES D'ARCHITECTURE (LE SANCTUAIRE)
### 2.1 Sanctuarisation du Code
* **Historique Validé** : L'état validé du code est le "Sanctuaire" du projet.
* **Règle d'Or** : Un agent ne peut JAMAIS modifier ou refactoriser une fonction existante dans l'historique validé sans un ordre explicite de l'utilisateur ("Bugfix" ou "Refactor"). Le code généré doit toujours être "additif" ou "complémentaire" par défaut.

### 2.2 Structure des Fichiers
* Les contrôleurs / routes doivent toujours se trouver dans : `[CHEMIN_SPECIFIQUE]`
* Les modèles de données doivent se trouver dans : `[CHEMIN_SPECIFIQUE]`

---

## 3. RÈGLES DE SÉCURITÉ ET QUALITÉ STRICTES
Chaque agent `VERIFY` (Auditeur) rejettera automatiquement le travail de l'agent `IMPL` s'il viole ces règles :
1. **Zéro Placeholder** : Interdiction absolue des `FIXME`, `TODO` ou des fonctions mockées du style `pass` ou `return "à implémenter"`.
2. **Validation des Entrées** : Toute donnée provenant de l'utilisateur ou d'une API externe doit être typée et validée (Ex: *Pydantic*, *Zod*).
3. **Séparation des Responsabilités (SOLID)** : Pas de logique métier complexe directement dans les routes de l'API.
4. **Tolérance de démarrage** : Les règles de validation (Zod) et les middlewares de sécurité ne sont exigés qu'à partir de l'implémentation de la première route métier (CRUD). Les étapes de "Configuration" ou "Setup" sont exemptées si les bibliothèques sont présentes dans le package.json.

---

## 4. NORMES DE DÉVELOPPEMENT (COHÉRENCE)
### 4.1 Backend (NestJS/TypeScript)
* **Décorateurs** : Activer obligatoirement `experimentalDecorators: true` dans le `tsconfig.json`.
* **Validation** : Toute API doit utiliser des DTO avec `class-validator` et `class-transformer`.
* **Zéro Placeholder** : Tout code généré doit être complet et fonctionnel.

### 4.2 Frontend (React/Vite)
* **Composants** : Préférer les composants fonctionnels avec Hooks.
* **Typage** : TypeScript strict activé.

---

## 5. FORMAT TÂCHES ET TRAÇABILITÉ
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
