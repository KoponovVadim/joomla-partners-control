import httpx
from django.utils import timezone

from partners.models import DonorSite


DEFAULT_TIMEOUT_SECONDS = 12
USER_AGENT = "JPC-Page-Monitor/1.0 (+https://parasyte.deluxmedia.ru/)"


def check_donor_page(donor, *, client=None, checked_at=None):
    checked_at = checked_at or timezone.now()
    owns_client = client is None
    client = client or httpx.Client(
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
    )

    status_code = None
    error = ""
    try:
        response = client.get(donor.page_url)
        status_code = response.status_code
    except httpx.HTTPError as exc:
        error = str(exc)[:1000]
    finally:
        if owns_client:
            client.close()

    unhealthy = status_code is None or status_code >= 400
    previous_unhealthy = (
        donor.page_checked_at is not None
        and (donor.page_http_status is None or donor.page_http_status >= 400)
    )

    donor.page_http_status = status_code
    donor.page_checked_at = checked_at
    donor.page_check_error = error
    if unhealthy:
        if not previous_unhealthy or donor.page_unhealthy_since is None:
            donor.page_unhealthy_since = checked_at
    else:
        donor.page_unhealthy_since = None

    donor.save(
        update_fields=[
            "page_http_status",
            "page_checked_at",
            "page_unhealthy_since",
            "page_check_error",
            "updated_at",
        ]
    )
    return status_code, error


def check_all_donor_pages(*, queryset=None):
    queryset = queryset if queryset is not None else DonorSite.objects.filter(enabled=True)
    checked_at = timezone.now()
    results = []
    with httpx.Client(
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
    ) as client:
        for donor in queryset.iterator():
            status_code, error = check_donor_page(
                donor,
                client=client,
                checked_at=checked_at,
            )
            results.append((donor.pk, status_code, error))
    return results
