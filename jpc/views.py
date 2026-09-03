from mimetypes import guess_type
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404


PUBLIC_MEDIA_DIRECTORY = PurePosixPath("client_logos")
PUBLIC_MEDIA_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}


def public_media(request, path):
    """Serve only directly uploaded client logo images in production."""
    candidate = PurePosixPath(path)
    if (
        candidate.parent != PUBLIC_MEDIA_DIRECTORY
        or candidate.name in {"", ".", ".."}
        or candidate.suffix.lower() not in PUBLIC_MEDIA_EXTENSIONS
    ):
        raise Http404("Media file not found")

    storage = FileSystemStorage(
        location=settings.MEDIA_ROOT,
        base_url=settings.MEDIA_URL,
    )
    try:
        handle = storage.open(candidate.as_posix(), "rb")
    except (FileNotFoundError, SuspiciousFileOperation, OSError) as exc:
        raise Http404("Media file not found") from exc

    content_type = guess_type(candidate.name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response
