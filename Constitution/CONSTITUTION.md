# 📜 Constitution du Projet (Store-Manager)

## ⚖️ Principes Fondamentaux
- **Sanctuarisation** : Le code validé ne doit être modifié que sur ordre explicite.
- **Additivité** : Privilégier l'ajout de code plutôt que la modification de l'existant.
- **Zéro Placeholder** : Pas de `TODO`, `FIXME` ou fonctions vides.

## 🔧 Configuration TC (ES Modules - ESM Obligatoire)

**Tous les projets Speckit.Factory doivent être configurés en ES Modules (ESM).**

### Backend Configuration
- **Type**: `"type": "module"` (obligatoire dans `backend/package.json`)
- **TypeScript**: `tsconfig.json` avec `"module": "ESNext"` et `"target": "ES2022"`
- **Exécution**: `ts-node --esm` ou `nodemon --exec ts-node --esm`
- **Build Output**: `dist/` avec fichiers `.js` compilés depuis TypeScript
- **Imports**: Tous les chemins relatifs doivent inclure l'extension `.js` (ex: `import { User } from "./models/user.js"`)
- **Interdiction**: Zéro usage de `require()` ou `import ... = require()`

### Frontend Configuration
- **Type**: `"type": "module"` (Vite gère cela nativement)
- **Build**: Vite crée des bundles ESM par défaut
- **Imports**: Aucune extension requise sur les imports locaux (Vite normalise)

---

## 🎨 Design Constitution (Figma Maker Style)
L'intelligence graphique du projet est pilotée par le subagent `GraphicDesign` et basée sur l'extraction d'intelligence visuelle sur mesure.

### Principes Graphiques
- **Design Cohérent & Sur Mesure** : Le projet suit un pattern unique extrait des références utilisateur (Pinterest, ChatGPT ou image).
- **Réactivité** : Design "Mobile-First" utilisant Tailwind CSS rigoureusement.
- **Identité Visuelle** : 
  - **Custom Pattern (Prioritaire)** : Le système de design généré spécifiquement pour ce projet (stocké dans `design/dataset/custom_pattern.json`).
  - **Premium** : Palette moderne, ombres douces et typographie haute performance.

### Règles de Mise en Page
- **Conteneurs** : `max-w-7xl mx-auto px-6`
- **Extraction de Tokens** : Les couleurs (#hex), le radius et les ombres sont définis dynamiquement par la phase de `Vision Pattern`.

### Composants Types
- **Cartes** : `rounded-[radius] shadow-xl border border-gray-100` (Adapté du pattern custom).
- **Boutons** : Formes et couleurs extraites de l'intelligence visuelle.

