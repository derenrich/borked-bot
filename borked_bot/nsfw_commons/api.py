from typing import Any, Dict, List, Optional

import requests

from ..util.util import retry

# NSFW classifier server. Spec: https://github.com/derenrich/nsfw-classifier
# POST /classify-batch/<model> with a JSON body that is a raw list of image
# URLs (or host file paths). Returns a list of ClassificationResult objects:
#   {"file_path": <url>, "predictions": [{"label": ..., "score": ...}], "error": <str|null>}
# Falconsai/nsfw_image_detection_26 emits the labels "normal" and "nsfw".
DEFAULT_BASE_URL = "https://ml.34364836.xyz"
DEFAULT_MODEL = "falconsai"


@retry(exceptions=[requests.exceptions.RequestException])
def classify_batch(session: requests.Session, urls: List[str],
                   base_url: str = DEFAULT_BASE_URL,
                   model: str = DEFAULT_MODEL,
                   timeout: int = 600) -> List[Dict[str, Any]]:
    """Send a batch of image URLs to the classifier and return the raw results.

    The request body is a bare JSON array of strings, matching the server's
    ``file_paths: List[str]`` signature. Results are returned in the same order
    as the input URLs.
    """
    endpoint = f"{base_url.rstrip('/')}/classify-batch/{model}"
    resp = session.post(endpoint, json=list(urls), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def nsfw_score(result: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extract the NSFW probability from a single ClassificationResult.

    Returns ``None`` if the image failed to load/classify or no NSFW label is
    present in the predictions.
    """
    if not result or result.get("error"):
        return None
    for pred in result.get("predictions") or []:
        if "nsfw" in (pred.get("label") or "").lower():
            return float(pred.get("score", 0.0))
    return None
