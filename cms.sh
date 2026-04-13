#!/bin/bash
# Agent CMS wrapper script
# Usage: ./cms.sh [--init "Title"] [--deploy] [--git]

export CMS_AUTH_KEY="lrBZiSvwVj2JkY3qbJiGsK_jRqXiY-sB9XxAoc0EUbk"
python3 /home/alex/agent-cms/build.py "$@"