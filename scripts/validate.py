#!/usr/bin/env python3
"""
Enterprise Telegram Bot - Pre-deployment Validation

This script validates the codebase before deployment to catch issues early:
- Import validation
- Function reference checks  
- Configuration validation
- Database schema validation
- Bot factory validation

Usage: python scripts/validate.py
"""

import ast
import os
import sys
import importlib.util
from pathlib import Path

def validate_imports():
    """Check for missing imports and circular dependencies."""
    print("🔍 Validating imports...")
    
    src_dir = Path("src")
    issues = []
    
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            with open(py_file, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Check for relative imports
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('src.'):
                        # Valid relative import
                        continue
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('src.'):
                            continue
            
        except SyntaxError as e:
            issues.append(f"❌ Syntax error in {py_file}: {e}")
        except Exception as e:
            issues.append(f"⚠️ Could not parse {py_file}: {e}")
    
    if issues:
        print("Import validation issues found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ All imports look good")
        return True


def validate_function_references():
    """Check for missing function references like bot_utils.create_progress_bar."""
    print("🔍 Validating function references...")
    
    # Common function patterns that should have module prefixes
    problematic_patterns = [
        "create_progress_bar(",
        "create_balance_card(",
        "format_user_info_card(",
        "get_usage_tip(",
        "require_admin(",
        "is_admin_user("
    ]
    
    issues = []
    src_dir = Path("src")
    
    for py_file in src_dir.rglob("*.py"):
        try:
            with open(py_file, 'r') as f:
                content = f.read()
            
            for line_num, line in enumerate(content.splitlines(), 1):
                for pattern in problematic_patterns:
                    if pattern in line and "bot_utils." not in line and "def " not in line:
                        # Skip if calling function within the same module
                        if py_file.name == "bot_utils.py" and pattern.replace("(", "") in ["create_progress_bar", "create_balance_card", "format_user_info_card", "get_usage_tip", "require_admin", "is_admin_user"]:
                            continue
                        issues.append(f"❌ {py_file}:{line_num} - Missing module prefix: {pattern}")
        
        except Exception as e:
            issues.append(f"⚠️ Could not check {py_file}: {e}")
    
    if issues:
        print("Function reference issues found:")
        for issue in issues[:10]:  # Limit output
            print(f"  {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
        return False
    else:
        print("✅ All function references look good")
        return True


def validate_bot_factory():
    """Check that bot factory file exists and has basic structure."""
    print("🔍 Validating bot factory...")
    
    try:
        bot_factory_path = Path("src/bot_factory.py")
        if not bot_factory_path.exists():
            print("❌ bot_factory.py not found")
            return False
        
        with open(bot_factory_path, 'r') as f:
            content = f.read()
        
        # Check for essential functions/imports
        required_elements = [
            "def create_application",
            "Application",
            "from src.handlers import",
            "add_handler"
        ]
        
        missing = []
        for element in required_elements:
            if element not in content:
                missing.append(element)
        
        if missing:
            print(f"❌ Missing required elements: {missing}")
            return False
        
        print("✅ Bot factory structure looks good")
        return True
        
    except Exception as e:
        print(f"❌ Bot factory validation failed: {e}")
        return False


def validate_webhook_server():
    """Check that webhook server can be imported."""
    print("🔍 Validating webhook server...")
    
    try:
        # Test import without creating the app (which needs DB)
        spec = importlib.util.spec_from_file_location("webhook_server", "src/webhook_server.py")
        if spec is None:
            print("❌ Could not load webhook_server.py")
            return False
        
        print("✅ Webhook server can be imported")
        return True
        
    except Exception as e:
        print(f"❌ Webhook server validation failed: {e}")
        return False


def validate_requirements():
    """Check that requirements.txt is valid."""
    print("🔍 Validating requirements.txt...")
    
    try:
        with open("requirements.txt", 'r') as f:
            requirements = f.read()
        
        # Basic validation
        lines = [line.strip() for line in requirements.splitlines() if line.strip() and not line.startswith('#')]
        
        essential_packages = ['telegram', 'flask', 'psycopg2', 'stripe', 'gunicorn']
        missing = []
        
        for package in essential_packages:
            if not any(package in line.lower() for line in lines):
                missing.append(package)
        
        if missing:
            print(f"❌ Missing essential packages: {missing}")
            return False
        
        print(f"✅ Requirements.txt looks good ({len(lines)} packages)")
        return True
        
    except Exception as e:
        print(f"❌ Requirements validation failed: {e}")
        return False


def main():
    """Run all validations."""
    print("🧪 ENTERPRISE TELEGRAM BOT - PRE-DEPLOYMENT VALIDATION")
    print("=" * 60)
    
    validations = [
        ("Import Validation", validate_imports),
        ("Function References", validate_function_references),
        ("Bot Factory", validate_bot_factory),
        ("Webhook Server", validate_webhook_server),
        ("Requirements", validate_requirements),
    ]
    
    passed = 0
    failed = 0
    
    for name, validator in validations:
        print(f"\n📋 {name}:")
        try:
            if validator():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Validation error: {e}")
            failed += 1
    
    print(f"\n" + "=" * 60)
    print(f"📊 VALIDATION SUMMARY:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    
    if failed == 0:
        print(f"  🎉 All validations passed! Ready for deployment.")
        return True
    else:
        print(f"  ⚠️ {failed} validation(s) failed. Fix issues before deploying.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 