from html import escape

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ClientDescriptionVariantFormSet, ClientForm
from .models import ClientSite


@login_required
def client_edit(request, pk=None):
    client = get_object_or_404(ClientSite, pk=pk) if pk else ClientSite()
    form = ClientForm(request.POST or None, request.FILES or None, instance=client)
    has_variant_payload = request.method != "POST" or "descriptions-TOTAL_FORMS" in request.POST
    variants = ClientDescriptionVariantFormSet(
        request.POST if request.method == "POST" and has_variant_payload else None,
        instance=client,
        prefix="descriptions",
    )
    variants_valid = variants.is_valid() if request.method == "POST" and has_variant_payload else True

    if request.method == "POST" and form.is_valid() and variants_valid:
        with transaction.atomic():
            client = form.save()
            if has_variant_payload:
                variants.instance = client
                variants.save()
            else:
                # Совместимость со старыми формами/скриптами.
                legacy_html = request.POST.get("default_html", "").strip()
                if not legacy_html:
                    legacy_text = request.POST.get("description", "").strip()
                    if legacy_text:
                        legacy_html = escape(legacy_text).replace("\r\n", "\n").replace("\n", "<br>\n")
                if legacy_html and not client.description_variants.exists():
                    client.description_variants.create(
                        name="Основное",
                        html=legacy_html,
                        position=1,
                        enabled=True,
                    )

            all_variants = list(client.description_variants.order_by("position", "id"))
            changed = []
            for position, variant in enumerate(all_variants, start=1):
                if variant.position != position:
                    variant.position = position
                    changed.append(variant)
            if changed:
                client.description_variants.model.objects.bulk_update(changed, ["position"])

            # Legacy fallback синхронизируем с первым активным HTML-вариантом.
            fallback_html = next(
                (variant.html for variant in all_variants if variant.enabled and variant.html.strip()),
                "",
            )
            if client.default_html != fallback_html:
                client.default_html = fallback_html
                client.save(update_fields=["default_html", "updated_at"])

        messages.success(
            request,
            f"Клиент сохранён. HTML-вариантов: {client.description_variants.filter(enabled=True).count()}.",
        )
        return redirect("client-edit", pk=client.pk)

    return render(
        request,
        "partners/form.html",
        {
            "form": form,
            "description_formset": variants,
            "title": "Новый клиент" if not client.pk else f"Клиент: {client.name}",
            "object": client if client.pk else None,
            "kind": "client",
        },
    )
