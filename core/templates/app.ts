// @ts-nocheck
/**
 * Backend Express.js - Application Principale
 * Configuration complète avec Express, TypeScript, JWT, Prisma/Mongoose
 * 
 * TEMPLATE NOTICE: This file is copied to backend/src/app.ts during project scaffolding.
 * Module resolution errors shown here will resolve once npm dependencies are installed
 * in the backend folder (see backend/package.json for all required packages).
 * 
 * Utilisation :
 *   npm run dev    # Développement avec hot-reload
 *   npm run build  # Compiler TypeScript
 *   npm run start  # Démarrer le serveur compilé
 */

import express, { Request, Response } from 'express'
import cors from 'cors'
import helmet from 'helmet'
import morgan from 'morgan'
import jwt from 'jsonwebtoken'
import bcrypt from 'bcryptjs'
import 'dotenv/config'

// ⚠️ IMPORTS DYNAMIQUES pour BD (requis pour ESM avec dépendances optionnelles)
let PrismaClient: any = null
let mongoose: any = null

// Lazy-load Prisma si PostgreSQL
const initPrisma = async () => {
    if (!PrismaClient) {
        const prismaModule = await import('@prisma/client')
        PrismaClient = prismaModule.PrismaClient
    }
    return new PrismaClient()
}

// Lazy-load Mongoose si MongoDB
const initMongoose = async () => {
    if (!mongoose) {
        mongoose = await import('mongoose')
        mongoose = mongoose.default || mongoose
    }
    return mongoose
}

// Types étendus pour Express
declare global {
    namespace Express {
        interface Request {
            user?: { id: number; email: string }
        }
    }
}

const app = express()
const PORT = process.env.PORT || 5000

// ============================================================
// ⚙️ MIDDLEWARE
// ============================================================

// Sécurité
app.use(helmet())

// CORS
app.use(cors({
    origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
    credentials: true
}))

// Body parser
app.use(express.json())
app.use(express.urlencoded({ extended: true }))

// Logging
app.use(morgan('combined'))

// ============================================================
// 🗄️ BASE DE DONNÉES - Configuration selon le TYPE
// ============================================================

// Déterminer quel type de BD est utilisé
const DB_TYPE = process.env.DATABASE_TYPE || 'mongodb'

let prisma: any = null
let mongooseConnection: any = null

// Initialiser la BD au démarrage
const initDatabase = async () => {
    try {
        if (DB_TYPE === 'postgres' || DB_TYPE === 'postgresql') {
            // PostgreSQL avec Prisma (via ESM import dynamique)
            prisma = await initPrisma()
            console.log('✅ Client Prisma initialisé (PostgreSQL)')
        } else if (DB_TYPE === 'mongodb') {
            // MongoDB avec Mongoose (via ESM import dynamique)
            const mongooseLib = await initMongoose()
            const mongoURI = process.env.MONGODB_URI || 'mongodb://localhost:27017/mon_projet'
            await mongooseLib.connect(mongoURI)
            mongooseConnection = mongooseLib
            console.log('✅ Connecté à MongoDB')
        }
    } catch (err) {
        console.error('❌ Erreur initialisation BD :', err)
        process.exit(1)
    }
}

// ============================================================
// 🔐 MIDDLEWARE D'AUTHENTIFICATION
// ============================================================

const authMiddleware = (req: Request, res: Response, next: Function) => {
    const token = req.headers.authorization?.split(' ')[1]

    if (!token) {
        return res.status(401).json({ error: 'Token manquant' })
    }

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secret')
        req.user = decoded as any
        next()
    } catch (err) {
        return res.status(401).json({ error: 'Token invalide' })
    }
}

// ============================================================
// 📡 ROUTES
// ============================================================

// Health check
app.get('/health', (req: Request, res: Response) => {
    res.json({
        status: 'OK',
        timestamp: new Date().toISOString(),
        database: DB_TYPE,
        uptime: process.uptime()
    })
})

// Route API publique
app.get('/api/public', (req: Request, res: Response) => {
    res.json({
        message: 'Bienvenue sur l\'API',
        version: '1.0.0',
        database: DB_TYPE
    })
})

// Route protégée par JWT
app.get('/api/protected', authMiddleware, (req: Request, res: Response) => {
    res.json({
        message: 'Route protégée',
        user: req.user
    })
})

// ============================================================
// 👤 ROUTES UTILISATEURS (Exemple avec différentes BD)
// ============================================================

// GET /api/users - Récupérer tous les utilisateurs
app.get('/api/users', async (req: Request, res: Response) => {
    try {
        let users

        if (DB_TYPE === 'postgres' || DB_TYPE === 'postgresql') {
            // Prisma
            users = await prisma.user.findMany({
                select: {
                    id: true,
                    email: true,
                    name: true,
                    createdAt: true
                }
            })
        } else {
            // Mongoose
            const User = mongooseConnection.model('User', new mongooseConnection.Schema({
                email: { type: String, unique: true },
                name: String,
                createdAt: { type: Date, default: Date.now }
            }))
            users = await User.find().select('-password')
        }

        res.json(users)
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' })
    }
})

// POST /api/users - Créer un utilisateur
app.post('/api/users', async (req: Request, res: Response) => {
    try {
        const { email, name, password } = req.body

        if (!email || !password) {
            return res.status(400).json({ error: 'Email et password requis' })
        }

        // Hasher le mot de passe (ESM: bcrypt est importé au top)
        const hashedPassword = await bcrypt.hash(password, 10)

        let newUser

        if (DB_TYPE === 'postgres' || DB_TYPE === 'postgresql') {
            // Prisma
            newUser = await prisma.user.create({
                data: {
                    email,
                    name: name || '',
                    password: hashedPassword
                }
            })
        } else {
            // Mongoose
            // Code exemple (à adapter selon votre schéma)
        }

        res.status(201).json({
            id: newUser.id,
            email: newUser.email,
            name: newUser.name
        })
    } catch (error: any) {
        console.error('Erreur création utilisateur :', error)
        res.status(500).json({ error: error.message || 'Erreur serveur' })
    }
})

// ============================================================
// 🧹 ROUTES ADMIN (Protégées)
// ============================================================

// GET /api/admin/stats - Statistiques
app.get('/api/admin/stats', authMiddleware, async (req: Request, res: Response) => {
    try {
        let userCount

        if (DB_TYPE === 'postgres' || DB_TYPE === 'postgresql') {
            userCount = await prisma.user.count()
        } else {
            // Mongoose - à implémenter
            userCount = 0
        }

        res.json({
            totalUsers: userCount,
            timestamp: new Date().toISOString()
        })
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' })
    }
})

// ============================================================
// ❌ ROUTE 404
// ============================================================

app.use((req: Request, res: Response) => {
    res.status(404).json({
        error: 'Route non trouvée',
        method: req.method,
        path: req.path
    })
})

// ============================================================
// 🚀 DÉMARRAGE DU SERVEUR (avec initialisation BD)
// ============================================================

let server: any = null

const startServer = async () => {
    try {
        // Initialiser la BD avant de démarrer le serveur
        await initDatabase()

        server = app.listen(PORT, () => {
            console.log(`
╔════════════════════════════════════════╗
║  🚀 Backend Express Démarré            ║
║  📍 Port: ${PORT}                      ║
║  🗄️  Base de données: ${DB_TYPE}      ║
║  🌍 URL: http://localhost:${PORT}     ║
╚════════════════════════════════════════╝
    `)
        })
    } catch (err) {
        console.error('❌ Erreur démarrage serveur :', err)
        process.exit(1)
    }
}

// Démarrer le serveur
startServer()

// ============================================================
// 🛑 GESTION PROPRE DE L'ARRÊT
// ============================================================

const gracefulShutdown = async () => {
    console.log('\n🛑 Arrêt en cours...')

    server.close(async () => {
        console.log('✅ Serveur fermé')

        // Fermer les connexions BD
        if (prisma) {
            await prisma.$disconnect()
            console.log('✅ Prisma déconnecté')
        }

        if (mongooseConnection) {
            await mongooseConnection.disconnect()
            console.log('✅ Mongoose déconnecté')
        }

        process.exit(0)
    })
}

process.on('SIGTERM', gracefulShutdown)
process.on('SIGINT', gracefulShutdown)

export default app
