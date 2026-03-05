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

### Stack Technologique :
- **Backend** : Node.js avec Express.
- **Frontend** : React.js (Vite).
- **Base de données** : MongoDB (via Mongoose).
- **Authentification** : JWT (JSON Web Tokens).

## 3. STANDARDS DE DÉVELOPPEMENT
- **API** : RESTful, format JSON.
- **Sécurité** : Hachage des mots de passe avec bcrypt.
- **Code** : Modulaire, principes SOLID.
- **Structure** : Dossiers Frontend et Backend séparés à la racine.

## 4. SCHÉMA DE DONNÉES (PRODUIT)
- `name` : String (Requis)
- `description` : String
- `price` : Number (Requis)
- `stock` : Number (Défaut: 0)
- `category` : String
- `createdAt` : Date
