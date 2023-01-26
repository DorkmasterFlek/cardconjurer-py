from PIL import Image
from django.core.management.base import BaseCommand

from creator import models


class Command(BaseCommand):
    help = """Resize current existing card images if they don't match what we want."""

    def add_arguments(self, parser):
        parser.add_argument('--width', type=int, default=models.Card.CARD_IMAGE_SIZE[0],
                            help='Width to resize card images to.  Default: %(default)s')

        parser.add_argument('--height', type=int, default=models.Card.CARD_IMAGE_SIZE[1],
                            help='Height to resize card images to.  Default: %(default)s')

    def handle(self, *args, **options):
        count = 0

        for card in models.Card.objects.all().order_by('pk'):
            updated = False

            for attr in ('front_image', 'back_image'):
                field = getattr(card, attr)
                if field and (field.width != options['width'] or field.height != options['height']):
                    image = Image.open(field.path)
                    image = image.resize((options['width'], options['height']), Image.LANCZOS)
                    image.save(field.path)
                    updated = True

            if updated:
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Resized card image(s) for card {card.pk} - "{card.name}"'))

        self.stdout.write(self.style.SUCCESS(f'Resized card image(s) for {count} cards'))
