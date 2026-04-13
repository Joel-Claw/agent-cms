# Agent CMS

A static site generator designed for AI agents. Pure HTML/CSS output, zero runtime dependencies.

## Why?

AI agents writing blog posts shouldn't manually copy-paste HTML templates. They should call one function and get consistent, themed output.

## Features

- **Markdown to HTML** - Write content in markdown, get styled HTML
- **Theme enforcement** - One source of truth for styling
- **Auto-index** - Home page and posts listing update automatically
- **Plugin system** - Hooks for custom behavior
- **RSS feed** - Auto-generated
- **Static output** - Deploy anywhere (Pi, shared hosting, S3, Cloudflare Pages)

## Quick Start

```bash
# Create a new post
python3 cms.py --init "My First Post"

# Build everything
python3 cms.py

# Deploy to server
python3 cms.py --deploy

# Push to git
python3 cms.py --git

# All at once
python3 cms.py --deploy --git

# Output is in ./output/ - deploy it anywhere
```

Note: `cms.py` is a wrapper that loads the auth key from `~/.openclaw/vault/secrets.json` automatically. For direct use:

```bash
CMS_AUTH_KEY=your_key python3 build.py --init "Title"
```

## Project Structure

```
agent-cms/
├── config.json         # Site configuration
├── build.py            # Build script
├── content/posts/      # Markdown posts
│   └── 2026-04-13-slug.md
├── themes/default/     # Theme templates
│   ├── post.html
│   ├── index.html
│   └── style.css
├── plugins/            # Optional plugins
│   └── example.py
└── output/             # Generated static files
```

## Post Format

```markdown
---
title: My Post Title
date: 2026-04-13
description: Optional meta description
---

# My Post Title

Content here...
```

## Plugin Hooks

```python
def pre_render(post_data):
    """Modify content before HTML conversion."""
    return post_data

def post_render(html):
    """Modify final HTML output."""
    return html

def on_publish(post_info):
    """Webhook/notification after publish."""
    pass
```

## Agent API

For programmatic use, the build script can be called directly:

```python
from build import build_post, parse_post, load_config

config = load_config()
post = parse_post('content/posts/2026-04-13-my-post.md')
result = build_post(post, config)
# result: {'title': '...', 'url': '/posts/2026-04-13-my-post.html'}
```

## Security

Agent CMS uses authentication to ensure only authorized agents can create/modify content:

### Setup

```bash
# Generate or show the auth key
python3 build.py --show-key
# Output: CMS_AUTH_KEY=abc123...
```

Store this key securely. The agent uses it via environment variable:

```bash
# For authenticated builds
CMS_AUTH_KEY=abc123... python3 build.py

# For creating posts
CMS_AUTH_KEY=abc123... python3 build.py --init "New Post"
```

### Configuration

In `config.json`:
```json
{
  "auth": {
    "key_file": ".cms_auth",
    "require_auth": true
  }
}
```

Set `require_auth` to `false` for development/testing.

### Key File

- Stored in `.cms_auth` (not in git)
- Mode 600 (owner read/write only)
- 32-byte cryptographically secure random token

## Deployment

Output is pure static files. Deploy to:

- Raspberry Pi with nginx
- Shared hosting (just upload)
- GitHub Pages
- Cloudflare Pages
- Netlify
- S3 + CloudFront
- Any web server

### Deploy Command

Configure in `config.json`:
```json
{
  "deploy": {
    "method": "rsync",
    "host": "yourserver.com",
    "user": "youruser",
    "path": "/var/www/blog/",
    "key_file": "/path/to/ssh/key"
  }
}
```

Then deploy:
```bash
# Build and deploy in one command
CMS_AUTH_KEY=... python3 build.py --deploy
```

The `--deploy` flag:
1. Builds all posts
2. Syncs output to remote server via rsync
3. Deletes old files on server
4. Runs `on_publish` plugin hooks

### Git Command

Maintain the repo on GitHub:

```bash
# Build, commit, and push to git
CMS_AUTH_KEY=... python3 build.py --git
```

The `--git` flag:
1. Builds all posts
2. Commits new/modified content with auto-generated message
3. Pushes to remote origin

### Combined workflow

```bash
# Build, deploy, and push to git
CMS_AUTH_KEY=... python3 build.py --deploy --git
```

### Local build on server

If the CMS is installed on the same server as nginx:

```bash
# Build directly to deploy.path (e.g., /var/www/blog)
CMS_AUTH_KEY=... python3 build.py --local
```

The `--local` flag:
1. Builds all posts
2. Writes directly to `deploy.path` instead of local `output_dir`
3. No rsync needed - files are already in place

Use `--local` when:
- CMS is on the same server as nginx
- You want to build directly in `/var/www/<site>`
- No remote deployment needed

## License

MIT