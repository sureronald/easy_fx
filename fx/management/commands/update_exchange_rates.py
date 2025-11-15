from django.core.management.base import BaseCommand
from fx.services import update_all_exchange_rates


class Command(BaseCommand):
    help = 'Manually update exchange rates for all active currencies'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting exchange rates update...'))

        try:
            update_all_exchange_rates()
            self.stdout.write(self.style.SUCCESS('Exchange rates updated successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to update exchange rates: {str(e)}'))
            raise
