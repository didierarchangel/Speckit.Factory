/**
 * @SPEC-KIT-TASK: Main Express application entrypoint
 * Initializes the backend server with routes and middleware
 */

import express from 'express';
import { authMiddleware } from './middlewares/auth';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());

// Health check route
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Protected routes example
app.get('/api/me', authMiddleware, (req, res) => {
  res.json({ user: req.user });
});

export default app;
