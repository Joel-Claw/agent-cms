#!/usr/bin/env python3
"""
Agent CMS - Static site generator for AI agents

Builds pure HTML/CSS from markdown posts and themes.
Zero runtime dependencies - output is static files.

Usage:
  python3 build.py                    # Build all posts
  python3 build.py --post slug.md      # Build single post
  python3 build.py --init              # Create new post template
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONTENT_DIR = os.path.join(SCRIPT_DIR, "content/posts")
THEMES_DIR = os.path.join(SCRIPT_DIR, "themes")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
PLUGINS_DIR = os.path.join(SCRIPT_DIR, "plugins")
AUTH_KEY_FILE = os.path.join(SCRIPT_DIR, ".cms_auth")


def generate_auth_key():
    """Generate a new authentication key."""
    import secrets
    key = secrets.token_urlsafe(32)
    with open(AUTH_KEY_FILE, 'w') as f:
        f.write(key)
    os.chmod(AUTH_KEY_FILE, 0o600)  # Owner read/write only
    return key


def load_auth_key():
    """Load existing auth key or generate new one."""
    if os.path.exists(AUTH_KEY_FILE):
        with open(AUTH_KEY_FILE) as f:
            return f.read().strip()
    return generate_auth_key()


def verify_auth(provided_key, config):
    """Verify authentication key."""
    if not config.get('auth', {}).get('require_auth', False):
        return True  # Auth disabled
    
    stored_key = load_auth_key()
    import secrets
    return secrets.compare_digest(provided_key or '', stored_key)




def load_config():
    """Load site configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_plugins(config):
    """Load plugin modules."""
    plugins = []
    if not os.path.exists(PLUGINS_DIR):
        return plugins
    
    for plugin_name in config.get("plugins", []):
        plugin_path = Path(PLUGINS_DIR) / f"{plugin_name}.py"
        if plugin_path.exists():
            # Import plugin module
            import importlib.util
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugins.append(module)
    
    return plugins


def run_plugins(plugins, hook, data):
    """Run plugin hooks on data."""
    for plugin in plugins:
        if hasattr(plugin, hook):
            data = getattr(plugin, hook)(data)
    return data


def parse_markdown(content):
    """Convert markdown to HTML (basic implementation)."""
    # Headers
    content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
    content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
    
    # Bold and italic
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
    
    # Links
    content = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', content)
    
    # Code blocks
    content = re.sub(r'```(\w+)?\n(.+?)```', r'<pre><code>\2</code></pre>', content, flags=re.DOTALL)
    content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
    
    # Lists
    content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
    content = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', content)
    
    # Paragraphs
    paragraphs = content.split('\n\n')
    processed = []
    for p in paragraphs:
        if p.strip() and not p.strip().startswith('<'):
            processed.append(f'<p>{p}</p>')
        else:
            processed.append(p)
    
    return '\n\n'.join(processed)


def estimate_read_time(content):
    """Estimate reading time in minutes."""
    words = len(content.split())
    return max(1, round(words / 200))


def parse_post(filepath):
    """Parse a markdown post file."""
    with open(filepath) as f:
        content = f.read()
    
    # Extract frontmatter
    frontmatter = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()
            content = parts[2]
    
    # Extract title from content if not in frontmatter
    if 'title' not in frontmatter:
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if match:
            frontmatter['title'] = match.group(1)
            content = re.sub(r'^# .+$', '', content, count=1, flags=re.MULTILINE)
    
    # Use filename date if not in frontmatter
    filename = os.path.basename(filepath)
    if 'date' not in frontmatter:
        match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            frontmatter['date'] = match.group(1)
    
    return {
        'title': frontmatter.get('title', 'Untitled'),
        'date': frontmatter.get('date', datetime.now().strftime('%Y-%m-%d')),
        'description': frontmatter.get('description', ''),
        'content': content.strip(),
        'slug': filename.replace('.md', ''),
    }


def render_template(template, context):
    """Simple template rendering with {{var}} and {{#section}}...{{/section}} syntax."""
    result = template
    
    # Handle conditionals {{#var}}...{{/var}}
    for match in re.finditer(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', result, re.DOTALL):
        var_name = match.group(1)
        if var_name in context and context[var_name]:
            result = result.replace(match.group(0), match.group(2))
        else:
            result = result.replace(match.group(0), '')
    
    # Handle loops {{#items}}...{{/items}}
    for match in re.finditer(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', result, re.DOTALL):
        var_name = match.group(1)
        if var_name in context and isinstance(context[var_name], list):
            items_html = ''
            template_bit = match.group(2)
            for item in context[var_name]:
                item_html = template_bit
                for key, value in item.items() if isinstance(item, dict) else []:
                    item_html = item_html.replace('{{' + key + '}}', str(value))
                items_html += item_html
            result = result.replace(match.group(0), items_html)
    
    # Handle simple variables
    for match in re.finditer(r'\{\{(\w+(?:\.\w+)?)\}\}', result):
        var_path = match.group(1).split('.')
        value = context
        for key in var_path:
            if isinstance(value, dict):
                value = value.get(key, '')
            else:
                value = ''
                break
        result = result.replace(match.group(0), str(value))
    
    return result


def build_post(post_data, config, theme, plugins):
    """Build a single post HTML file."""
    # Run pre-render plugins
    post_data = run_plugins(plugins, 'pre_render', post_data)
    
    # Convert markdown to HTML
    html_content = parse_markdown(post_data['content'])
    
    # Calculate read time
    read_time = estimate_read_time(post_data['content'])
    
    # Build context
    context = {
        'site': config['site'],
        'title': post_data['title'],
        'date': post_data['date'],
        'description': post_data.get('description', ''),
        'content': html_content,
        'readTime': read_time,
        'year': datetime.now().year,
    }
    
    # Render template
    with open(os.path.join(THEMES_DIR, theme, 'post.html')) as f:
        template = f.read()
    
    html = render_template(template, context)
    
    # Run post-render plugins
    html = run_plugins(plugins, 'post_render', html)
    
    # Write output
    output_path = os.path.join(OUTPUT_DIR, 'posts', f"{post_data['slug']}.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return {
        'title': post_data['title'],
        'date': post_data['date'],
        'url': f"/posts/{post_data['slug']}.html",
    }


def build_index(posts, config, theme, plugins):
    """Build the index page listing all posts."""
    context = {
        'site': config['site'],
        'posts': posts,
        'year': datetime.now().year,
    }
    
    with open(os.path.join(THEMES_DIR, theme, 'index.html')) as f:
        template = f.read()
    
    html = render_template(template, context)
    html = run_plugins(plugins, 'post_render', html)
    
    # Copy to output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w') as f:
        f.write(html)


def build_rss(posts, config):
    """Build RSS feed."""
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{config['site']['title']}</title>
  <link>{config['site']['url']}</link>
  <description>{config['site']['tagline']}</description>
"""
    for post in posts[:config['build']['postsPerPage']]:
        rss += f"""  <item>
    <title>{post['title']}</title>
    <link>{config['site']['url']}{post['url']}</link>
    <pubDate>{post['date']}</pubDate>
  </item>
"""
    rss += "</channel>\n</rss>"
    
    with open(os.path.join(OUTPUT_DIR, 'rss.xml'), 'w') as f:
        f.write(rss)


def init_post(title):
    """Create a new post template."""
    date = datetime.now().strftime('%Y-%m-%d')
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    filename = f"{date}-{slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)
    
    content = f"""---
title: {title}
date: {date}
description: 
---

# {title}

Write your content here...
"""
    
    os.makedirs(CONTENT_DIR, exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Created: {filepath}")
    return filepath


def show_auth_key():
    """Display or generate auth key for agent use."""
    key = load_auth_key()
    print(f"CMS_AUTH_KEY={key}")
    return key


def main():
    config = load_config()
    plugins = load_plugins(config)
    theme = config.get('theme', 'default')
    require_auth = config.get('auth', {}).get('require_auth', False)
    
    # --show-key: Display auth key (for agent to store)
    if '--show-key' in sys.argv:
        show_auth_key()
        return
    
    # --init requires auth if enabled
    if '--init' in sys.argv:
        if require_auth:
            auth_key = os.environ.get('CMS_AUTH_KEY')
            if not verify_auth(auth_key, config):
                print("ERROR: Authentication required. Set CMS_AUTH_KEY environment variable.")
                sys.exit(1)
        title = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else 'New Post'
        init_post(title)
        return
    
    # Build requires auth if enabled
    if require_auth:
        auth_key = os.environ.get('CMS_AUTH_KEY')
        if not verify_auth(auth_key, config):
            print("ERROR: Authentication required. Set CMS_AUTH_KEY environment variable.")
            sys.exit(1)
    
    # Ensure output directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, 'posts'), exist_ok=True)
    
    # Copy static files from theme
    theme_dir = os.path.join(THEMES_DIR, theme)
    for static_file in ['style.css', 'favicon.ico', 'avatar.jpg']:
        src = os.path.join(theme_dir, static_file)
        if os.path.exists(src):
            import shutil
            shutil.copy(src, os.path.join(OUTPUT_DIR, static_file))
    
    # Find and build all posts
    posts = []
    for filename in sorted(os.listdir(CONTENT_DIR), reverse=True):
        if filename.endswith('.md'):
            filepath = os.path.join(CONTENT_DIR, filename)
            post_data = parse_post(filepath)
            post_info = build_post(post_data, config, theme, plugins)
            posts.append(post_info)
    
    # Build index
    build_index(posts, config, theme, plugins)
    
    # Build RSS
    if config['build'].get('rss'):
        build_rss(posts, config)
    
    print(f"Built {len(posts)} posts to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()