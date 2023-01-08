import json
import re
import urllib.parse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from creator import models


class Command(BaseCommand):
    help = 'Imports cards in saved JSON files from previous CardConjurer site.'

    def _make_urls_local(self, data):
        """Helper function to recursively check all keys in data and make old URLs into local ones.
        Also check for Gatherer set symbol URLs and turn that into the equivalent local set one.
        """

        if isinstance(data, dict):
            return {k: self._make_urls_local(v) for k, v in data.items()}

        elif isinstance(data, (list, tuple)):
            return [self._make_urls_local(v) for v in data]

        # String checks for URLs.
        elif isinstance(data, str):
            if re.match(r'^https?:', data, flags=re.IGNORECASE):
                u = urllib.parse.urlparse(data)

                # Gatherer set images.  If we have set code and rarity, convert to local image.  Otherwise leave alone.
                if u.hostname == 'gatherer.wizards.com':
                    qs = urllib.parse.parse_qs(u.query)
                    if qs.get('set') and qs.get('rarity'):
                        return f"/img/setSymbols/official/{qs['set'][0].lower()}-{qs['rarity'][0].lower()}.svg"
                    else:
                        return data

                # Old localhost images and old CardConjurer cache, convert to just path for the new site.
                elif u.hostname.lower() in ('127.0.0.1', 'localhost', 'card-conjurer.storage.googleapis.com'):
                    return u.path

                # External URL, leave it alone.
                else:
                    return data

            # Already no hostname, leave it alone.
            else:
                return data

        # Return whatever the value is by default.
        else:
            return data

    def add_arguments(self, parser):
        parser.add_argument('set', type=int, help='Set ID to add imported cards.')

        parser.add_argument('file', nargs='+', help='File(s) to process.')

    def handle(self, *args, **options):
        try:
            set = models.Set.objects.get(pk=options['set'])
        except models.Set.DoesNotExist:
            raise CommandError(f"Set {options['set']} not found")

        count = 0

        for name in options['file']:
            with open(name) as f:
                records = json.load(f)
                if not isinstance(records, (list, tuple)):
                    records = [records]

                for i, record in enumerate(records, 1):
                    if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                        self.stderr.write(self.style.ERROR(f'Line {i} - Invalid record'))
                        continue

                    data = self._make_urls_local(record['data'])

                    card = models.Card(set=set, front=data)
                    if not card.name:
                        self.stderr.write(self.style.ERROR(f'Line {i} - Card data has no name'))
                        continue

                    # Info note was added later, so make sure it's defined to avoid "undefined" text/error.
                    if card.front.get('infoNote') in (None, "undefined", "null"):
                        card.front['infoNote'] = ''

                    # Override set code to our set.
                    card.front['infoSet'] = set.code

                    with transaction.atomic():
                        card.save()
                        count += 1
                        self.stdout.write(self.style.SUCCESS(f'Successfully imported card "{card.name}"'))

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} cards'))
