import enum
import math
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


def int_to_roman(num):
    """Helper function to convert integer to a Roman numeral string.

    Args:
        num (int): Integer to convert.

    Returns:
        str: Roman numeral representation.
    """
    romans_dict = {
        1: "I",
        5: "V",
        10: "X",
        50: "L",
        100: "C",
        500: "D",
        1000: "M",
        5000: "G",
        10000: "H",
    }

    div = 1
    while num >= div:
        div *= 10

    div /= 10

    res = ""

    while num:

        # main significant digit extracted
        # into lastNum
        last_num = int(num / div)

        if last_num <= 3:
            res += (romans_dict[div] * last_num)
        elif last_num == 4:
            res += (romans_dict[div] +
                    romans_dict[div * 5])
        elif 5 <= last_num <= 8:
            res += (romans_dict[div * 5] +
                    (romans_dict[div] * (last_num - 5)))
        elif last_num == 9:
            res += (romans_dict[div] +
                    romans_dict[div * 10])

        num = math.floor(num % div)
        div /= 10

    return res


class Colour(enum.IntEnum):
    """Ranking enumeration of card colours to sort in WUBRG order."""
    WHITE = 1
    BLUE = 2
    BLACK = 3
    RED = 4
    GREEN = 5
    MULTICOLOR = 6
    COLORLESS = 7


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
    # Final card image render size to resize images to (width, height).
    # Card renders from the CardConjurer editor are HUGE (1500 x 2100) so make this something more reasonable.
    CARD_IMAGE_SIZE = (500, 700)

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

    def _get_text(self, key, data=None, remove_symbols=False):
        """Helper function to get text value from card data JSON based on key name.

        Args:
            key (str): Key of text value to get.
            data (dict): JSON data object.  If not provided, front face data will be used.
            remove_symbols (bool): If True, remove any curly brace symbols from the text.  This is useful for removing
                                   formatting tags from certain fields that don't need any, e.g. name and types.

        Returns:
            str: That text value, if it exists.  Blank string otherwise.
        """

        if data is None:
            data = self.front

        s = data.get('text', {}).get(key, {}).get('text', '')

        # Remove symbols?
        if remove_symbols:
            s = re.sub(r'\{([^}]+)}', '', s, flags=re.IGNORECASE)

        # Remove leading/trailing whitespace.
        s = s.strip()

        # Check if the piece of text has an unclosed italics tag (some reminder text or flavor text does).
        s = re.sub(r'{i}(?!.*{/i})(.*)', r'{i}\1{/i}', s, flags=re.IGNORECASE)

        # Replace divider tag with line break.
        s = re.sub(r'{divider}', '\n', s, flags=re.IGNORECASE)

        return s

    def _get_type_line_data(self, index, data=None):
        """Helper function to get type line data (main or subtypes) and split on dash."""

        line = re.split(r'{?-}?', self._get_text('type', data), 1, flags=re.IGNORECASE)
        if len(line) > index:
            return [s.strip() for s in line[index].split()]
        else:
            return []

    def _get_rules_data(self, index, data=None):
        """Helper function to get rules data (rules or flavor text) and split on flavor separator."""

        if data is None:
            data = self.front

        rules = self._get_text('rules', data)

        # If rules text is only italics, it's all flavor text.
        if re.match(r'^{i}[^{}]+{/i}$', rules, flags=re.IGNORECASE):
            line = ['', rules]
        # Otherwise, split on flavor separator or dash plus italics opener.
        else:
            line = re.split(r'{flavor}|{-}\s*{i}', rules, 1, flags=re.IGNORECASE)

        line = line[index] if len(line) > index else ''

        # If we're getting rules text (index 0), get additional rules text from other text objects for card types.
        if index == 0:
            # Planeswalker abilities.  List of ability costs has corresponding text element "ability<x>".
            if data.get('planeswalker') and isinstance(data['planeswalker'].get('abilities'), (list, tuple)):
                for i, cost in enumerate(data['planeswalker']['abilities']):
                    cost = cost.strip()
                    ability = self._get_text(f'ability{i}', data)
                    if ability:
                        # Cost is optional.  Might be static/triggered ability.
                        if cost:
                            line += f'{cost}: '
                        line += ability + '\n'

            # Saga chapters.  List of ability costs has corresponding text element "ability<x>".
            if data.get('saga') and isinstance(data['saga'].get('abilities'), (list, tuple)):
                line += self._get_text('reminder', data) + '\n'
                chapter = 0

                for i, cost in enumerate(data['saga']['abilities']):
                    if cost.strip().isdigit():
                        cost = int(cost)
                        line_chapters = []

                        while cost > 0:
                            chapter += 1
                            line_chapters.append(int_to_roman(chapter))
                            cost -= 1

                        if line_chapters:
                            line += f'{", ".join(line_chapters)} {{-}} ' + self._get_text(f'ability{i}', data) + '\n'

            # Class abilities.
            if data.get('class') and isinstance(data['class'].get('count'), int) and data['class']['count'] > 0:
                line += self._get_text('level0c') + '\n'
                for i in range(1, data['class']['count'] + 1):
                    cost = self._get_text(f'level{i}a', data).strip(':')
                    name = self._get_text(f'level{i}b', data)
                    line += f'{cost}: {name}' + '\n'
                    line += self._get_text(f'level{i}c') + '\n'

            # Once we have everything, replace tilde or {cardname} with the card name.
            line = re.sub(r'~|{cardname}', self.name, line, flags=re.IGNORECASE)

            # Add extra line break between each line of rules text for paragraph breaks.
            line = re.sub(r'[\r\n]+', '\n\n', line)

            # But make sure there's only one line break between bullet points (spell modes).
            line = re.sub(r'\s+({\.}|•)', r'\n\1', line, flags=re.IGNORECASE)

        # If we're getting flavor text (index 1), remove all italics tags (it will be italic on the display).
        elif index == 1:
            line = re.sub(r'{/?i}', '', line, flags=re.IGNORECASE)

        return line.strip()

    def _has_type(self, value):
        """Helper function to check if a card has a given type on its type line (not subtypes).

        Args:
            value (str): Type to check.

        Returns:
            bool: True if card has this type, False otherwise.
        """
        return value.lower() in [s.lower() for s in self.types]

    def _has_subtype(self, value):
        """Helper function to check if a card has a given subtype on its type line.

        Args:
            value (str): Subtype to check.

        Returns:
            bool: True if card has this subtype, False otherwise.
        """
        return value.lower() in [s.lower() for s in self.subtypes]

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
        return self._get_text('title', remove_symbols=True) or 'Unknown'

    @property
    def name_back(self):
        """
        Returns:
            str: Card name (title) from back face.
        """
        return self._get_text('title', self.back, remove_symbols=True)

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

    @property
    def loyalty(self):
        """
        Returns:
            str: Starting loyalty for front face.
        """
        return self._get_text('loyalty')

    @property
    def loyalty_back(self):
        """
        Returns:
            str: Starting loyalty for back face.
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
        return self._has_type("creature")

    @property
    def is_legendary(self):
        """
        Returns:
            bool: True if legendary.
        """
        return self._has_type("legendary")

    @property
    def is_artifact(self):
        """
        Returns:
            bool: True if artifact.
        """
        return self._has_type("artifact")

    @property
    def is_land(self):
        """
        Returns:
            bool: True if land.
        """
        return self._has_type("land")

    @property
    def is_token(self):
        """
        Returns:
            bool: True if card is a token.
        """
        return self._has_type("token")

    @property
    def colours(self):
        """
        Returns:
            list[Colour]: List of colours this card has in its cost.
        """

        colours = []
        cost = self.cost.upper()

        for code, colour in (
                ('W', Colour.WHITE),
                ('U', Colour.BLUE),
                ('B', Colour.BLACK),
                ('R', Colour.RED),
                ('G', Colour.GREEN),
        ):
            if code in cost:
                colours.append(colour)

        return colours

    @property
    def set_number_key(self):
        """
        Returns:
            tuple: Tuple that can be used as a sorting key for set number order logic.
        """

        # Put tokens at the very end.
        token_key = 1 if not self.is_token else 2

        # Colours go in WUBRG order, then multicolour, then colourless.
        colours = self.colours
        if len(colours) == 1:
            colour_key = colours[0]
        elif len(colours) > 1:
            colour_key = Colour.MULTICOLOR
        else:
            colour_key = Colour.COLORLESS

        # Non-lands (e.g. artifacts) go first, then lands.
        type_key = 1 if not self.is_land else 2

        # Final key is name alphabetically.  Remove "a", "an", "and" the from the start.
        name_key = self.name.lower()
        for prefix in ('a ', 'an ', 'the '):
            if name_key.startswith(prefix):
                name_key = name_key[len(prefix):]

        # Return final tuple.
        return token_key, colour_key, type_key, name_key
