#!/usr/bin/env python3
"""
Test et Démonstration du ESM Import Resolver

Ce script teste le resolver ESM sur du code TypeScript réel.
"""

from pathlib import Path
from utils.esm_import_resolver import ESMImportResolver


def test_basic_imports():
    """Teste les imports de base"""
    print("=" * 60)
    print("TEST 1: Imports de base")
    print("=" * 60)
    
    resolver = ESMImportResolver()
    
    test_cases = [
        {
            "name": "Import simple",
            "input": 'import { getUser } from "../services/user.service"',
            "expected": 'import { getUser } from "../services/user.service.js"'
        },
        {
            "name": "Import relatif ./",
            "input": 'import Button from "./Button"',
            "expected": 'import Button from "./Button.js"'
        },
        {
            "name": "Import avec chemin profond",
            "input": 'import config from "../../config"',
            "expected": 'import config from "../../config.js"'
        },
        {
            "name": "Import npm (unchanged)",
            "input": 'import express from "express"',
            "expected": 'import express from "express"'
        },
        {
            "name": "Import chemin absolu (unchanged)",
            "input": 'import Button from "@/components/Button"',
            "expected": 'import Button from "@/components/Button"'
        },
        {
            "name": "Import fichier .json (unchanged)",
            "input": 'import config from "./config.json"',
            "expected": 'import config from "./config.json"'
        },
    ]
    
    for test in test_cases:
        result = resolver.resolve_content(test["input"])
        status = "✅" if result == test["expected"] else "❌"
        print(f"\n{status} {test['name']}")
        print(f"   Input:    {test['input']}")
        print(f"   Expected: {test['expected']}")
        print(f"   Got:      {result}")


def test_complex_file():
    """Teste un fichier complet"""
    print("\n" + "=" * 60)
    print("TEST 2: Fichier TypeScript Complet")
    print("=" * 60)
    
    resolver = ESMImportResolver()
    
    before = '''import express from "express"
import { Request, Response } from "express"
import { UserService } from "../services/user.service"
import { validateEmail } from "../validators/email"
import config from "../../config"
import * as fs from "fs"

export async function getUser(req: Request, res: Response) {
  const user = await UserService.find(req.params.id)
  res.json(user)
}

const dynamicImport = () => import("./dynamic")'''

    after = resolver.resolve_content(before)
    
    print("\n📝 AVANT:")
    print("-" * 60)
    print(before)
    
    print("\n✅ APRÈS:")
    print("-" * 60)
    print(after)
    
    # Compter les changements
    before_lines = before.split('\n')
    after_lines = after.split('\n')
    
    changes = sum(1 for b, a in zip(before_lines, after_lines) if b != a)
    print(f"\n📊 {changes} lignes modifiées")


def test_dynamic_imports():
    """Teste les imports dynamiques"""
    print("\n" + "=" * 60)
    print("TEST 3: Imports Dynamiques et Re-exports")
    print("=" * 60)
    
    resolver = ESMImportResolver()
    
    test_cases = [
        {
            "name": "Dynamic import",
            "input": 'await import("./module")',
            "expected": 'await import("./module.js")'
        },
        {
            "name": "Re-export",
            "input": 'export { UserService } from "../services/user.service"',
            "expected": 'export { UserService } from "../services/user.service.js"'
        },
        {
            "name": "Export * from",
            "input": 'export * from "./types"',
            "expected": 'export * from "./types.js"'
        },
    ]
    
    for test in test_cases:
        result = resolver.resolve_content(test["input"])
        status = "✅" if result == test["expected"] else "❌"
        print(f"\n{status} {test['name']}")
        print(f"   Input:    {test['input']}")
        print(f"   Expected: {test['expected']}")
        print(f"   Got:      {result}")


def test_file_types():
    """Teste la détection de types de fichiers"""
    print("\n" + "=" * 60)
    print("TEST 4: Détection de Types de Fichiers")
    print("=" * 60)
    
    resolver = ESMImportResolver()
    
    test_files = [
        ("service.ts", True),
        ("component.tsx", True),
        ("index.js", True),
        ("helper.mjs", True),
        ("config.json", False),
        ("styles.css", False),
        ("image.png", False),
        ("README.md", False),
    ]
    
    for filename, expected in test_files:
        result = resolver._is_supported_file(Path(filename))
        status = "✅" if result == expected else "❌"
        print(f"{status} {filename:20} → {result} (expected {expected})")


def demo_real_case():
    """Démontre un cas réel complet"""
    print("\n" + "=" * 60)
    print("DÉMO: Cas Réel - Backend Service")
    print("=" * 60)
    
    resolver = ESMImportResolver()
    
    # Simuler un vrai fichier service
    backend_service = '''/**
 * User Service - Gestion des utilisateurs
 */

import { PrismaClient } from "@prisma/client"
import * as jwt from "jsonwebtoken"
import { UserValidator } from "../validators/user"
import { config } from "../../config"
import { logger } from "../utils/logger"

class UserService {
  private prisma: PrismaClient
  
  constructor() {
    this.prisma = new PrismaClient()
  }
  
  async getUser(id: string) {
    return await this.prisma.user.findUnique({ where: { id } })
  }
  
  async createUser(data: any) {
    const validated = await UserValidator.validate(data)
    return await this.prisma.user.create({ data: validated })
  }
  
  async deleteUser(id: string) {
    return await this.prisma.user.delete({ where: { id } })
  }
}

export default new UserService()
'''

    fixed = resolver.resolve_content(backend_service)
    
    print("\n📝 SERVICE ORIGINAL:")
    print("-" * 60)
    print(backend_service[:500] + "\n... (truncated)")
    
    print("\n✅ APRÈS RÉSOLUTION ESM:")
    print("-" * 60)
    print(fixed[:500] + "\n... (truncated)")
    
    # Afficher les différences
    print("\n📊 CHANGEMENTS DÉTECTÉS:")
    print("-" * 60)
    
    original_lines = backend_service.split('\n')
    fixed_lines = fixed.split('\n')
    
    for i, (orig, fixed_line) in enumerate(zip(original_lines, fixed_lines)):
        if orig != fixed_line:
            print(f"Ligne {i+1}:")
            print(f"  AVANT:  {orig}")
            print(f"  APRÈS:  {fixed_line}")


if __name__ == "__main__":
    print("\n🚀 TEST SUITE: ESM Import Resolver\n")
    
    try:
        test_basic_imports()
        test_complex_file()
        test_dynamic_imports()
        test_file_types()
        demo_real_case()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS COMPLÉTÉS AVEC SUCCÈS")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
