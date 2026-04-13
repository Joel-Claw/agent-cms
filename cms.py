#!/usr/bin/env python3
"""
Agent CMS wrapper - gets auth key from vault and runs build
"""
import os
import sys
import json

# Get auth key from vault
vault_path = '/home/alex/.openclaw/vault/secrets.json'
try:
    with open(vault_path) as f:
        vault = json.load(f)
    auth_key = vault.get('cms_auth_key')
    if not auth_key:
        print("ERROR: cms_auth_key not found in vault")
        sys.exit(1)
    os.environ['CMS_AUTH_KEY'] = auth_key
except FileNotFoundError:
    print("ERROR: Vault not found")
    sys.exit(1)

# Run build.py with all arguments
import subprocess
result = subprocess.run([sys.executable, '/home/alex/agent-cms/build.py'] + sys.argv[1:])
sys.exit(result.returncode)