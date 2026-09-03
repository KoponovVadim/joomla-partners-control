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
                # Backward compatibility for old forms/scripts that still send one
                # plain `description` field and know nothing about the formset.
                legacy_description = request.POST.get("description", "").strip()
                if legacy_description and not client.description_variants.exists():
                    client.description_variants.create(
                        name="Основное",
                        text=legacy_description,
                        position=1,
                        enabled=True,
                    )

            active = list(client.description_variants.order_by("position", "id"))
            for position, variant in enumerate(active, start=1):
                if variant.position != position:
                    variant.position = position
            if active:
                client.description_variants.model.objects.bulk_update(active, ["position"])

            # Keep the legacy field synchronized as a fallback for old code/data.
            fallback = next(
                (variant.text for variant in active if variant.enabled and variant.text.strip()),
                "",
            )
            if client.description != fallback:
                client.description = fallback
                client.save(update_fields=["description", "updated_at"])

        messages.success(
            request,
            f"Клиент сохранён. Вариантов описания: {client.description_variants.filter(enabled=True).count()}.",
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
