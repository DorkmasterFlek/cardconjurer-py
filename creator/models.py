import mimetypes
import os
import re
import urllib.request

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils.deconstruct import deconstructible


# *** Helper functions for uploaded art and final generated card image paths for where to save them.

@deconstructible
class CardImagePathRename:
    """Helper class to make common card image path based on card ID and filename prefix."""

    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1]
        return "cards/{}/{}{}".format(instance.pk, self.prefix, ext)


_front_art_path = CardImagePathRename("front_art")
_front_image_path = CardImagePathRename("front_image")
_back_art_path = CardImagePathRename("back_art")
_back_image_path = CardImagePathRename("back_image")


# *** Models

class Set(models.Model):
    """Model for card set."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=16)
    set_symbol = models.CharField(max_length=16, blank=True, verbose_name='Set Symbol to Use')

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f'{self.name} ({self.code})'


class Card(models.Model):
    """Model for individual card."""
    set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name='cards')
    front = models.JSONField(verbose_name='Front Face Data')
    front_art = models.ImageField(blank=True, null=True, verbose_name='Front Face Art', upload_to=_front_art_path)
    front_image = models.ImageField(blank=True, null=True, verbose_name='Front Face Image', upload_to=_front_image_path)
    back = models.JSONField(blank=True, null=True, verbose_name='Back Face Data')
    back_art = models.ImageField(blank=True, null=True, verbose_name='Back Face Art', upload_to=_back_art_path)
    back_image = models.ImageField(blank=True, null=True, verbose_name='Back Face Image', upload_to=_back_image_path)

    class Meta:
        ordering = ["front__text__title__text"]

    def __str__(self):
        return f'{self.name}'

    # *** Internal helper functions.

    def _get_text(self, key, data=None):
        """Helper function to get text value from card data JSON based on key name.

        Args:
            key (str): Key of text value to get.
            data (dict): JSON data object.  If not provided, front face data will be used.

        Returns:
            str: That text value, if it exists.  Blank string otherwise.
        """

        if data is None:
            data = self.front

        return data.get('text', {}).get(key, {}).get('text', '')

    def _get_type_line_data(self, index, data=None):
        """Helper function to get type line data (main or subtypes) and split on dash."""

        line = re.split(r'{?-}?', self._get_text('type', data), 1, flags=re.IGNORECASE)
        if len(line) > index:
            return [s.strip() for s in line[index].split()]
        else:
            return []

    def _get_rules_data(self, index, data=None):
        """Helper function to get rules data (rules or flavor text) and split on flavor separator."""

        rules = self._get_text('rules', data)

        # If rules text is only italics, it's all flavor text.
        if re.match(r'^{i}[^{}]+({/i})?$', rules, flags=re.IGNORECASE):
            line = re.split(r'{i}', rules, 1, flags=re.IGNORECASE)
        # Otherwise, split on flavor separator or dash plus italics opener.
        else:
            line = re.split(r'{flavor}|{-}\s*{i}', rules, 1, flags=re.IGNORECASE)

        # TODO: Get additional rules text from other text objects (e.g. saga/planeswalker abilities).
        line[0] = re.sub(r'~|{cardname}', self.name, line[0], flags=re.IGNORECASE)

        return line[index] if len(line) > index else ''

    @transaction.atomic
    def save(self, **kwargs):
        """Perform a two stage save process for new cards with image fields null at first so we can use the primary key
        in image paths in a follow-up update."""

        two_stage_update = False
        images_to_update = {}

        if not self.pk:
            # Check for images if we're creating a new record.  If any are present, we need a two stage update.
            for name in ('front_art', 'front_image', 'back_art', 'back_image'):
                field = getattr(self, name, None)
                if field:
                    images_to_update[name] = field
                    setattr(self, name, None)
                    two_stage_update = True

            # Check if any face data has an uploaded art source.  If so, we need a two stage update.
            for key in ("front", "back"):
                data = getattr(self, key)
                if data and data.get('artSource') and data['artSource'].startswith('data:'):
                    two_stage_update = True

        # Otherwise check if we're uploading an art image inside the card face data.
        else:
            for key in ("front", "back"):
                data = getattr(self, key)
                if data and data.get('artSource') and data['artSource'].startswith('data:'):
                    response = urllib.request.urlopen(data['artSource'])
                    info = response.info()
                    ext = mimetypes.guess_extension(info.get_content_type())
                    art_key = f'{key}_art'
                    name = f'{art_key}{ext}'
                    setattr(self, art_key, ContentFile(response.file.read(), name=name))

                    # Calculate the URL path for the saved image file and set the art source to that.
                    img = getattr(self, art_key)
                    path = img.field.generate_filename(self, name)
                    data['artSource'] = img.storage.url(path)

        super().save(**kwargs)

        if two_stage_update:
            for name, field in images_to_update.items():
                setattr(self, name, field)
            kwargs.pop('force_insert', None)  # Make sure follow-up save is not an insert, if the caller passed this.
            self.save(**kwargs)

    # *** Main properties from JSON data.

    @property
    def name(self):
        """
        Returns:
            str: Card name (title) from front face.
        """
        return self._get_text('title') or 'Unknown'

    @property
    def name_back(self):
        """
        Returns:
            str: Card name (title) from back face.
        """
        return self._get_text('title', self.back)

    @property
    def cost(self):
        """
        Returns:
            str: Mana cost from front face.
        """
        return self._get_text('mana')

    @property
    def types(self):
        """
        Returns:
            list[str]: List of card types for front face (i.e. everything before the dash).
        """
        return self._get_type_line_data(0)

    @property
    def types_back(self):
        """
        Returns:
            list[str]: List of card types for back face (i.e. everything before the dash).
        """
        return self._get_type_line_data(0, self.back)

    @property
    def subtypes(self):
        """
        Returns:
            list[str]: List of card subtypes for front face (i.e. everything after the dash).
        """
        return self._get_type_line_data(1)

    @property
    def subtypes_back(self):
        """
        Returns:
            list[str]: List of card subtypes for back face (i.e. everything after the dash).
        """
        return self._get_type_line_data(1, self.back)

    @property
    def rules(self):
        """
        Returns:
            str: Rules text for front face.
        """
        return self._get_rules_data(0)

    @property
    def rules_back(self):
        """
        Returns:
            str: Rules text for back face.
        """
        return self._get_rules_data(0, self.back)

    @property
    def flavor(self):
        """
        Returns:
            str: Flavor text for front face.
        """
        return self._get_rules_data(1)

    @property
    def flavor_back(self):
        """
        Returns:
            str: Flavor text for back face.
        """
        return self._get_rules_data(1, self.back)

    @property
    def pt(self):
        """
        Returns:
            str: Power/toughness for front face.
        """
        return self._get_text('pt')

    @property
    def pt_back(self):
        """
        Returns:
            str: Power/toughness for back face.
        """
        return self._get_text('pt', self.back)

    # *** Helper properties to identify certain conditions.

    @property
    def is_double_faced(self):
        """
        Returns:
            bool: True if this is a double-faced card.
        """
        return bool(self.back)

    @property
    def is_creature(self):
        """
        Returns:
            bool: True if creature.
        """
        return "creature" in [s.lower() for s in self.types]

    @property
    def is_legendary(self):
        """
        Returns:
            bool: True if legendary.
        """
        return "legendary" in [s.lower() for s in self.types]

    @property
    def is_token(self):
        """
        Returns:
            bool: True if card is a token.
        """
        return "token" in [s.lower() for s in self.types]
