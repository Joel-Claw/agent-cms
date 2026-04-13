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
python3 build.py --init "My First Post"

# Build everything
python3 build.py

# Output is in ./output/ - deploy it anywhere
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

## Deployment

Output is pure static files. Deploy to:

- Raspberry Pi with nginx
- Shared hosting (just upload)
- GitHub Pages
- Cloudflare Pages
- Netlify
- S3 + CloudFront
- Any web server

## License

MIT