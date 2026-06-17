import time

import pywikibot
import requests
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


def category_image_batch(session, category, limit, thumb_width):
    """Fetch files from a Commons category, returning ``(title, thumb_url)``.

    For debugging/testing: pulls up to ``limit`` files from a known category
    rather than random sampling. Mirrors the classifier server's category
    fetch (``generator=categorymembers`` with ``iiprop=url``), keeping only
    common raster image formats.
    """
    # Standardize category name structure
    if not category.startswith("Category:"):
        category = f"Category:{category}"

    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": category,
        "gcmtype": "file",
        "gcmlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": str(thumb_width),
        "format": "json",
        "formatversion": "2",
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
        thumb_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
        if not thumb_url:
            continue
        ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""
        if ext not in IMAGE_EXTENSIONS:
            continue
        out.append((title, thumb_url))
    return out


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
                   threshold, base_url, dry_run):
    """Classify one batch of files and tag the NSFW ones.

    Returns a ``(processed, flagged, tagged)`` tuple of counts.
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
            if err:
                print(f"skip {title}: {err}")
            continue
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


def update_nsfw_commons(commons_site, repo, dry_run=False,
                        threshold=DEFAULT_THRESHOLD,
                        batch_size=DEFAULT_BATCH_SIZE,
                        batches=50,
                        thumb_width=DEFAULT_THUMB_WIDTH,
                        base_url=DEFAULT_BASE_URL,
                        sleep=2.0,
                        category=None,
                        limit=200):
    """Classify Commons images and tag the NSFW ones.

    By default samples random files from Commons. If ``category`` is given
    (debugging/testing), images are pulled from that category instead, up to
    ``limit`` files. Either way, files are classified in batches of
    ``batch_size`` and any scoring at or above ``threshold`` get the Wikimedia
    Commons content descriptor (P14416) set to "Not Safe For Work according to
    Falconsai/nsfw_image_detection_26" (Q140257486) on their structured data.
    """
    session = get_session()
    eg_string = editgroup_string()
    nsfw_target = pywikibot.ItemPage(repo, NSFW_VALUE)
    processed = 0
    flagged = 0
    tagged = 0

    if category:
        print(f"Using classifier at {base_url}, threshold {threshold}, batch size "
              f"{batch_size}, thumb width {thumb_width}, category {category} (limit {limit})")
        try:
            files = category_image_batch(session, category, limit, thumb_width)
        except requests.exceptions.RequestException as e:
            print(f"failed to fetch category files: {e}")
            files = []
        chunks = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
        for batch in tqdm(chunks, desc=f"category {category}"):
            p, f, t = _process_batch(session, commons_site, repo, batch, nsfw_target,
                                     eg_string, threshold, base_url, dry_run)
            processed += p
            flagged += f
            tagged += t
            time.sleep(sleep)
    else:
        for _ in tqdm(range(batches), desc="nsfw commons batches"):
            try:
                batch = random_image_batch(session, batch_size, thumb_width)
            except requests.exceptions.RequestException as e:
                print(f"failed to fetch random Commons files: {e}")
                time.sleep(sleep)
                continue
            p, f, t = _process_batch(session, commons_site, repo, batch, nsfw_target,
                                     eg_string, threshold, base_url, dry_run)
            processed += p
            flagged += f
            tagged += t
            time.sleep(sleep)

    print(f"processed {processed} images, {flagged} over threshold, {tagged} newly tagged")
