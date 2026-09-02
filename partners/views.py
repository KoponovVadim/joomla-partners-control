import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import ClientForm, DonorForm, PageTemplateForm, PlacementForm
from .joomla import get_adapter
from .joomla.exceptions import JoomlaError, JoomlaNotImplementedError
from .models import ClientSite, DonorSite, PageTemplate, Placement, PublicationLog
from .services.credentials import encrypt_password
from .services.page_renderer import render_page


@login_required
def dashboard(request):
    mode = request.GET.get("mode", "donors")
    query = request.GET.get("q", "").strip()
    donors = DonorSite.objects.select_related("template").prefetch_related("placements__client")
    clients = ClientSite.objects.annotate(placement_count=Count("placements")).prefetch_related("placements__donor")
    if query:
        donors = donors.filter(Q(name__icontains=query) | Q(domain__icontains=query))
        clients = clients.filter(Q(name__icontains=query) | Q(domain__icontains=query))
    return render(request, "partners/dashboard.html", {"mode": mode, "query": query, "donors": donors, "clients": clients})


@login_required
def donor_edit(request, pk=None):
    donor = get_object_or_404(DonorSite, pk=pk) if pk else None
    form = DonorForm(request.POST or None, instance=donor)
    if request.method == "POST" and form.is_valid():
        donor = form.save(commit=False)
        password = form.cleaned_data["password"]
        if password:
            donor.encrypted_password = encrypt_password(password)
        donor.save()
        messages.success(request, "Настройки донора сохранены.")
        return redirect("dashboard")
    return render(request, "partners/form.html", {"form": form, "title": "Новый донор" if not donor else f"Настройки: {donor.domain}", "object": donor, "kind": "donor"})


@login_required
def client_edit(request, pk=None):
    client = get_object_or_404(ClientSite, pk=pk) if pk else None
    form = ClientForm(request.POST or None, request.FILES or None, instance=client)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, "Клиент сохранён.")
        return redirect("dashboard")
    return render(request, "partners/form.html", {"form": form, "title": "Новый клиент" if not client else f"Клиент: {client.name}", "object": client, "kind": "client"})


@login_required
def template_edit(request):
    template = PageTemplate.objects.order_by("id").first()
    form = PageTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Шаблон сохранён.")
        return redirect("template-edit")
    return render(request, "partners/form.html", {"form": form, "title": "Шаблон страницы", "object": template, "kind": "template"})


@login_required
def placement_edit(request, pk):
    placement = get_object_or_404(Placement.objects.select_related("donor", "client"), pk=pk)
    form = PlacementForm(request.POST or None, instance=placement)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "Настройки размещения сохранены.")
        return redirect("dashboard")
    return render(request, "partners/form.html", {"form": form, "title": f"{placement.client.name} на {placement.donor.domain}", "object": placement, "kind": "placement"})


@login_required
def donor_preview(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    try: page = render_page(donor)
    except ValueError as exc:
        messages.error(request, str(exc)); return redirect("donor-edit", pk=pk)
    PublicationLog.objects.create(donor=donor, action="preview", status="success", message="Сформирован локальный предпросмотр", generated_html_hash=page.body_hash)
    return render(request, "partners/preview.html", {"donor": donor, "page": page})


def _adapter_action(donor, action, callback, html_hash=""):
    try:
        result = callback(get_adapter(donor))
        status, message = "success", str(result or "Операция выполнена")
    except JoomlaNotImplementedError as exc:
        status, message = "not_implemented", str(exc)
    except JoomlaError as exc:
        status, message = "error", str(exc)
    PublicationLog.objects.create(donor=donor, action=action, status=status, message=message, generated_html_hash=html_hash)
    return status, message


@login_required
@require_POST
def donor_test(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    status, message = _adapter_action(donor, "connection_test", lambda adapter: adapter.test_connection())
    donor.connection_status = "online" if status == "success" else status
    donor.last_checked_at = timezone.now(); donor.save(update_fields=["connection_status", "last_checked_at", "updated_at"])
    messages.info(request, message)
    return redirect("donor-edit", pk=pk)


@login_required
@require_POST
def donor_sync(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    try: page = render_page(donor)
    except ValueError as exc:
        messages.error(request, str(exc)); return redirect("dashboard")
    if donor.article_id:
        status, message = _adapter_action(donor, "update_article", lambda adapter: adapter.update_article(donor.article_id, page.final_html), page.body_hash)
    else:
        status, message = _adapter_action(donor, "create_article", lambda adapter: adapter.create_article(alias=donor.article_alias, html=page.final_html), page.body_hash)
    if status == "success":
        donor.last_published_at = timezone.now(); donor.save(update_fields=["last_published_at", "updated_at"])
    messages.info(request, message)
    return redirect("dashboard")


@login_required
@require_POST
def donor_adopt(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    if donor.joomla_version != "3" or not donor.article_id:
        messages.error(request, "Для принятия укажите Joomla 3 и ID существующего материала.")
        return redirect("donor-edit", pk=pk)
    status, message = _adapter_action(
        donor, "adopt_article", lambda adapter: adapter.adopt_article(donor.article_id)
    )
    messages.success(request, message) if status == "success" else messages.error(request, message)
    return redirect("donor-edit", pk=pk)


@login_required
@require_POST
def placement_add(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    client = get_object_or_404(ClientSite, pk=request.POST.get("client_id"), enabled=True)
    if Placement.objects.filter(donor=donor, client=client).exists():
        messages.warning(request, "Этот клиент уже добавлен к донору.")
    else:
        last_position = donor.placements.order_by("-position").values_list("position", flat=True).first()
        Placement.objects.create(donor=donor, client=client, position=(last_position or 0) + 1)
        messages.success(request, "Клиент добавлен к донору.")
    return redirect("dashboard")


@login_required
@require_POST
def placement_toggle(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    placement.enabled = not placement.enabled
    placement.save(update_fields=["enabled", "updated_at"])
    return JsonResponse({"ok": True, "enabled": placement.enabled})


@login_required
@require_POST
def placement_remove(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    placement.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def placements_reorder(request):
    try:
        ids = [int(value) for value in json.loads(request.body).get("ids", [])]
    except (ValueError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest("Некорректный список")
    placements = list(Placement.objects.filter(pk__in=ids))
    if len(placements) != len(ids) or (placements and len({p.donor_id for p in placements}) != 1):
        return HttpResponseBadRequest("Размещения должны принадлежать одному донору")
    with transaction.atomic():
        for position, placement_id in enumerate(ids, start=1):
            Placement.objects.filter(pk=placement_id).update(position=position)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def client_archive(request, pk):
    client = get_object_or_404(ClientSite, pk=pk)
    client.enabled = False
    client.save(update_fields=["enabled", "updated_at"])
    messages.success(request, "Клиент перемещён в архив; связанные размещения сохранены.")
    return redirect("dashboard")


@login_required
@require_POST
def placement_add(request, pk):
    donor = get_object_or_404(DonorSite, pk=pk)
    client_id = request.POST.get("client_id")
    if not client_id: return HttpResponseBadRequest("Клиент не выбран")
    client = get_object_or_404(ClientSite, pk=client_id)
    position = (donor.placements.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    _, created = Placement.objects.get_or_create(donor=donor, client=client, defaults={"position": position})
    messages.success(request, "Клиент добавлен." if created else "Клиент уже размещён на этом доноре.")
    return redirect("dashboard")


@login_required
@require_POST
def placement_toggle(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    placement.enabled = not placement.enabled; placement.save(update_fields=["enabled", "updated_at"])
    return JsonResponse({"ok": True, "enabled": placement.enabled})


@login_required
@require_POST
def placement_remove(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    placement.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def placements_reorder(request):
    try: ids = [int(value) for value in json.loads(request.body).get("ids", [])]
    except (ValueError, TypeError, json.JSONDecodeError): return JsonResponse({"ok": False}, status=400)
    placements = list(Placement.objects.filter(pk__in=ids))
    if len(placements) != len(ids) or len({p.donor_id for p in placements}) > 1: return JsonResponse({"ok": False}, status=400)
    positions = {pk: index for index, pk in enumerate(ids)}
    with transaction.atomic():
        for placement in placements: placement.position = positions[placement.pk]
        Placement.objects.bulk_update(placements, ["position"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def client_archive(request, pk):
    client = get_object_or_404(ClientSite, pk=pk)
    client.enabled = False; client.save(update_fields=["enabled", "updated_at"])
    messages.success(request, "Клиент архивирован; связанные размещения сохранены.")
    return redirect("dashboard")


@login_required
def logs(request):
    return render(request, "partners/logs.html", {"logs": PublicationLog.objects.select_related("donor")[:500]})
