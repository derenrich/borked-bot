import time
import urllib.parse

import pywikibot
import requests
import random
from tqdm import tqdm

from ..util.util import editgroup_string, get_session
from .api import DEFAULT_BASE_URL, classify_batch, nsfw_score

# Wikimedia Commons content descriptor.
CONTENT_DESCRIPTOR = "P14416"
# "Not Safe For Work according to Falconsai/nsfw_image_detection_26".
NSFW_VALUE = "Q140257486"

DEFAULT_THRESHOLD = 0.9
DEFAULT_BATCH_SIZE = 16
DEFAULT_THUMB_WIDTH = 400

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
ENWIKI_REST_MEDIA = "https://en.wikipedia.org/w/rest.php/v1/page/{title}/links/media"
FILE_NAMESPACE = 6

# Common raster image formats the classifier (a vision model) can ingest.
# Deliberately excludes vector (SVG), document (PDF/DjVu), video and audio.
IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "tif", "tiff", "bmp",
}


def random_image_batch(session, batch_size, thumb_width):
    """Fetch a batch of random Commons files, returning ``(title, thumb_url)``.

    Uses the ``generator=random`` query to pick files from the File namespace,
    keeping only common raster image formats and requesting a thumbnail URL of
    the requested width for each.
    """
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "generator": "random",
        "grnnamespace": FILE_NAMESPACE,
        "grnlimit": batch_size,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": thumb_width,
    }
    resp = session.get(COMMONS_API, params=params, timeout=60)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", [])

    out = []
    for page in pages:
        title = page.get("title")
        imageinfo = page.get("imageinfo") or []
        if not title or not imageinfo:
            continue
        info = imageinfo[0]
        mime = info.get("mime", "")
        thumb_url = info.get("thumburl")
        # Require a real raster thumbnail; skip SVG and anything non-image.
        if not thumb_url or not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""
        if ext not in IMAGE_EXTENSIONS:
            continue
        out.append((title, thumb_url))
    return out


def category_members(session, api_url, category, member_namespace):
    """Lazily yield member titles in a category, recursing into subcategories.

    Performs a breadth-first walk: a category's direct members are yielded
    before any subcategory is opened, and a subcategory's contents are fetched
    only when the walk reaches it -- i.e. only if the consumer keeps pulling.
    Subcategory *titles* are discovered cheaply alongside members, but their
    members are not fetched up front. Visited categories are tracked to avoid
    cycles.

    :param member_namespace: namespace number of members to yield (e.g. ``0``
        for articles, ``6`` for files). Subcategories (namespace 14) are always
        requested as well so the walk can recurse.
    """
    if not category.startswith("Category:"):
        category = f"Category:{category}"

    queue = [category]
    visited = {category}
    while queue:
        cat = queue.pop(0)
        cont = {}
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmprop": "title|type",
                "cmnamespace": f"{member_namespace}|14",
                "cmlimit": "500",
                "format": "json",
            }
            params.update(cont)
            resp = session.get(api_url, params=params, timeout=60)
            if resp.status_code == 429:
                time.sleep(30)
                continue
            resp.raise_for_status()
            data = resp.json()
            members = data.get("query", {}).get("categorymembers", [])
            random.shuffle(members)
            for member in members:
                title = member.get("title")
                if not title:
                    continue
                if member.get("type") == "subcat":
                    if title not in visited:
                        visited.add(title)
                        queue.append(title)
                else:
                    yield title
            cont = data.get("continue")
            if not cont:
                break
            time.sleep(2)

def _resolve_thumbs(session, titles, thumb_width):
    """Resolve ``(title, thumb_url)`` for Commons file titles via imageinfo."""
    out = []
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        params = {
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": str(thumb_width),
            "format": "json",
            "formatversion": "2",
        }
        resp = session.get(COMMONS_API, params=params, timeout=60)
        if resp.status_code == 429:
            time.sleep(30)
            continue
        resp.raise_for_status()
        for page in resp.json().get("query", {}).get("pages", []):
            title = page.get("title")
            imageinfo = page.get("imageinfo") or []
            if not title or not imageinfo:
                continue
            thumb_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
            if thumb_url:
                out.append((title, thumb_url))
        time.sleep(1)
    return out


def commons_category_files(session, category, limit, thumb_width):
    """Collect raster image files from a Commons category (recursively).

    Walks the category and its subcategories lazily, keeping common raster
    formats, and resolves a thumbnail URL of ``thumb_width`` for each file.
    Returns up to ``limit`` ``(title, thumb_url)`` pairs.
    """
    titles = []
    for title in category_members(session, COMMONS_API, category, FILE_NAMESPACE):
        ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""
        if ext not in IMAGE_EXTENSIONS:
            continue
        titles.append(title)
        if limit is not None and len(titles) >= limit:
            break
    return _resolve_thumbs(session, titles, thumb_width)


def enwiki_category_articles(session, category):
    """Yield mainspace article titles in an enwiki category, recursing into
    subcategories on demand."""
    return category_members(session, ENWIKI_API, category, 0)


def article_media(session, title):
    """Return Commons-hosted raster ``(file_title, thumb_url)`` used in an article.

    Uses the REST media endpoint. Skips files hosted locally on enwiki (which
    have no Commons structured data) and non-raster media (SVG, video, etc.).
    """
    url = ENWIKI_REST_MEDIA.format(title=urllib.parse.quote(title, safe=""))
    resp = session.get(url, timeout=60)
    if resp.status_code == 429:
        time.sleep(30)
        resp = session.get(url, timeout=60)
    resp.raise_for_status()

    out = []
    files = resp.json().get("files", [])
    random.shuffle(files)  # avoid biasing toward the start of the list
    for f in files:
        desc = f.get("file_description_url") or ""
        # Only Commons-hosted files have MediaInfo we can tag.
        if "commons.wikimedia.org" not in desc:
            continue
        if (f.get("original") or {}).get("mediatype") != "BITMAP":
            continue
        name = f.get("title")
        if not name:
            continue
        # The REST API drops the namespace prefix; restore it for Commons.
        file_title = name if name.startswith("File:") else f"File:{name}"
        thumb_url = (f.get("preferred") or {}).get("url") or (f.get("original") or {}).get("url")
        if not thumb_url:
            continue
        if thumb_url.startswith("//"):
            thumb_url = "https:" + thumb_url
        out.append((file_title, thumb_url))
    return out


def enwiki_category_files(session, category, limit):
    """Collect deduplicated Commons raster files used across articles in a category."""
    files = []
    seen = set()
    for title in enwiki_category_articles(session, category):
        try:
            media = article_media(session, title)
        except requests.exceptions.RequestException as e:
            print(f"failed to fetch media for {title}: {e}")
            continue
        for file_title, thumb_url in media:
            if file_title in seen:
                continue
            seen.add(file_title)
            files.append((file_title, thumb_url))
            if limit is not None and len(files) >= limit:
                return files
    return files


def already_tagged(media):
    """Whether the MediaInfo already carries the NSFW content descriptor."""
    for claim in media.claims.get(CONTENT_DESCRIPTOR, []):
        target = claim.getTarget()
        if target is not None:
            return True
    return False


def tag_file(commons_site, repo, title, nsfw_target, score, eg_string):
    """Add ``P14416 = Q140257486`` to a Commons file's structured data."""
    file_page = pywikibot.FilePage(commons_site, title)
    media = file_page.data_item()
    try:
        # Succeeds (with empty statements) for files that have no structured
        # data yet; only raises if the file itself no longer exists.
        media.get()
    except (pywikibot.exceptions.NoWikibaseEntityError,
            pywikibot.exceptions.NoPageError):
        # File was deleted between sampling and tagging.
        return False

    if already_tagged(media):
        return False

    claim = pywikibot.Claim(repo, CONTENT_DESCRIPTOR)
    claim.setTarget(nsfw_target)
    summary = f"Add NSFW content descriptor (score {score:.3f}) {eg_string}"
    media.addClaim(claim, summary=summary, bot=True)
    return True


def _process_batch(session, commons_site, repo, files, nsfw_target, eg_string,
                   threshold, base_url, dry_run, rows=None):
    """Classify one batch of files and tag the NSFW ones.

    Returns a ``(processed, flagged, tagged)`` tuple of counts. If ``rows`` is
    a list, one ``(title, score, decision)`` record per classified image is
    appended to it for later table output.
    """
    if not files:
        return (0, 0, 0)

    urls = [thumb for (_, thumb) in files]
    try:
        results = classify_batch(session, urls, base_url=base_url)
    except requests.exceptions.RequestException as e:
        print(f"classifier request failed: {e}")
        return (0, 0, 0)

    # Match results back to inputs by URL (the server echoes it as file_path);
    # the response is ordered, but matching is robust to either.
    by_url = {r.get("file_path"): r for r in results if isinstance(r, dict)}

    processed = flagged = tagged = 0
    for (title, thumb), fallback in zip(files, results):
        processed += 1
        result = by_url.get(thumb, fallback)
        score = nsfw_score(result)
        if score is None:
            err = result.get("error") if isinstance(result, dict) else None
            if rows is not None:
                rows.append((title, None, "error"))
            if err:
                print(f"skip {title}: {err}")
            continue

        decision = "NSFW" if score >= threshold else "SAFE"
        if rows is not None:
            rows.append((title, score, decision))
        if score < threshold:
            print(f"SAFE {score:.3f}: {title}")
            continue

        flagged += 1
        print(f"NSFW {score:.3f}: {title}")
        if dry_run:
            print(f"dry run: would tag {title} ({score:.3f})")
            continue
        try:
            if tag_file(commons_site, repo, title, nsfw_target, score, eg_string):
                tagged += 1
        except (pywikibot.exceptions.APIError,
                pywikibot.exceptions.OtherPageSaveError) as e:
            print(f"failed to tag {title}: {e}")

    return (processed, flagged, tagged)


def _process_file_list(session, commons_site, repo, files, nsfw_target, eg_string,
                       threshold, base_url, dry_run, batch_size, sleep, desc, rows=None):
    """Chunk a flat list of files into batches and classify/tag each."""
    processed = flagged = tagged = 0
    chunks = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
    for batch in tqdm(chunks, desc=desc):
        p, f, t = _process_batch(session, commons_site, repo, batch, nsfw_target,
                                 eg_string, threshold, base_url, dry_run, rows=rows)
        processed += p
        flagged += f
        tagged += t
        time.sleep(sleep)
    return (processed, flagged, tagged)


def write_results_table(path, rows):
    """Write a sortable MediaWiki table of classification results.

    Each row shows a thumbnail of the image, a link to the file, the NSFW
    score, and the decision (NSFW / SAFE / error).
    """
    lines = [
        '{| class="wikitable sortable"',
        '|+ NSFW classification results',
        "! Image !! File !! NSFW score !! Decision",
    ]
    for title, score, decision in rows:
        if score is None:
            score_cell = 'data-sort-value="-1" | —'
        else:
            score_cell = f'data-sort-value="{score:.5f}" | {score:.3f}'
        lines.append("|-")
        lines.append(f"| [[{title}|120px]] || [[:{title}]] || {score_cell} || {decision}")
    lines.append("|}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote results table ({len(rows)} rows) to {path}")


def update_nsfw_commons(commons_site, repo, dry_run=False,
                        threshold=DEFAULT_THRESHOLD,
                        batch_size=DEFAULT_BATCH_SIZE,
                        batches=50,
                        thumb_width=DEFAULT_THUMB_WIDTH,
                        base_url=DEFAULT_BASE_URL,
                        sleep=2.0,
                        category=None,
                        enwiki_category=None,
                        limit=200,
                        table=None):
    """Classify Commons images and tag the NSFW ones.

    Source of images (in priority order):

    * ``enwiki_category`` (debugging/testing): articles in this English
      Wikipedia category (and its subcategories) are enumerated, and the
      Commons raster images used in each article are classified.
    * ``category`` (debugging/testing): files pulled directly from this Commons
      category (and its subcategories).
    * otherwise: random files sampled from Commons.

    Files are classified in batches of ``batch_size``; any scoring at or above
    ``threshold`` get the Wikimedia Commons content descriptor (P14416) set to
    "Not Safe For Work according to Falconsai/nsfw_image_detection_26"
    (Q140257486) on their structured data. ``limit`` caps the number of files
    collected in the category modes. If ``table`` is a path, a MediaWiki table
    of all results (image and decision) is written there.
    """
    session = get_session()
    eg_string = editgroup_string()
    nsfw_target = pywikibot.ItemPage(repo, NSFW_VALUE)
    rows = [] if table else None
    processed = 0
    flagged = 0
    tagged = 0

    if enwiki_category:
        files = enwiki_category_files(session, enwiki_category, limit)
        print(f"collected {len(files)} Commons images from enwiki category {enwiki_category}")
        processed, flagged, tagged = _process_file_list(
            session, commons_site, repo, files, nsfw_target, eg_string,
            threshold, base_url, dry_run, batch_size, sleep,
            desc=f"enwiki category {enwiki_category}", rows=rows)
    elif category:
        try:
            files = commons_category_files(session, category, limit, thumb_width)
        except requests.exceptions.RequestException as e:
            print(f"failed to fetch category files: {e}")
            files = []
        processed, flagged, tagged = _process_file_list(
            session, commons_site, repo, files, nsfw_target, eg_string,
            threshold, base_url, dry_run, batch_size, sleep,
            desc=f"category {category}", rows=rows)
    else:
        for _ in tqdm(range(batches), desc="nsfw commons batches"):
            try:
                batch = random_image_batch(session, batch_size, thumb_width)
            except requests.exceptions.RequestException as e:
                print(f"failed to fetch random Commons files: {e}")
                time.sleep(sleep)
                continue
            p, f, t = _process_batch(session, commons_site, repo, batch, nsfw_target,
                                     eg_string, threshold, base_url, dry_run, rows=rows)
            processed += p
            flagged += f
            tagged += t
            time.sleep(sleep)

    print(f"processed {processed} images, {flagged} over threshold, {tagged} newly tagged")

    if table:
        write_results_table(table, rows)
