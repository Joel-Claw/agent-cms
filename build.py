#!/usr/bin/env python3
"""
Agent CMS - Static site generator for AI agents

Builds pure HTML/CSS from markdown posts and themes.
Zero runtime dependencies - output is static files.

Usage:
  python3 build.py                    # Build all posts
  python3 build.py --post slug.md      # Build single post
  python3 build.py --init             # Create new post template
  python3 build.py --drafts           # Include draft posts
  python3 build.py --serve            # Start live preview server
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import markdown

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONTENT_DIR = os.path.join(SCRIPT_DIR, "content/posts")
PAGES_DIR = os.path.join(SCRIPT_DIR, "content/pages")
IMAGES_DIR = os.path.join(SCRIPT_DIR, "content/images")
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
        config = json.load(f)

    # Support both single-site and multi-site configs
    if 'sites' in config:
        config['_multi_site'] = True
    else:
        # Single-site config - normalize to multi-site format internally
        config['_multi_site'] = False
        config['sites'] = {
            'default': {
                'site': config.get('site', {}),
                'theme': config.get('theme', 'default'),
                'content_dir': CONTENT_DIR,
                'output_dir': OUTPUT_DIR,
                'plugins': config.get('plugins', []),
                'deploy': config.get('deploy', {}),
            }
        }
        config['default_site'] = 'default'

    return config


def load_plugins(config):
    """Load plugin modules."""
    plugins = []
    if not os.path.exists(PLUGINS_DIR):
        return plugins

    for plugin_name in config.get("plugins", []):
        plugin_path = Path(PLUGINS_DIR) / f"{plugin_name}.py"
        if plugin_path.exists():
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
    """Convert markdown to HTML using the markdown library with extensions.

    Supports: tables, footnotes, task lists, code highlighting, fenced code,
    strikethrough, superscript, and all standard markdown features.
    """
    extensions = [
        'tables',           # Table syntax
        'footnotes',        # Footnote syntax [^1]
        'md_in_html',       # Markdown inside HTML blocks
        'fenced_code',      # Fenced code blocks
        'codehilite',       # Syntax highlighting (graceful fallback if pygments missing)
        'toc',              # Table of contents
        'smarty',           # Smart quotes/em-dashes
        'sane_lists',       # Better list handling
        'pymdownx.tasklist', # GitHub-style task lists
        'pymdownx.tilde',    # Strikethrough (~~text~~), superscript (^^text^^)
    ]
    extension_configs = {
        'codehilite': {
            'css_class': 'highlight',
            'guess_lang': True,
        },
        'pymdownx.tasklist': {
            'clickable_checkbox': False,
        },
    }

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    return md.convert(content)


def estimate_read_time(content):
    """Estimate reading time in minutes."""
    words = len(content.split())
    return max(1, round(words / 200))


def parse_frontmatter_value(value):
    """Parse a frontmatter value, handling lists like [python, ai] and booleans."""
    value = value.strip()
    # Handle boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    # Handle list like [python, ai]
    if value.startswith('[') and value.endswith(']'):
        items = value[1:-1].split(',')
        return [item.strip().strip('"').strip("'") for item in items if item.strip()]
    # Handle quoted strings
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_post(filepath):
    """Parse a markdown post file with frontmatter.

    Returns dict with: title, date, description, content, slug,
    and optional: tags, category, draft.
    """
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
                    frontmatter[key.strip()] = parse_frontmatter_value(value)
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
        'tags': frontmatter.get('tags', []),
        'category': frontmatter.get('category', ''),
        'draft': frontmatter.get('draft', False),
    }


def render_template(template, context):
    """Simple template rendering with {{var}} and {{#section}}...{{/section}} syntax.

    Supports:
    - {{var}} / {{obj.key}} - simple variable substitution
    - {{#list}}...{{/list}} - loop over list of dicts, with {{key}} inside
    - {{#var}}...{{/var}} - conditional (shows content if var is truthy)
    """
    result = template

    # Handle loops {{#items}}...{{/items}} FIRST (before conditionals)
    # Loops = context[var] is a list; conditionals = context[var] is scalar/truthy
    for match in re.finditer(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', result, re.DOTALL):
        var_name = match.group(1)
        if var_name in context and isinstance(context[var_name], list):
            items_html = ''
            template_bit = match.group(2)
            for item in context[var_name]:
                item_html = template_bit
                if isinstance(item, dict):
                    for key, value in item.items():
                        item_html = item_html.replace('{{' + key + '}}', str(value))
                items_html += item_html
            result = result.replace(match.group(0), items_html)
        elif var_name in context:
            # Not a list - treat as conditional
            if context[var_name]:
                result = result.replace(match.group(0), match.group(2))
            else:
                result = result.replace(match.group(0), '')

    # Handle any remaining conditionals {{#var}}...{{/var}}
    for match in re.finditer(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', result, re.DOTALL):
        var_name = match.group(1)
        if var_name in context and context[var_name]:
            result = result.replace(match.group(0), match.group(2))
        else:
            result = result.replace(match.group(0), '')

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


def build_post(post_data, config, theme, plugins, output_dir=None):
    """Build a single post HTML file."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

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
        'tags': post_data.get('tags', []),
        'category': post_data.get('category', ''),
    }

    # Render template
    with open(os.path.join(THEMES_DIR, theme, 'post.html')) as f:
        template = f.read()

    html = render_template(template, context)

    # Run post-render plugins
    html = run_plugins(plugins, 'post_render', html)

    # Write output
    out_path = os.path.join(output_dir, 'posts', f"{post_data['slug']}.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(html)

    return {
        'title': post_data['title'],
        'date': post_data['date'],
        'url': f"/posts/{post_data['slug']}.html",
        'description': post_data.get('description', ''),
        'tags': post_data.get('tags', []),
        'category': post_data.get('category', ''),
    }


def build_index(posts, config, theme, plugins, output_dir=None, posts_per_page=None):
    """Build the index page listing all posts, with optional pagination."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    # Determine posts per page
    if posts_per_page is None:
        posts_per_page = config.get('build', {}).get('postsPerPage', 10)

    if posts_per_page and len(posts) > posts_per_page:
        # Paginate
        total_pages = (len(posts) + posts_per_page - 1) // posts_per_page

        for page_num in range(1, total_pages + 1):
            start = (page_num - 1) * posts_per_page
            end = start + posts_per_page
            page_posts = posts[start:end]

            # Determine output path and ensure directory exists
            if page_num == 1:
                os.makedirs(output_dir, exist_ok=True)
                page_path = os.path.join(output_dir, 'index.html')
                canonical_url = '/'
            else:
                page_dir = os.path.join(output_dir, 'posts', 'page')
                os.makedirs(page_dir, exist_ok=True)
                page_path = os.path.join(page_dir, f'{page_num}.html')
                canonical_url = f'/posts/page/{page_num}.html'

            context = {
                'site': config['site'],
                'posts': page_posts,
                'year': datetime.now().year,
                'currentPage': page_num,
                'totalPages': total_pages,
                'hasPrev': page_num > 1,
                'hasNext': page_num < total_pages,
                'prevPage': '/posts/page/{}.html'.format(page_num - 1) if page_num > 2 else '/' if page_num > 1 else '',
                'nextPage': '/posts/page/{}.html'.format(page_num + 1) if page_num < total_pages else '',
            }

            with open(os.path.join(THEMES_DIR, theme, 'index.html')) as f:
                template = f.read()

            html = render_template(template, context)
            html = run_plugins(plugins, 'post_render', html)

            with open(page_path, 'w') as f:
                f.write(html)
    else:
        # No pagination, single index page
        context = {
            'site': config['site'],
            'posts': posts,
            'year': datetime.now().year,
        }

        with open(os.path.join(THEMES_DIR, theme, 'index.html')) as f:
            template = f.read()

        html = render_template(template, context)
        html = run_plugins(plugins, 'post_render', html)

        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, 'index.html'), 'w') as f:
            f.write(html)


def build_rss(posts, config, output_dir=None):
    """Build RSS feed with full content and proper dates."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    site = config['site']
    build_config = config.get('build', {})
    posts_per_page = build_config.get('postsPerPage', 10)

    # RFC 822 formatted date
    now_rfc822 = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z') or datetime.utcnow().strftime('%a, %d %b %Y 00:00:00 +0000')

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{xml_escape(site.get('title', 'Blog'))}</title>
  <link>{xml_escape(site.get('url', ''))}</link>
  <description>{xml_escape(site.get('tagline', ''))}</description>
  <language>en</language>
  <lastBuildDate>{now_rfc822}</lastBuildDate>
  <atom:link href="{xml_escape(site.get('url', ''))}/rss.xml" rel="self" type="application/rss+xml"/>
"""

    for post in posts[:posts_per_page]:
        post_url = f"{site.get('url', '')}{post['url']}"
        description = xml_escape(post.get('description', ''))
        # Format date as RFC 822
        try:
            dt = datetime.strptime(post['date'], '%Y-%m-%d')
            pub_date = dt.strftime('%a, %d %b %Y 00:00:00 +0000')
        except (ValueError, KeyError):
            pub_date = now_rfc822

        rss += f"""  <item>
    <title>{xml_escape(post['title'])}</title>
    <link>{xml_escape(post_url)}</link>
    <description>{description}</description>
    <pubDate>{pub_date}</pubDate>
    <guid>{xml_escape(post_url)}</guid>
    <author>{xml_escape(site.get('author', ''))}</author>
  </item>
"""

    rss += "</channel>\n</rss>"

    with open(os.path.join(output_dir, 'rss.xml'), 'w') as f:
        f.write(rss)


def build_sitemap(posts, config, output_dir=None):
    """Build sitemap.xml for search engines."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    site_url = config['site'].get('url', '').rstrip('/')
    today = datetime.now().strftime('%Y-%m-%d')

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # Homepage
    lines.append(f"""  <url>
    <loc>{xml_escape(site_url)}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>""")

    # Posts
    for post in posts:
        post_url = f"{site_url}{post['url']}"
        try:
            dt = datetime.strptime(post['date'], '%Y-%m-%d')
            lastmod = dt.strftime('%Y-%m-%d')
        except (ValueError, KeyError):
            lastmod = today

        lines.append(f"""  <url>
    <loc>{xml_escape(post_url)}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>""")

    # Tags pages
    all_tags = set()
    for post in posts:
        for tag in post.get('tags', []):
            all_tags.add(tag)
    for tag in sorted(all_tags):
        tag_url = f"{site_url}/tags/{xml_escape(tag)}.html"
        lines.append(f"""  <url>
    <loc>{tag_url}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>""")

    # About page (if it exists in pages dir)
    pages_dir = os.path.join(SCRIPT_DIR, 'content', 'pages')
    if os.path.exists(pages_dir):
        for page_file in os.listdir(pages_dir):
            if page_file.endswith('.md'):
                page_slug = page_file.replace('.md', '')
                page_url = f"{site_url}/{xml_escape(page_slug)}.html"
                lines.append(f"""  <url>
    <loc>{page_url}</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

    lines.append('</urlset>')

    with open(os.path.join(output_dir, 'sitemap.xml'), 'w') as f:
        f.write('\n'.join(lines))


def build_tag_pages(posts, config, theme, plugins, output_dir=None):
    """Build tag index pages at /tags/<tag>.html."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    # Collect all tags
    tag_posts = {}
    for post in posts:
        for tag in post.get('tags', []):
            tag = tag.lower().strip()
            if tag not in tag_posts:
                tag_posts[tag] = []
            tag_posts[tag].append(post)

    # Generate a page for each tag
    for tag, tag_post_list in tag_posts.items():
        context = {
            'site': config['site'],
            'title': f'Posts tagged "{tag}"',
            'posts': tag_post_list,
            'year': datetime.now().year,
            'tagName': tag,
        }

        with open(os.path.join(THEMES_DIR, theme, 'index.html')) as f:
            template = f.read()

        html = render_template(template, context)
        html = run_plugins(plugins, 'post_render', html)

        tag_dir = os.path.join(output_dir, 'tags')
        os.makedirs(tag_dir, exist_ok=True)
        with open(os.path.join(tag_dir, f'{tag}.html'), 'w') as f:
            f.write(html)


def build_custom_pages(config, theme, plugins, output_dir=None, pages_dir=None):
    """Build custom pages from content/pages/ directory."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if pages_dir is None:
        pages_dir = PAGES_DIR

    if not os.path.exists(pages_dir):
        return []

    results = []
    for filename in sorted(os.listdir(pages_dir)):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(pages_dir, filename)
        with open(filepath) as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = {}
        page_content = content
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        frontmatter[key.strip()] = parse_frontmatter_value(value)
                page_content = parts[2]

        # Extract title
        title = frontmatter.get('title', '')
        if not title:
            match = re.search(r'^# (.+)$', page_content, re.MULTILINE)
            if match:
                title = match.group(1)
                page_content = re.sub(r'^# .+$', '', page_content, count=1, flags=re.MULTILINE)
            else:
                title = filename.replace('.md', '').replace('-', ' ').title()

        description = frontmatter.get('description', '')

        # Convert markdown to HTML
        html_content = parse_markdown(page_content.strip())

        # Build context and render
        context = {
            'site': config['site'],
            'title': title,
            'description': description,
            'content': html_content,
            'year': datetime.now().year,
        }

        with open(os.path.join(THEMES_DIR, theme, 'post.html')) as f:
            template = f.read()

        html = render_template(template, context)
        html = run_plugins(plugins, 'post_render', html)

        # Write to output/<slug>.html
        slug = filename.replace('.md', '')
        out_path = os.path.join(output_dir, f'{slug}.html')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w') as f:
            f.write(html)

        results.append({
            'title': title,
            'url': f'/{slug}.html',
            'description': description,
        })

    return results


def copy_images(output_dir=None, images_dir=None):
    """Copy images from content/images/ to output/images/."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if images_dir is None:
        images_dir = IMAGES_DIR

    if not os.path.exists(images_dir):
        return

    dest = os.path.join(output_dir, 'images')
    if os.path.exists(dest):
        shutil.rmtree(dest)

    shutil.copytree(images_dir, dest)


def init_post(title, content_dir=None):
    """Create a new post template."""
    if content_dir is None:
        content_dir = CONTENT_DIR

    date = datetime.now().strftime('%Y-%m-%d')
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    filename = f"{date}-{slug}.md"
    filepath = os.path.join(content_dir, filename)

    content = f"""---
title: {title}
date: {date}
description:
tags: []
category:
---

# {title}

Write your content here...
"""

    os.makedirs(content_dir, exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Created: {filepath}")
    return filepath


def show_auth_key():
    """Display or generate auth key for agent use."""
    key = load_auth_key()
    print(f"CMS_AUTH_KEY={key}")
    return key


def deploy(site_config, config):
    """Deploy output to remote server via rsync."""
    deploy_config = site_config.get('deploy', {})

    if not deploy_config.get('host') or not deploy_config.get('path'):
        print("ERROR: Deploy not configured. Set host and path in config.json")
        sys.exit(1)

    host = deploy_config['host']
    user = deploy_config.get('user', '')
    remote_path = deploy_config['path']
    key_file = deploy_config.get('key_file', '')
    output_dir = site_config.get('output_dir', OUTPUT_DIR)

    # Build rsync command
    rsync_cmd = ['rsync', '-avz', '--delete']

    if key_file:
        rsync_cmd.extend(['-e', f'ssh -i {key_file}'])

    # Source and destination
    src = output_dir + '/'  # Trailing slash = copy contents, not the dir itself
    if user:
        dest = f'{user}@{host}:{remote_path}'
    else:
        dest = f'{host}:{remote_path}'

    rsync_cmd.extend([src, dest])

    print(f"Deploying to {dest}...")
    result = os.system(' '.join(rsync_cmd))

    if result == 0:
        print("Deploy successful!")
        # Run on_publish plugins
        plugins = load_plugins({'plugins': site_config.get('plugins', [])})
        run_plugins(plugins, 'on_publish', {'status': 'success', 'url': site_config['site']['url']})
    else:
        print(f"Deploy failed with code {result}")
        sys.exit(1)


def git_push(commit_msg=None):
    """Commit and push changes to git repo."""
    # Change to script directory for git operations
    os.chdir(SCRIPT_DIR)

    if not os.path.exists('.git'):
        print("ERROR: Not a git repository")
        sys.exit(1)

    # Check for changes
    result = os.system('git diff --quiet --exit-code')
    if result == 0:
        print("No changes to commit")
        return

    # Add all changes
    os.system('git add -A')

    # Commit
    if not commit_msg:
        # Generate commit message from new/modified posts
        status_output = os.popen('git status --porcelain').read()

        new_posts = [l.split()[1] for l in status_output.split('\n') if 'content/posts/' in l and l.startswith('A')]
        mod_posts = [l.split()[1] for l in status_output.split('\n') if 'content/posts/' in l and l.startswith('M')]

        parts = []
        if new_posts:
            parts.append(f"Add {len(new_posts)} new post(s)")
        if mod_posts:
            parts.append(f"Update {len(mod_posts)} post(s)")

        commit_msg = ' | '.join(parts) if parts else 'Update content'

    commit_cmd = f'git commit -m "{commit_msg}"'
    os.system(commit_cmd)

    # Push
    result = os.system('git push')
    if result != 0:
        print("ERROR: Git push failed")
        sys.exit(1)

    print(f"Committed and pushed: {commit_msg}")


def serve(output_dir=None, port=8000):
    """Start a local HTTP server for live preview."""
    import http.server
    import socketserver

    if output_dir is None:
        output_dir = OUTPUT_DIR

    if not os.path.exists(output_dir):
        print(f"ERROR: Output directory {output_dir} not found. Run build first.")
        sys.exit(1)

    os.chdir(output_dir)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving on http://localhost:{port}/")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


def build_site(site_name, site_config, config, local=False, include_drafts=False):
    """Build a single site."""
    # Get site-specific paths
    content_dir = site_config.get('content_dir', os.path.join(SCRIPT_DIR, 'content', site_name))

    # Output directory: use deploy.path if --local, otherwise local output_dir
    if local and site_config.get('deploy', {}).get('path'):
        output_dir = site_config['deploy']['path']
    else:
        output_dir = site_config.get('output_dir', os.path.join(SCRIPT_DIR, 'output', site_name))

    theme = site_config.get('theme', 'default')

    # Load site-specific plugins
    site_plugins = site_config.get('plugins', [])
    plugins = load_plugins({'plugins': site_plugins}) if site_plugins else []

    # Ensure output directories exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'posts'), exist_ok=True)

    # Copy static files from theme
    theme_dir = os.path.join(THEMES_DIR, theme)
    for static_file in ['style.css', 'favicon.ico', 'avatar.jpg']:
        src = os.path.join(theme_dir, static_file)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(output_dir, static_file))

    # Copy images
    img_src = os.path.join(os.path.dirname(content_dir), 'images') if not os.path.isabs(content_dir) else IMAGES_DIR
    copy_images(output_dir, img_src)

    # Find and build all posts
    posts = []
    content_path = content_dir
    if not os.path.isabs(content_dir):
        content_path = os.path.join(SCRIPT_DIR, content_dir)

    if os.path.exists(content_path):
        for filename in sorted(os.listdir(content_path), reverse=True):
            if filename.endswith('.md'):
                filepath = os.path.join(content_path, filename)
                post_data = parse_post(filepath)

                # Skip drafts unless --drafts flag
                if post_data.get('draft') and not include_drafts:
                    continue

                post_info = build_post(post_data, {'site': site_config['site'], 'build': config.get('build', {})}, theme, plugins, output_dir)
                posts.append(post_info)

    # Build index (with pagination)
    posts_per_page = config.get('build', {}).get('postsPerPage', 10)
    build_index(posts, {'site': site_config['site'], 'build': config.get('build', {})}, theme, plugins, output_dir, posts_per_page=posts_per_page)

    # Build tag pages
    build_tag_pages(posts, {'site': site_config['site']}, theme, plugins, output_dir)

    # Build custom pages
    pages_dir = os.path.join(os.path.dirname(content_path), 'pages') if not os.path.isabs(content_dir) else PAGES_DIR
    build_custom_pages({'site': site_config['site']}, theme, plugins, output_dir, pages_dir)

    # Build RSS
    if config.get('build', {}).get('rss'):
        build_rss(posts, {'site': site_config['site'], 'build': config.get('build', {})}, output_dir)

    # Build sitemap
    if config.get('build', {}).get('sitemap'):
        build_sitemap(posts, {'site': site_config['site']}, output_dir)

    print(f"Built {len(posts)} posts to {output_dir}/")

    return posts


def main():
    config = load_config()
    require_auth = config.get('auth', {}).get('require_auth', False)

    # --show-key: Display auth key (for agent to store)
    if '--show-key' in sys.argv:
        show_auth_key()
        return

    # Check for --local flag (build directly to deploy path)
    local_build = '--local' in sys.argv

    # Check for --drafts flag (include draft posts)
    include_drafts = '--drafts' in sys.argv

    # Parse --site argument for multi-site configs
    site_arg = None
    if '--site' in sys.argv:
        idx = sys.argv.index('--site')
        if idx + 1 < len(sys.argv):
            site_arg = sys.argv[idx + 1]

    # Determine which site(s) to build
    if config['_multi_site']:
        if site_arg:
            if site_arg not in config['sites']:
                print(f"ERROR: Site '{site_arg}' not found in config")
                print(f"Available sites: {', '.join(config['sites'].keys())}")
                sys.exit(1)
            sites_to_build = [site_arg]
        else:
            # Build default site or all sites
            default = config.get('default_site')
            if default and default in config['sites']:
                sites_to_build = [default]
            else:
                sites_to_build = list(config['sites'].keys())
    else:
        sites_to_build = ['default']

    # Auth check for write operations
    if '--init' in sys.argv or '--deploy' in sys.argv or '--git' in sys.argv:
        if require_auth:
            auth_key = os.environ.get('CMS_AUTH_KEY')
            if not verify_auth(auth_key, config):
                print("ERROR: Authentication required. Set CMS_AUTH_KEY environment variable.")
                sys.exit(1)

    # --init: Create new post
    if '--init' in sys.argv:
        title = ' '.join([a for a in sys.argv[2:] if not a.startswith('--')])
        if not title:
            title = 'New Post'
        site_name = sites_to_build[0]
        site_config = config['sites'][site_name]
        content_dir = site_config.get('content_dir', os.path.join(SCRIPT_DIR, 'content', site_name))
        if not os.path.isabs(content_dir):
            content_dir = os.path.join(SCRIPT_DIR, content_dir)
        init_post(title, content_dir)
        return

    # --serve: Start live preview server
    if '--serve' in sys.argv:
        # Build first, then serve
        for site_name in sites_to_build:
            site_config = config['sites'][site_name]
            build_site(site_name, site_config, config, local=local_build, include_drafts=include_drafts)

        site_name = sites_to_build[0]
        site_config = config['sites'][site_name]
        output_dir = site_config.get('output_dir', os.path.join(SCRIPT_DIR, 'output', site_name))
        if local_build and site_config.get('deploy', {}).get('path'):
            output_dir = site_config['deploy']['path']

        # Parse port
        port = 8000
        if '--port' in sys.argv:
            idx = sys.argv.index('--port')
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])

        serve(output_dir, port)
        return

    # Build site(s)
    all_posts = {}
    for site_name in sites_to_build:
        site_config = config['sites'][site_name]
        all_posts[site_name] = build_site(site_name, site_config, config, local=local_build, include_drafts=include_drafts)

    # Deploy if --deploy flag (only if not --local, since --local already deploys)
    if '--deploy' in sys.argv and not local_build:
        for site_name in sites_to_build:
            site_config = config['sites'][site_name]
            if site_config.get('deploy', {}).get('method') == 'rsync':
                deploy(site_config, config)

    # Git commit and push if --git flag
    if '--git' in sys.argv:
        git_push()


if __name__ == '__main__':
    main()