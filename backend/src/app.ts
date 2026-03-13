// @SPEC-KIT-TASK: 19_tests_backend
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';

dotenv.config();

const app = express();

// Middlewares (Rule 12.2)
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());
app.use(helmet());
app.use(morgan('dev'));

// Debugging middleware (Rule 12.2)
app.use((req, res, next) => {
  console.log(`[DEBUG] ${req.method} ${req.url}`);
  console.log(`[DEBUG] Content-Type: ${req.headers['content-type']}`);
  if (req.method === 'POST' || req.method === 'PUT' || req.method === 'PATCH') {
    if (Object.keys(req.body).length === 0) {
      console.warn('[DEBUG] Request body is empty. Check Content-Type header or if body parser is correctly configured.');
    } else {
      console.log('[DEBUG] Request body:', req.body);
    }
  }
  next();
});

// A simple test route for integration tests
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'UP', message: 'Backend is healthy!' });
});

export default app;