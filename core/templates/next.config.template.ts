/**
 * NextJS Configuration Template
 * 
 * This template will be used when initializing a new project with Next.js
 * as the frontend framework.
 * 
 * Requirement: This file is part of the Golden Templates and should not be
 * manually modified by implementation agents unless fixing a critical build error.
 */

import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  
  // Enable TypeScript strict mode
  typescript: {
    // Set to false only if you understand the warnings
    strict: true,
  },
  
  // Enable ESLint (optional, but recommended)
  eslint: {
    dirs: ['src', 'app', 'pages'],
  },
  
  // Configure image optimization
  images: {
    unoptimized: process.env.NODE_ENV === 'development',
  },

  // Experimental features (if needed)
  // experimental: {
  //   appDir: true, // For App Router
  // },
}

export default nextConfig
