# wiki/backup_utils.py
import os
import json
import zipfile
import shutil
from django.conf import settings
from django.utils import timezone
from .models import Backup
from datetime import datetime, timedelta


def create_backup(backup_type='full', description=''):
    """Создание резервной копии"""

    try:
        # Создаем запись о бэкапе
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{backup_type}_backup_{timestamp}"

        backup = Backup.objects.create(
            name=backup_name,
            file_path='',  # Будет установлен после создания
            backup_type=backup_type,
            status='in_progress',
            description=description
        )

        # Пути для бэкапов
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        backup_path = os.path.join(backup_dir, f"{backup_name}.zip")

        # Создаем архив
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:

            # База данных SQLite
            db_path = settings.DATABASES['default']['NAME']
            if not os.path.isabs(db_path):
                db_path = os.path.join(settings.BASE_DIR, db_path)

            if db_path and os.path.exists(db_path) and backup_type in ['full', 'database']:
                zipf.write(db_path, 'database.sqlite3')
                print(f"✓ Добавлена база данных: {db_path}")

            # Медиафайлы
            if backup_type in ['full', 'media']:
                media_dir = settings.MEDIA_ROOT
                if os.path.exists(media_dir):
                    media_files_added = 0
                    for root, dirs, files in os.walk(media_dir):
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                # Пропускаем слишком большие файлы (> 50MB)
                                if os.path.getsize(file_path) > 50 * 1024 * 1024:
                                    continue
                                arcname = os.path.relpath(file_path, settings.BASE_DIR)
                                zipf.write(file_path, arcname)
                                media_files_added += 1
                            except Exception as e:
                                print(f"⚠️ Ошибка добавления файла {file}: {e}")

                    print(f"✓ Добавлено медиафайлов: {media_files_added}")

            # Метаданные
            metadata = {
                'backup_name': backup_name,
                'backup_type': backup_type,
                'created_at': timezone.now().isoformat(),
                'description': description,
                'database_engine': settings.DATABASES['default']['ENGINE'],
                'system_info': {
                    'python_version': os.sys.version,
                    'platform': os.sys.platform,
                }
            }

            zipf.writestr('metadata.json', json.dumps(metadata, indent=2, ensure_ascii=False))

        # Обновляем запись бэкапа
        backup.file_path = backup_path
        backup.file_size = os.path.getsize(backup_path)
        backup.status = 'completed'
        backup.metadata = metadata
        backup.save()

        print(f"✅ Бэкап создан: {backup_name} ({backup.file_size_display()})")

        # Очищаем старые бэкапы (больше 30 дней)
        cleanup_old_backups(backup_dir, days=30)

        return backup

    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {str(e)}")
        # В случае ошибки обновляем статус
        if 'backup' in locals():
            backup.status = 'failed'
            backup.save(update_fields=['status'])
        raise e


def cleanup_old_backups(backup_dir, days=30):
    """Удаление старых бэкапов"""
    cutoff_date = timezone.now() - timedelta(days=days)

    for filename in os.listdir(backup_dir):
        if filename.endswith('.zip'):
            file_path = os.path.join(backup_dir, filename)

            try:
                # Получаем дату создания файла
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                file_time = timezone.make_aware(file_time)

                if file_time < cutoff_date:
                    os.remove(file_path)

                    # Удаляем запись из базы данных если есть
                    backup_name = filename.replace('.zip', '')
                    Backup.objects.filter(name=backup_name).delete()

                    print(f"🗑️ Удален старый бэкап: {filename}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении {filename}: {str(e)}")


def create_date_specific_backup(date_str, backup_type='full', description=''):
    """Создает бэкап за конкретную дату"""
    from .models import Article

    try:
        # Парсим дату
        backup_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Создаем запись о бэкапе
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"date_{backup_date}_{backup_type}_backup_{timestamp}"

        backup = Backup.objects.create(
            name=backup_name,
            file_path='',
            backup_type=backup_type,
            status='in_progress',
            description=f"{description} (за {backup_date})"
        )

        # Пути для бэкапов
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        backup_path = os.path.join(backup_dir, f"{backup_name}.zip")

        # Создаем архив
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:

            # Экспорт статей за конкретную дату
            articles = Article.objects.filter(created_at__date=backup_date)

            articles_data = []
            for article in articles:
                articles_data.append({
                    'id': article.id,
                    'title': article.title,
                    'slug': article.slug,
                    'content': article.content,
                    'author': article.author.username,
                    'created_at': article.created_at.isoformat(),
                    'status': article.status,
                    'categories': [cat.name for cat in article.categories.all()],
                    'tags': [tag.name for tag in article.tags.all()],
                })

            # Добавляем JSON с данными статей
            json_filename = f'articles_{backup_date}.json'
            zipf.writestr(json_filename, json.dumps(articles_data, indent=2, ensure_ascii=False))

            # Полный бэкап базы данных
            if backup_type == 'full':
                db_path = settings.DATABASES['default']['NAME']
                if not os.path.isabs(db_path):
                    db_path = os.path.join(settings.BASE_DIR, db_path)

                if os.path.exists(db_path):
                    zipf.write(db_path, 'database.sqlite3')

            # Метаданные
            metadata = {
                'backup_name': backup_name,
                'backup_type': backup_type,
                'backup_date': str(backup_date),
                'created_at': timezone.now().isoformat(),
                'description': description,
                'article_count': len(articles_data),
                'date_specific': True,
            }

            zipf.writestr('metadata.json', json.dumps(metadata, indent=2, ensure_ascii=False))

        # Обновляем запись бэкапа
        backup.file_path = backup_path
        backup.file_size = os.path.getsize(backup_path)
        backup.status = 'completed'
        backup.metadata = metadata
        backup.save()

        return backup

    except Exception as e:
        if 'backup' in locals():
            backup.status = 'failed'
            backup.save()
        raise e