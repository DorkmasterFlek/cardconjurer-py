from django.urls import path

from . import views

urlpatterns = [
    # Main web views.
    path('', views.ListSetsView.as_view(), name='list-sets'),
    path('view-set/<int:pk>', views.DisplaySetView.as_view(), name='view-set'),
    path('create-card/<int:pk>', views.CreateCardView.as_view(), name='create-card'),
    path('edit-card-front/<int:pk>', views.EditCardFrontView.as_view(), name='edit-card-front'),
    path('edit-card-back/<int:pk>', views.EditCardBackView.as_view(), name='edit-card-back'),
    path('view-card/<int:pk>', views.DisplayCardView.as_view(), name='view-card'),

    # API views.
    path('api/create-card', views.CreateCardAPIView.as_view(), name='api-create-card'),
    path('api/update-card/<int:pk>', views.UpdateCardAPIView.as_view(), name='api-update-card'),

    # Handle absolute paths from the CardConjurer source by redirecting them to the static URLs.
    path('fonts/<path:path>', views.CardConjurerStaticRedirectView.as_view(base_dir='fonts')),
    path('img/<path:path>', views.CardConjurerStaticRedirectView.as_view(base_dir='img')),
    path('js/<path:path>', views.CardConjurerStaticRedirectView.as_view(base_dir='js')),
]
