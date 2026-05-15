"""Tests for Agent CMS build system.

Run with: python3 -m pytest tests/ -v
"""
import json
import os
import shutil
import tempfile
import unittest

# Ensure we import from the repo
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys_path_backup = None

import sys
sys_path_backup = sys.path[:]
sys.path.insert(0, SCRIPT_DIR)

import build


class TestMarkdown(unittest.TestCase):
    """Test the markdown-to-HTML conversion."""

    def test_headers(self):
        html = build.parse_markdown("# Heading 1\n## Heading 2\n### Heading 3")
        # markdown library adds id attributes to headers
        self.assertIn("Heading 1</h1>", html)
        self.assertIn("Heading 2</h2>", html)
        self.assertIn("Heading 3</h3>", html)

    def test_bold_italic(self):
        html = build.parse_markdown("**bold** and *italic*")
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)

    def test_links(self):
        html = build.parse_markdown("[link](https://example.com)")
        self.assertIn('<a href="https://example.com">link</a>', html)

    def test_inline_code(self):
        html = build.parse_markdown("`code`")
        self.assertIn("<code>code</code>", html)

    def test_code_block(self):
        html = build.parse_markdown("```python\nprint('hi')\n```")
        self.assertIn("<code", html)
        self.assertIn("print", html)

    def test_list(self):
        html = build.parse_markdown("- item1\n- item2")
        self.assertIn("<li>item1</li>", html)
        self.assertIn("<li>item2</li>", html)

    def test_paragraphs(self):
        html = build.parse_markdown("Hello\n\nWorld")
        self.assertIn("<p>", html)

    def test_table(self):
        """Tables should be rendered via markdown library extension."""
        md = "| H1 | H2 |\n| --- | --- |\n| a | b |"
        html = build.parse_markdown(md)
        self.assertIn("<table", html)
        self.assertIn("<th", html)
        self.assertIn("<td", html)

    def test_task_list(self):
        """Task lists should render as checkboxes."""
        md = "- [x] done\n- [ ] todo"
        html = build.parse_markdown(md)
        # pymdownx.tasklist renders checkboxes with checked attribute
        self.assertIn("checkbox", html.lower())
        self.assertIn("checked", html.lower())

    def test_strikethrough(self):
        """Strikethrough via ~~text~~ should work."""
        md = "~~deleted~~"
        html = build.parse_markdown(md)
        self.assertIn("<del>deleted</del>", html)

    def test_footnote(self):
        """Footnotes should be rendered."""
        md = "Text with a footnote[^1].\n\n[^1]: This is the footnote."
        html = build.parse_markdown(md)
        # Should contain footnote content
        self.assertIn("footnote", html.lower())

    def test_blockquote(self):
        md = "> quoted text"
        html = build.parse_markdown(md)
        self.assertIn("<blockquote>", html)

    def test_horizontal_rule(self):
        md = "---"
        html = build.parse_markdown(md)
        self.assertIn("<hr", html)


class TestParsePost(unittest.TestCase):
    """Test post parsing and frontmatter."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_post(self, content, filename="2026-01-01-test.md"):
        filepath = os.path.join(self.tmpdir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath

    def test_basic_frontmatter(self):
        path = self._write_post("---\ntitle: Test Post\ndate: 2026-01-01\n---\n\nContent here")
        post = build.parse_post(path)
        self.assertEqual(post['title'], 'Test Post')
        self.assertEqual(post['date'], '2026-01-01')

    def test_title_from_heading(self):
        path = self._write_post("# My Title\n\nSome content")
        post = build.parse_post(path)
        self.assertEqual(post['title'], 'My Title')

    def test_date_from_filename(self):
        path = self._write_post("# No Date\n\nContent", "2026-05-15-no-date.md")
        post = build.parse_post(path)
        self.assertEqual(post['date'], '2026-05-15')

    def test_slug_from_filename(self):
        path = self._write_post("---\ntitle: Hello\n---\nContent", "2026-04-13-hello-world.md")
        post = build.parse_post(path)
        self.assertEqual(post['slug'], '2026-04-13-hello-world')

    def test_tags_frontmatter(self):
        path = self._write_post("---\ntitle: Tagged\ntags: [python, ai]\n---\nContent")
        post = build.parse_post(path)
        self.assertIn('tags', post)
        # tags should be a list
        self.assertIsInstance(post['tags'], list)
        self.assertIn('python', post['tags'])
        self.assertIn('ai', post['tags'])

    def test_category_frontmatter(self):
        path = self._write_post("---\ntitle: Categorized\ncategory: tech\n---\nContent")
        post = build.parse_post(path)
        self.assertEqual(post['category'], 'tech')

    def test_draft_frontmatter(self):
        path = self._write_post("---\ntitle: Draft\ndraft: true\n---\nContent")
        post = build.parse_post(path)
        self.assertTrue(post.get('draft'))

    def test_description_frontmatter(self):
        path = self._write_post("---\ntitle: Desc\ndescription: A test post\n---\nContent")
        post = build.parse_post(path)
        self.assertEqual(post['description'], 'A test post')


class TestBuildPost(unittest.TestCase):
    """Test post building."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.content_dir = os.path.join(self.tmpdir, 'content', 'posts')
        # Theme dir must be structured as themes/default/ so THEMES_DIR points to themes/
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.content_dir)
        os.makedirs(self.theme_dir)
        os.makedirs(self.output_dir)

        # Copy theme from actual themes dir
        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        # Write a test post
        post_path = os.path.join(self.content_dir, '2026-01-01-test.md')
        with open(post_path, 'w') as f:
            f.write("---\ntitle: Test Post\ndate: 2026-01-01\n---\n\nHello world")

        # Monkey-patch paths
        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
            'CONTENT_DIR': build.CONTENT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir
        build.CONTENT_DIR = self.content_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        build.CONTENT_DIR = self._originals['CONTENT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_build_creates_html(self):
        post = build.parse_post(os.path.join(self.content_dir, '2026-01-01-test.md'))
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        result = build.build_post(post, config, 'default', [], self.output_dir)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'posts', '2026-01-01-test.html')))

    def test_build_post_returns_info(self):
        post = build.parse_post(os.path.join(self.content_dir, '2026-01-01-test.md'))
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        result = build.build_post(post, config, 'default', [], self.output_dir)
        self.assertIn('title', result)
        self.assertIn('url', result)
        self.assertEqual(result['title'], 'Test Post')


class TestBuildIndex(unittest.TestCase):
    """Test index page generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.theme_dir)

        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_build_index(self):
        posts = [
            {'title': 'Post 1', 'date': '2026-01-01', 'url': '/posts/1.html'},
            {'title': 'Post 2', 'date': '2026-01-02', 'url': '/posts/2.html'},
        ]
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        build.build_index(posts, config, 'default', [], self.output_dir)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'index.html')))

    def test_index_contains_posts(self):
        posts = [
            {'title': 'Post 1', 'date': '2026-01-01', 'url': '/posts/1.html'},
        ]
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        build.build_index(posts, config, 'default', [], self.output_dir)
        with open(os.path.join(self.output_dir, 'index.html')) as f:
            html = f.read()
        # The template uses {{#posts}} loop with {{title}}, {{url}}, {{date}}
        self.assertIn('Post 1', html)


class TestDrafts(unittest.TestCase):
    """Test draft filtering."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.content_dir = os.path.join(self.tmpdir, 'content', 'posts')
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.content_dir)
        os.makedirs(self.theme_dir)

        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
            'CONTENT_DIR': build.CONTENT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir
        build.CONTENT_DIR = self.content_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        build.CONTENT_DIR = self._originals['CONTENT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_drafts_excluded_by_default(self):
        # Write a draft post
        with open(os.path.join(self.content_dir, '2026-01-01-draft.md'), 'w') as f:
            f.write("---\ntitle: Draft Post\ndate: 2026-01-01\ndraft: true\n---\nDraft content")
        # Write a published post
        with open(os.path.join(self.content_dir, '2026-01-02-published.md'), 'w') as f:
            f.write("---\ntitle: Published Post\ndate: 2026-01-02\n---\nPublished content")

        config = {
            'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'},
            'build': {'postsPerPage': 10, 'rss': True, 'sitemap': True},
        }

        posts = build.build_site('test', {
            'site': config['site'],
            'theme': 'default',
            'content_dir': self.content_dir,
            'output_dir': self.output_dir,
        }, config)

        # Draft should be excluded
        post_titles = [p['title'] for p in posts]
        self.assertNotIn('Draft Post', post_titles)
        self.assertIn('Published Post', post_titles)

    def test_drafts_included_with_flag(self):
        with open(os.path.join(self.content_dir, '2026-01-01-draft.md'), 'w') as f:
            f.write("---\ntitle: Draft Post\ndate: 2026-01-01\ndraft: true\n---\nDraft content")

        config = {
            'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'},
            'build': {'postsPerPage': 10, 'rss': True, 'sitemap': True},
        }

        posts = build.build_site('test', {
            'site': config['site'],
            'theme': 'default',
            'content_dir': self.content_dir,
            'output_dir': self.output_dir,
        }, config, include_drafts=True)

        post_titles = [p['title'] for p in posts]
        self.assertIn('Draft Post', post_titles)


class TestSitemap(unittest.TestCase):
    """Test sitemap generation."""

    def test_sitemap_generation(self):
        tmpdir = tempfile.mkdtemp()
        try:
            posts = [
                {'title': 'Post 1', 'date': '2026-01-01', 'url': '/posts/1.html'},
                {'title': 'Post 2', 'date': '2026-01-02', 'url': '/posts/2.html'},
            ]
            config = {
                'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'},
                'build': {'postsPerPage': 10, 'rss': True, 'sitemap': True},
            }
            build.build_sitemap(posts, config, tmpdir)
            sitemap_path = os.path.join(tmpdir, 'sitemap.xml')
            self.assertTrue(os.path.exists(sitemap_path))
            with open(sitemap_path) as f:
                content = f.read()
            self.assertIn('https://example.com', content)
            self.assertIn('/posts/1.html', content)
        finally:
            shutil.rmtree(tmpdir)


class TestPagination(unittest.TestCase):
    """Test pagination of post index."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.theme_dir)

        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_pagination_creates_pages(self):
        posts = [{'title': f'Post {i}', 'date': f'2026-01-{i+1:02d}', 'url': f'/posts/{i}.html'} for i in range(15)]
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        build.build_index(posts, config, 'default', [], self.output_dir, posts_per_page=5)

        # Should have page 1 (index.html), page 2, and page 3
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'index.html')))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'posts', 'page', '2.html')))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'posts', 'page', '3.html')))


class TestCustomPages(unittest.TestCase):
    """Test custom page generation (about, etc)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pages_dir = os.path.join(self.tmpdir, 'content', 'pages')
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.pages_dir)
        os.makedirs(self.theme_dir)

        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_build_custom_page(self):
        # Write an about page
        with open(os.path.join(self.pages_dir, 'about.md'), 'w') as f:
            f.write("---\ntitle: About\ndescription: About this site\n---\n\n# About\n\nThis is the about page.")

        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        result = build.build_custom_pages(config, 'default', [], self.output_dir, self.pages_dir)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'about.html')))


class TestImageHandling(unittest.TestCase):
    """Test image copying from content/images/ to output/images/."""

    def test_copy_images(self):
        tmpdir = tempfile.mkdtemp()
        try:
            # Create source image
            img_src_dir = os.path.join(tmpdir, 'content', 'images')
            os.makedirs(img_src_dir)
            with open(os.path.join(img_src_dir, 'photo.jpg'), 'w') as f:
                f.write('fake image data')

            output_dir = os.path.join(tmpdir, 'output')
            os.makedirs(output_dir)

            build.copy_images(output_dir, img_src_dir)

            self.assertTrue(os.path.exists(os.path.join(output_dir, 'images', 'photo.jpg')))
        finally:
            shutil.rmtree(tmpdir)

    def test_no_images_dir_is_ok(self):
        """Should not fail if images dir doesn't exist."""
        tmpdir = tempfile.mkdtemp()
        try:
            output_dir = os.path.join(tmpdir, 'output')
            os.makedirs(output_dir)
            # No images dir - should not crash
            build.copy_images(output_dir, os.path.join(tmpdir, 'nonexistent'))
            self.assertTrue(os.path.exists(output_dir))
        finally:
            shutil.rmtree(tmpdir)


class TestRSS(unittest.TestCase):
    """Test RSS feed generation with full content."""

    def test_rss_has_description(self):
        tmpdir = tempfile.mkdtemp()
        try:
            posts = [
                {'title': 'Post 1', 'date': '2026-01-01', 'url': '/posts/1.html',
                 'description': 'A test post about things'},
            ]
            config = {
                'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test Author', 'tagline': 'Test blog'},
                'build': {'postsPerPage': 10},
            }
            build.build_rss(posts, config, tmpdir)
            with open(os.path.join(tmpdir, 'rss.xml')) as f:
                content = f.read()
            self.assertIn('A test post about things', content)
            self.assertIn('Test Author', content)
        finally:
            shutil.rmtree(tmpdir)


class TestTagPages(unittest.TestCase):
    """Test tag page generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.theme_base = os.path.join(self.tmpdir, 'themes')
        self.theme_dir = os.path.join(self.theme_base, 'default')
        self.output_dir = os.path.join(self.tmpdir, 'output')
        os.makedirs(self.theme_dir)

        src_theme = os.path.join(SCRIPT_DIR, 'themes', 'default')
        for f in ['post.html', 'index.html', 'style.css']:
            shutil.copy(os.path.join(src_theme, f), os.path.join(self.theme_dir, f))

        self._originals = {
            'THEMES_DIR': build.THEMES_DIR,
            'OUTPUT_DIR': build.OUTPUT_DIR,
        }
        build.THEMES_DIR = self.theme_base
        build.OUTPUT_DIR = self.output_dir

    def tearDown(self):
        build.THEMES_DIR = self._originals['THEMES_DIR']
        build.OUTPUT_DIR = self._originals['OUTPUT_DIR']
        shutil.rmtree(self.tmpdir)

    def test_build_tag_pages(self):
        posts = [
            {'title': 'Post 1', 'date': '2026-01-01', 'url': '/posts/1.html', 'tags': ['python', 'ai']},
            {'title': 'Post 2', 'date': '2026-01-02', 'url': '/posts/2.html', 'tags': ['python']},
        ]
        config = {'site': {'title': 'Test', 'url': 'https://example.com', 'author': 'Test', 'tagline': 'Test'}}
        build.build_tag_pages(posts, config, 'default', [], self.output_dir)

        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'tags', 'python.html')))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'tags', 'ai.html')))


if __name__ == '__main__':
    unittest.main()