# wiki/management/commands/create_default_categories.py
from django.core.management.base import BaseCommand
from wiki.models import Category


class Command(BaseCommand):
    help = 'Создает базовые категории для вики Ведьмака'

    def handle(self, *args, **options):
        default_categories = [
            {
                'name': 'Персонажи',
                'description': 'Статьи о людях, эльфах, магах и других разумных существах',
                'icon': '👤',
                'is_featured': True,
                'display_order': 1
            },
            {
                'name': 'Монстры',
                'description': 'Бестиарий чудовищ и существ',
                'icon': '🐺',
                'is_featured': True,
                'display_order': 2
            },
            {
                'name': 'Локации',
                'description': 'Королевства, города и важные места',
                'icon': '🗺️',
                'is_featured': True,
                'display_order': 3
            },
            {
                'name': 'Магия',
                'description': 'Статьи о магии, заклинаниях, знаках и магических существах',
                'icon': '🔮',
                'is_featured': True,
                'display_order': 4
            },
            {
                'name': 'События',
                'description': 'Важные события, битвы, исторические моменты вселенной Ведьмака',
                'icon': '⚔️',
                'is_featured': True,
                'display_order': 5
            }
        ]

        created_count = 0
        updated_count = 0

        for category_data in default_categories:
            category, created = Category.objects.update_or_create(
                name=category_data['name'],
                defaults={
                    'description': category_data['description'],
                    'icon': category_data['icon'],
                    'is_featured': category_data['is_featured'],
                    'display_order': category_data['display_order']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Создана категория: {category.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'📝 Обновлена категория: {category.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Готово! Создано: {created_count}, Обновлено: {updated_count} категорий'
            )
        )