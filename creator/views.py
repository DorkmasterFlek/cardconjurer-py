import mimetypes
import urllib.request

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import Http404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView, RedirectView, ListView
from rest_framework.generics import CreateAPIView, UpdateAPIView

from . import models
from . import serializers


class ListSetsView(LoginRequiredMixin, ListView):
    queryset = models.Set.objects.prefetch_related('cards').all()
    template_name = "creator/list_sets.html"
    context_object_name = 'sets'


class DisplaySetView(LoginRequiredMixin, ListView):
    template_name = "creator/view_set.html"
    context_object_name = 'cards'
    set = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['set'] = self.set
        return context

    def get_queryset(self):
        try:
            # Get the single item from the filtered queryset
            self.set = models.Set.objects.get(pk=self.kwargs['pk'])
        except models.Set.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": models.Set._meta.verbose_name}
            )

        return sorted(models.Card.objects.filter(set=self.set).all(), key=lambda card: card.set_number_key)


class CreateCardView(LoginRequiredMixin, DetailView):
    model = models.Set
    template_name = "creator/creator.html"
    context_object_name = 'set'


class EditCardFrontView(LoginRequiredMixin, DetailView):
    model = models.Card
    template_name = "creator/creator.html"
    context_object_name = 'card'
    editing_back = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['face_to_edit'] = self.object.back if self.editing_back else self.object.front
        return context


class EditCardBackView(EditCardFrontView):
    """Subclass for editing the back of a double-faced card."""
    editing_back = True


class DisplayCardView(LoginRequiredMixin, DetailView):
    model = models.Card
    template_name = "creator/view_card.html"
    context_object_name = 'card'


class CardConjurerStaticRedirectView(RedirectView):
    """Redirect view to handle absolute paths to static CardConjurer content."""
    base_dir = ''

    @property
    def url(self):
        return static('cardconjurer_static/{}/'.format(self.base_dir)) + '%(path)s'


# *** JSON API views

class CardAPIMixIn(LoginRequiredMixin):
    serializer_class = serializers.CardSerializer

    def _get_image_content(self, data, key):
        """Helper function to get image content for the key from incoming data URL format in JSON request."""

        if data.get(key):
            response = urllib.request.urlopen(data[key])
            info = response.info()
            ext = mimetypes.guess_extension(info.get_content_type())
            data[key] = ContentFile(response.file.read(), name=f'{key}{ext}')

    def pre_process_data(self, request):
        """TODO: Pre-process the incoming POST data to get art image and uploaded image and create file objects."""

        new_data = request.data.copy()
        self._get_image_content(new_data, 'front_art')
        self._get_image_content(new_data, 'front_image')
        self._get_image_content(new_data, 'back_art')
        self._get_image_content(new_data, 'back_image')

        # Hack to replace request data with new data since it's not directly modifiable.
        request._full_data = new_data

    def post_process_data(self, response):
        """Post-process the outgoing data to send the view card URL back to the caller."""

        response.data['view_url'] = reverse('view-card', args=[response.data['id']])


class CreateCardAPIView(CardAPIMixIn, CreateAPIView):
    def perform_create(self, serializer):
        """Add Django message after DB update."""

        super().perform_create(serializer)
        messages.success(self.request, "Card added successfully.")

    def post(self, request, *args, **kwargs):
        self.pre_process_data(request)
        response = super().post(request, *args, **kwargs)
        self.post_process_data(response)
        return response


class UpdateCardAPIView(CardAPIMixIn, UpdateAPIView):
    queryset = models.Card.objects.all()

    def perform_update(self, serializer):
        """Add Django message after DB update."""

        super().perform_update(serializer)
        messages.success(self.request, "Card updated successfully.")

    def post(self, request, *args, **kwargs):
        """Allow using POST to update cards and default to partial update (PATCH method)."""
        return self.patch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        self.pre_process_data(request)
        response = super().put(request, *args, **kwargs)
        self.post_process_data(response)
        return response

    def patch(self, request, *args, **kwargs):
        self.pre_process_data(request)
        response = super().patch(request, *args, **kwargs)
        self.post_process_data(response)
        return response
