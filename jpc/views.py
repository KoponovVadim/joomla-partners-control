from mimetypes import guess_type

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404


PUBLIC_MEDIA_PREFIX = "client_logos/"


def public_media(request, path):
    """Serve only uploaded client logos in production."""
    if not path.startswith(PUBLIC_MEDIA_PREFIX):
        raise Http404("Media file not found")

    storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    try:
        handle = storage.open(path, "rb")
    except (FileNotFoundError, SuspiciousFileOperation, OSError) as exc:
        raise Http404("Media file not found") from exc

    content_type = guess_type(path)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response
