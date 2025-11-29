# wiki/management/commands/check_categories.py
from django.core.management.base import BaseCommand
from wiki.models import Category


class Command(BaseCommand):
    help = 'Показывает текущие категории в системе'

    def handle(self, *args, **options):
        categories = Category.objects.all().order_by('display_order')

        if not categories.exists():
            self.stdout.write(self.style.ERROR('❌ Категории не найдены!'))
            self.stdout.write(self.style.WARNING('Запустите: python manage.py create_default_categories'))
            return

        self.stdout.write(self.style.SUCCESS('📋 Текущие категории:'))

        for category in categories:
            status = '⭐ Основная' if category.is_featured else '📄 Обычная'
            self.stdout.write(
                f"• {category.icon} {category.name} ({status})"
                f" - {category.articles.count()} статей"
            )