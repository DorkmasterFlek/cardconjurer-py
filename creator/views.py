import mimetypes
import urllib.request
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageFile
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import File
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


class SetStatsView(LoginRequiredMixin, DetailView):
    model = models.Set
    template_name = "creator/set_stats.html"
    context_object_name = 'set'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        charts = []

        # ******** Get stats data.

        @dataclass
        class StatColour:
            name: str
            bgcolour: str
            total: int = 0
            commanders: int = 0

            @property
            def attr(self):
                return self.name.lower()

        statcolours = [
            StatColour('White', '#ffffee'),
            StatColour('Blue', '#2222ff'),
            StatColour('Black', '#000000'),
            StatColour('Red', '#ff2222'),
            StatColour('Green', '#22ff22'),
            StatColour('Gold', '#ddbb66'),
            StatColour('Colourless', '#bbbbbb'),
        ]

        @dataclass
        class StatByColour:
            name: str
            colour: str
            white: int = 0
            blue: int = 0
            black: int = 0
            red: int = 0
            green: int = 0
            gold: int = 0
            colourless: int = 0

            @property
            def total(self) -> int:
                return self.white + self.blue + self.black + self.red + self.green + self.gold + self.colourless

        cardtypes = [
            StatByColour('Artifact', '#bbbbbb'),
            StatByColour('Creature', '#228822'),
            StatByColour('Enchantment', '#aaddcc'),
            StatByColour('Instant', '#555577'),
            StatByColour('Land', '#886644'),
            StatByColour('Planeswalker', '#9944bb'),
            StatByColour('Sorcery', '#992222'),
            StatByColour('Other', '#000000'),
        ]

        manavalues = [
            StatByColour('0', '#0000ff'),
            StatByColour('1', '#1100ee'),
            StatByColour('2', '#2200dd'),
            StatByColour('3', '#3300cc'),
            StatByColour('4', '#4400bb'),
            StatByColour('5', '#5500aa'),
            StatByColour('6+', '#660099'),
        ]

        for card in self.object.cards.all():
            # Counts by colour.
            statcolour = None
            if card.is_multicolour:
                statcolour = statcolours[5]
            elif card.is_colourless:
                statcolour = statcolours[6]
            else:
                match card.first_colour:
                    case models.Colour.WHITE:
                        statcolour = statcolours[0]
                    case models.Colour.BLUE:
                        statcolour = statcolours[1]
                    case models.Colour.BLACK:
                        statcolour = statcolours[2]
                    case models.Colour.RED:
                        statcolour = statcolours[3]
                    case models.Colour.GREEN:
                        statcolour = statcolours[4]

            statcolour.total += 1
            if card.can_be_commander:
                statcolour.commanders += 1

            # Counts by card type.
            found_type = False
            for cardtype in cardtypes:
                if card.has_type(cardtype.name) or (cardtype.name == 'Other' and not found_type):
                    found_type = True
                    setattr(cardtype, statcolour.attr, getattr(cardtype, statcolour.attr) + 1)

            # Counts by mana value (non-land cards only).
            if not card.is_land:
                found_mana_value = False
                for manavalue in manavalues:
                    if str(card.mana_value) == manavalue.name or (manavalue.name == '6+' and not found_mana_value):
                        found_mana_value = True
                        setattr(manavalue, statcolour.attr, getattr(manavalue, statcolour.attr) + 1)

        # Filter out types that didn't have any cards to save space.
        cardtypes = [cardtype for cardtype in cardtypes if cardtype.total > 0]

        # ******** Build charts.

        # Cards by type.
        charts.append({
            'id': 'cards_by_type',
            'type': 'bar',
            'data': {
                'datasets': [{
                    'data': [cardtype.total for cardtype in cardtypes],
                    'backgroundColor': [cardtype.colour for cardtype in cardtypes],
                    'borderColor': 'rgba(0, 0, 0, 0.5)',
                    'borderWidth': 1,
                    'label': 'Count',
                }],
                'labels': [cardtype.name for cardtype in cardtypes],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Cards By Type',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                    'subtitle': {
                        'display': True,
                        'position': 'bottom',
                        'font': {'style': 'italic'},
                        'text': 'Cards of multiple types count for both types',
                        'padding': {
                            'top': 10,
                        },
                    },
                },
            },
        })

        # Colours By Type (excluding lands)
        types_to_use = [cardtype for cardtype in cardtypes if cardtype.name != 'Land']
        datasets = []
        for colour in statcolours:
            datasets.append({
                'data': [getattr(cardtype, colour.attr) for cardtype in types_to_use],
                'backgroundColor': [colour.bgcolour] * len(types_to_use),
                'barPercentage': 1.0,
                'borderColor': 'rgba(0, 0, 0, 0.5)',
                'borderWidth': 1,
                'label': colour.name,
            })

        charts.append({
            'id': 'colours_by_type',
            'type': 'bar',
            'data': {
                'datasets': datasets,
                'labels': [cardtype.name for cardtype in types_to_use],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Colours By Type',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                    'subtitle': {
                        'display': True,
                        'position': 'bottom',
                        'font': {'style': 'italic'},
                        'text': 'Cards of multiple types count for both types',
                        'padding': {
                            'top': 10,
                        },
                    },
                },
            },
        })

        # Cards by mana value.
        charts.append({
            'id': 'cards_by_mana_value',
            'type': 'bar',
            'data': {
                'datasets': [{
                    'data': [manavalue.total for manavalue in manavalues],
                    'backgroundColor': [manavalue.colour for manavalue in manavalues],
                    'borderColor': 'rgba(0, 0, 0, 0.5)',
                    'borderWidth': 1,
                    'label': 'Count',
                }],
                'labels': [manavalue.name for manavalue in manavalues],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Cards By Mana Value',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                },
            },
        })

        # Colours by mana value.
        datasets = []
        for colour in statcolours:
            datasets.append({
                'data': [getattr(manavalue, colour.attr) for manavalue in manavalues],
                'backgroundColor': [colour.bgcolour] * len(manavalues),
                'barPercentage': 1.0,
                'borderColor': 'rgba(0, 0, 0, 0.5)',
                'borderWidth': 1,
                'label': colour.name,
            })

        charts.append({
            'id': 'colours_by_mana_value',
            'type': 'bar',
            'data': {
                'datasets': datasets,
                'labels': [manavalue.name for manavalue in manavalues],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Colours By Mana Value',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                },
            },
        })

        # Total cards by colour.
        charts.append({
            'id': 'cards_by_colour',
            'type': 'bar',
            'data': {
                'datasets': [{
                    'data': [statcolour.total for statcolour in statcolours],
                    'backgroundColor': [statcolour.bgcolour for statcolour in statcolours],
                    'borderColor': 'rgba(0, 0, 0, 0.5)',
                    'borderWidth': 1,
                    'label': 'Count',
                }],
                'labels': [statcolour.name for statcolour in statcolours],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Total Cards By Colour',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                },
            },
        })

        # Commanders by colour.
        charts.append({
            'id': 'legends_by_colour',
            'type': 'pie',
            'data': {
                'datasets': [{
                    'data': [statcolour.commanders for statcolour in statcolours],
                    'backgroundColor': [statcolour.bgcolour for statcolour in statcolours],
                    'borderColor': 'rgba(0, 0, 0, 0.5)',
                    'borderWidth': 1,
                    'label': 'Count',
                }],
                'labels': [statcolour.name for statcolour in statcolours],
            },
            'options': {
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': True,
                        'font': {'size': '24'},
                        'text': 'Commanders By Colour',
                        'padding': {
                            'bottom': 30,
                        },
                    },
                },
            },
        })

        context['charts'] = charts
        return context


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
        context['editing_back'] = self.editing_back
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

    def _get_image_content(self, data, key, resize=None):
        """Helper function to get image content for the key from incoming data URL format in JSON request.
        If resize is True, use Pillow to resize the image smaller (for final renders because they're GIANORMOUS).

        Args:
            data (dict): Form data dict.
            key (str): Field key name.
            resize (tuple[int]): Tuple of (width, height) to resize image, if needed.
        """

        if data.get(key):
            response = urllib.request.urlopen(data[key])
            info = response.info()
            ext = mimetypes.guess_extension(info.get_content_type())

            # Resize image if necessary.
            if resize:
                parser = ImageFile.Parser()
                parser.feed(response.read())
                image = parser.close()

                if image.width != resize[0] or image.height != resize[1]:
                    image = image.resize(resize, Image.LANCZOS)

                imgdata = BytesIO()
                image.save(imgdata, format=ext.strip('.'))

            # Otherwise use provided data.
            else:
                imgdata = BytesIO(response.read())

            imgdata.seek(0)
            data[key] = File(imgdata, name=f'{key}{ext}')

    def pre_process_data(self, request):
        """Pre-process the incoming POST data to get art image and uploaded image and create file objects."""

        new_data = request.data.copy()
        self._get_image_content(new_data, 'front_art')
        self._get_image_content(new_data, 'front_image', resize=models.Card.CARD_IMAGE_SIZE)
        self._get_image_content(new_data, 'back_art')
        self._get_image_content(new_data, 'back_image', resize=models.Card.CARD_IMAGE_SIZE)

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


class RemoveBackFaceAPIView(UpdateCardAPIView):
    def pre_process_data(self, request):
        """Pre-process the incoming POST data to remove any provided fields and clear back face data."""

        new_data = request.data.copy()
        new_data.clear()
        new_data['back'] = None
        new_data['back_art'] = None
        new_data['back_image'] = None

        # Hack to replace request data with new data since it's not directly modifiable.
        request._full_data = new_data
