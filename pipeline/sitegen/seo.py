"""Sitemaps and metadata audits derived from the pages that were actually built."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

from .config import SITE_URL

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class PageHead(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = []
        self.descriptions = []
        self.canonicals = []
        self.noindex = False
        self.in_title = False
        self.finished = False

    def handle_starttag(self, tag, attrs):
        if self.finished:
            return
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
            self.titles.append("")
        if tag == "meta":
            name = attrs.get("name", "").lower()
            content = attrs.get("content", "")
            if name == "description":
                self.descriptions.append(content)
            if name == "robots":
                self.noindex |= bool({"noindex", "none"} & set(content.lower().replace(",", " ").split()))
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonicals.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "head":
            self.finished = True

    def handle_data(self, data):
        if self.in_title and not self.finished:
            self.titles[-1] += data


def read_head(path):
    head = PageHead()
    with path.open(encoding="utf-8") as source:
        for line in source:
            head.feed(line)
            if head.finished:
                break
    return head


def page_url(site, path):
    relative = path.relative_to(site).as_posix()
    if relative.endswith("index.html"):
        relative = relative[:-len("index.html")]
    return SITE_URL + quote(relative, safe="/-._~")


def page_heads(site):
    return [(path, read_head(path)) for path in sorted(Path(site).rglob("*.html"))]


def write_sitemaps(site):
    """Include canonical HTML pages, including chapters; omit noindex variants.

    Keep the text sitemap for existing webmaster submissions. Do not manufacture
    lastmod dates from build time: an unchanged work is not revised every deploy.
    """
    urls = []
    for path, head in page_heads(site):
        if head.noindex:
            continue
        expected = page_url(site, path)
        if head.canonicals != [expected]:
            raise ValueError(f"{path}: expected one self-referencing canonical URL")
        urls.append(expected)
    ET.register_namespace("", SITEMAP_NS)
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for url in sorted(set(urls)):
        entry = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(entry, f"{{{SITEMAP_NS}}}loc").text = url
    ET.indent(root)
    ET.ElementTree(root).write(site / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (site / "sitemap.txt").write_text("\n".join(sorted(set(urls))) + "\n", encoding="utf-8")


def audit_site(site):
    """Check HTML metadata and exact sitemap coverage; downloads are not HTML."""
    site = Path(site)
    errors, expected, short = [], set(), []
    pages = page_heads(site)
    for path, head in pages:
        relative = path.relative_to(site).as_posix()
        if len(head.titles) != 1 or not head.titles[0].strip():
            errors.append(f"{relative}: expected one nonempty title")
        if len(head.descriptions) != 1 or not head.descriptions[0].strip():
            errors.append(f"{relative}: expected one nonempty meta description")
        if head.canonicals != [page_url(site, path)]:
            errors.append(f"{relative}: expected one self-referencing canonical URL")
        if not head.noindex:
            expected.add(page_url(site, path))
            if head.descriptions and len(head.descriptions[0].strip()) < 100:
                short.append(relative)
    for filename in ("sitemap.txt", "sitemap.xml"):
        try:
            if filename.endswith(".xml"):
                root = ET.parse(site / filename).getroot()
                if root.tag != f"{{{SITEMAP_NS}}}urlset":
                    raise ValueError("not a sitemap urlset")
                urls = [node.text or "" for node in root.findall(f"{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc")]
            else:
                urls = (site / filename).read_text(encoding="utf-8").splitlines()
            if len(urls) != len(set(urls)):
                errors.append(f"{filename}: duplicate URLs")
            errors.extend(f"{filename}: missing {url}" for url in sorted(expected - set(urls)))
            errors.extend(f"{filename}: noncanonical, missing, or noindex page {url}" for url in sorted(set(urls) - expected))
        except (OSError, ValueError, ET.ParseError) as error:
            errors.append(f"{filename}: {error}")
    return errors, {"html_pages": len(pages), "indexable_pages": len(expected), "short_descriptions": short}
