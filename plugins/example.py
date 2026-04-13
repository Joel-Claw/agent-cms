"""
Example plugin for Agent CMS

Plugins can define these hooks:
- pre_render(post_data) - modify content before HTML conversion
- post_render(html) - modify final HTML output
- on_publish(post_info) - webhook/notify after publish
"""


def pre_render(post_data):
    """Add custom processing before markdown conversion."""
    # Example: auto-generate description from first paragraph
    if not post_data.get('description'):
        first_para = post_data['content'].split('\n\n')[0]
        post_data['description'] = first_para[:160] + '...'
    
    return post_data


def post_render(html):
    """Modify final HTML output."""
    # Example: add analytics snippet
    # analytics = '<script src="/analytics.js"></script>'
    # return html.replace('</body>', analytics + '</body>')
    return html


def on_publish(post_info):
    """Called after a post is published."""
    # Example: send webhook notification
    # import requests
    # requests.post('https://example.com/webhook', json=post_info)
    pass