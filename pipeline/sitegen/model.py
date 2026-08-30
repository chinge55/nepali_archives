"""Loaded archive catalogue and shared browse-page helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from devanagari_slug import slugify

from .config import AUTHORS, GENRE, GENRE_ORDER
from .context import BuildContext
from .text import devnum, esc


WorkRecord = tuple[dict, dict, str]


@dataclass
class Catalogue:
    records: list[WorkRecord]
    extras: dict[str, dict[str, object]]
    by_author: dict[str, list[WorkRecord]]
    author_order: list[str]
    collections: dict[str, list[tuple[dict, dict]]]
    collection_slugs: dict[str, str]
    by_genre: dict[str, list[tuple[dict, dict]]]
    genres_present: list[str]

    @staticmethod
    def author_slug(work: dict) -> str:
        return Path(work["path"]).relative_to("archives").parts[1]

    @staticmethod
    def author_info(slug: str, sample_meta: dict) -> tuple[str, str, str]:
        if slug in AUTHORS:
            return AUTHORS[slug]
        author = sample_meta["author"]
        return (author["name"], author.get("name_roman") or "", "")

    def work_list_item(
        self, work: dict, meta: dict, href: str, *, chip: bool = False
    ) -> str:
        extra = self.extras[work["path"]]
        genre = meta["genre"][0] if meta["genre"] else ""
        reading_time = (
            "छोटो"
            if extra["min"] == 0
            else f"~{devnum(extra['min'])} मिनेट"
        )
        metadata = (
            (
                f'<span class="chip g-{genre}">'
                f'{esc(GENRE.get(genre, (genre, ""))[0])}</span>'
                if chip and genre
                else ""
            )
            + f'<span class="rt">{reading_time}</span>'
            + (
                '<span class="scan" title="मूल पृष्ठ स्क्यान उपलब्ध">📖</span>'
                if extra["pdf"]
                else ""
            )
        )
        return (
            f'<li><a class="row-link" href="{href}">'
            f'<span class="wmeta">{metadata}</span>{esc(meta["title"])}'
            f'<span class="r">{esc(meta.get("title_roman") or "")}</span></a></li>'
        )

    def genre_cards(self, base: str) -> str:
        cards = "".join(
            f'<a class="card g-{genre}" href="{base}genres/{genre}/">'
            f'<b>{esc(GENRE.get(genre, (genre, ""))[0])}</b>'
            f'<span class="en">{esc(GENRE.get(genre, (genre, ""))[1])}</span>'
            f'<span class="n">{devnum(len(self.by_genre[genre]))} कृति</span></a>'
            for genre in self.genres_present
        )
        return f'<div class="shelf">{cards}</div>'


def load_catalogue(context: BuildContext) -> Catalogue:
    works = json.loads(
        (context.archives / "index.json").read_text(encoding="utf-8")
    )["works"]
    records: list[WorkRecord] = []
    extras: dict[str, dict[str, object]] = {}
    for work in works:
        work_dir = context.root / work["path"]
        meta = json.loads(
            (work_dir / "metadata.json").read_text(encoding="utf-8")
        )
        text = (work_dir / "text.txt").read_text(encoding="utf-8")
        records.append((work, meta, text))
        extras[work["path"]] = {
            "min": round(len(text.split()) / 200),
            "pdf": bool(meta.get("formats", {}).get("pdf")),
        }

    by_author: dict[str, list[WorkRecord]] = {}
    for record in records:
        by_author.setdefault(Catalogue.author_slug(record[0]), []).append(record)

    def genre_key(meta: dict) -> tuple[int, str]:
        genre = meta["genre"][0] if meta["genre"] else "kavita"
        order = (
            GENRE_ORDER.index(genre)
            if genre in GENRE_ORDER
            else len(GENRE_ORDER)
        )
        return (order, meta["title"])

    for author in by_author:
        by_author[author].sort(key=lambda record: genre_key(record[1]))
    author_order = sorted(by_author, key=lambda author: -len(by_author[author]))

    collections: dict[str, list[tuple[dict, dict]]] = {}
    for work, meta, _ in records:
        for collection in work.get("collection") or []:
            collections.setdefault(collection, []).append((work, meta))
    collection_slugs = {
        collection: slugify(collection) for collection in collections
    }
    for collection in collections:
        collections[collection].sort(key=lambda item: item[1]["title"])

    by_genre: dict[str, list[tuple[dict, dict]]] = {}
    for work, meta, _ in records:
        genre = meta["genre"][0] if meta["genre"] else "kavita"
        by_genre.setdefault(genre, []).append((work, meta))
    genres_present = [
        genre
        for genre in GENRE_ORDER
        + sorted(
            key for key in by_genre if key not in GENRE_ORDER
        )
        if by_genre.get(genre)
    ]
    return Catalogue(
        records=records,
        extras=extras,
        by_author=by_author,
        author_order=author_order,
        collections=collections,
        collection_slugs=collection_slugs,
        by_genre=by_genre,
        genres_present=genres_present,
    )
