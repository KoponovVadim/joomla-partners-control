from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("donors/new/", views.donor_edit, name="donor-create"),
    path("donors/<int:pk>/edit/", views.donor_edit, name="donor-edit"),
    path("donors/<int:pk>/preview/", views.donor_preview, name="donor-preview"),
    path("donors/<int:pk>/test/", views.donor_test, name="donor-test"),
    path("donors/<int:pk>/sync/", views.donor_sync, name="donor-sync"),
    path("donors/<int:pk>/adopt/", views.donor_adopt, name="donor-adopt"),
    path("donors/<int:pk>/placements/add/", views.placement_add, name="placement-add"),
    path("placements/<int:pk>/edit/", views.placement_edit, name="placement-edit"),
    path("placements/<int:pk>/toggle/", views.placement_toggle, name="placement-toggle"),
    path("placements/<int:pk>/remove/", views.placement_remove, name="placement-remove"),
    path("placements/reorder/", views.placements_reorder, name="placements-reorder"),
    path("clients/new/", views.client_edit, name="client-create"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client-edit"),
    path("clients/<int:pk>/archive/", views.client_archive, name="client-archive"),
    path("templates/", views.template_edit, name="template-edit"),
    path("logs/", views.logs, name="logs"),
]
