# wiki/management/commands/fix_slugs.py
import re
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from wiki.models import Article, Category


class Command(BaseCommand):
    help = 'Исправляет все slug с кириллицей на латиницу'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет исправлено без сохранения',
        )

    def transliterate_russian(self, text):
        """Транслитерация русских символов"""
        translit_dict = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }

        text = text.lower()
        for ru, en in translit_dict.items():
            text = text.replace(ru, en)

        # Удаляем все не-ASCII символы
        text = re.sub(r'[^\x00-\x7F]+', '', text)

        return text

    def fix_article_slugs(self, dry_run=False):
        """Исправляет все slug статей"""
        self.stdout.write("🔧 Исправление slug статей...")

        articles = Article.objects.all()
        fixed_count = 0
        problems = []

        for article in articles:
            original_slug = article.slug

            # Если slug содержит кириллицу, исправляем
            if re.search(r'[а-яА-Я]', original_slug):
                # Используем заголовок для создания нового slug
                new_slug_base = self.transliterate_russian(article.title)
                new_slug = slugify(new_slug_base)

                # Делаем slug уникальным
                counter = 1
                final_slug = new_slug
                while Article.objects.filter(slug=final_slug).exclude(id=article.id).exists():
                    final_slug = f"{new_slug}-{counter}"
                    counter += 1

                if not dry_run:
                    article.slug = final_slug
                    article.save()

                self.stdout.write(f"✅ {article.title}")
                self.stdout.write(f"   Старый: {original_slug}")
                self.stdout.write(f"   Новый: {final_slug}")
                self.stdout.write("")
                fixed_count += 1

                problems.append({
                    'type': 'article',
                    'id': article.id,
                    'title': article.title,
                    'old_slug': original_slug,
                    'new_slug': final_slug,
                })

        self.stdout.write(f"📊 Найдено {fixed_count} статей с кириллицей в slug")
        return problems

    def fix_category_slugs(self, dry_run=False):
        """Исправляет все slug категорий"""
        self.stdout.write("🔧 Исправление slug категорий...")

        categories = Category.objects.all()
        fixed_count = 0
        problems = []

        for category in categories:
            original_slug = category.slug

            # Если slug содержит кириллицу, исправляем
            if re.search(r'[а-яА-Я]', original_slug):
                new_slug_base = self.transliterate_russian(category.name)
                new_slug = slugify(new_slug_base)

                # Делаем slug уникальным
                counter = 1
                final_slug = new_slug
                while Category.objects.filter(slug=final_slug).exclude(id=category.id).exists():
                    final_slug = f"{new_slug}-{counter}"
                    counter += 1

                if not dry_run:
                    category.slug = final_slug
                    category.save()

                self.stdout.write(f"✅ {category.name}")
                self.stdout.write(f"   Старый: {original_slug}")
                self.stdout.write(f"   Новый: {final_slug}")
                self.stdout.write("")
                fixed_count += 1

                problems.append({
                    'type': 'category',
                    'id': category.id,
                    'name': category.name,
                    'old_slug': original_slug,
                    'new_slug': final_slug,
                })

        self.stdout.write(f"📊 Найдено {fixed_count} категорий с кириллицей в slug")
        return problems

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("🚨 РЕЖИМ ПРЕДПРОСМОТРА - изменения не будут сохранены!"))
            self.stdout.write("=" * 60)

        self.stdout.write("🚀 Начинаем исправление slug...")
        self.stdout.write("=" * 60)

        # Исправляем статьи
        article_problems = self.fix_article_slugs(dry_run)

        self.stdout.write("-" * 60)

        # Исправляем категории
        category_problems = self.fix_category_slugs(dry_run)

        self.stdout.write("=" * 60)

        # Сводка
        total_problems = len(article_problems) + len(category_problems)

        if total_problems == 0:
            self.stdout.write(self.style.SUCCESS("✅ Все slug уже в правильном формате!"))
        else:
            if dry_run:
                self.stdout.write(self.style.WARNING(f"⚠️  Будет исправлено {total_problems} slug:"))
                self.stdout.write(f"   - Статей: {len(article_problems)}")
                self.stdout.write(f"   - Категорий: {len(category_problems)}")
                self.stdout.write(self.style.WARNING("\nДля применения изменений запустите команду без --dry-run"))
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ Исправлено {total_problems} slug:"))
                self.stdout.write(f"   - Статей: {len(article_problems)}")
                self.stdout.write(f"   - Категорий: {len(category_problems)}")

        self.stdout.write("=" * 60)