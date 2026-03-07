# ⚖️ CONSTITUTION : PROJECT STORE-MANAGER (CRUD)

## 1. VISION ET OBJECTIFS
Développement d'une application de gestion d'articles pour un magasin.
L'objectif est de fournir une interface simple pour Créer, Lire, Mettre à jour et Supprimer des produits.

## 2. ARCHITECTURE TECHNIQUE
Le projet suit une séparation stricte entre le Frontend et le Backend.

### Dossiers :
- `/backend` : API REST (Node.js/Express ou Python/FastAPI)
- `/frontend` : Interface Utilisateur (React ou Vue.js)
- `/Constitution` : Gouvernance et Étapes
- `/Task_App1` : Spécifications
- `/Task1` : Implémentation technique

### 1.2 Frontend (Si applicable)
* **Langage** : TypeScript
* **Framework** : React 18 (^18.2.0) avec Vite (^5.1.4)
* **Routage** : react-router-dom (^6.22.3)
* **Tests** : Jest (^29.7.0)
* **Styling** : Vanilla CSS

## 3. STANDARDS DE DÉVELOPPEMENT
- **API** : RESTful, format JSON.
- **Sécurité** : Hachage des mots de passe avec bcrypt.
- **Code** : Modulaire, principes SOLID.
- **Structure** : Dossiers Frontend et Backend séparés à la racine.
- **Tolérance de démarrage** : Les règles de validation (Zod) et les middlewares de sécurité ne sont exigés qu'à partir de l'implémentation de la première route métier (CRUD). Les étapes de "Configuration" ou "Setup" sont exemptées si les bibliothèques sont présentes dans le package.json.

## 4. SCHÉMA DE DONNÉES (PRODUIT)
- `name` : String (Requis)
- `description` : String
- `price` : Number (Requis)
- `stock` : Number (Défaut: 0)
- `category` : String
- `createdAt` : Date
