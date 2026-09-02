from mimetypes import guess_type

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404


def public_media(request, path):
    """Serve uploaded partner media in production without exposing arbitrary files."""
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
