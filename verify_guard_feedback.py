from utils.architecture_guard import ArchitectureGuard

guard = ArchitectureGuard()

print("Testing Backend Violation:")
try:
    guard.validate("backend", ["backend/invalid/file.ts"])
except ValueError as e:
    print(str(e))

print("\nTesting Backend UI Violation:")
try:
    guard.validate("backend", ["backend/src/Component.tsx"])
except ValueError as e:
    print(str(e))

print("\nTesting Frontend Violation:")
try:
    guard.validate("frontend", ["frontend/invalid/file.ts"])
except ValueError as e:
    print(str(e))
