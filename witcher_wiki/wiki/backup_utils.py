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

            # 1. База данных SQLite
            db_path = settings.DATABASES['default']['NAME']
            if db_path and os.path.exists(db_path) and backup_type in ['full', 'database']:
                zipf.write(db_path, 'database.sqlite3')
                print(f"✓ Добавлена база данных: {db_path}")

            # 2. Медиафайлы
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

            # 3. Статические файлы (только для полного бэкапа)
            if backup_type == 'full':
                static_dir = settings.STATIC_ROOT or os.path.join(settings.BASE_DIR, 'static')
                if os.path.exists(static_dir):
                    static_files_added = 0
                    for root, dirs, files in os.walk(static_dir):
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, settings.BASE_DIR)
                                zipf.write(file_path, arcname)
                                static_files_added += 1
                            except:
                                pass

                    print(f"✓ Добавлено статических файлов: {static_files_added}")

            # 4. Метаданные
            metadata = {
                'backup_name': backup_name,
                'backup_type': backup_type,
                'created_at': timezone.now().isoformat(),
                'django_version': getattr(settings, 'VERSION', '1.0'),
                'database_engine': settings.DATABASES['default']['ENGINE'],
                'description': description,
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


def restore_backup(backup_id):
    """Восстановление из резервной копии (только для админов)"""
    try:
        backup = Backup.objects.get(id=backup_id)

        if backup.status != 'completed' or not os.path.exists(backup.file_path):
            raise Exception("Бэкап не найден или недоступен")

        print(f"⚠️ ВНИМАНИЕ: Начато восстановление из бэкапа {backup.name}")
        print("Эта операция перезапишет текущую базу данных!")
        print("Для продолжения обратитесь к системному администратору.")

        # В реальном проекте здесь была бы логика восстановления
        # Для безопасности только возвращаем информацию о бэкапе
        return {
            'success': False,
            'message': 'Восстановление требует ручного вмешательства администратора',
            'backup': backup,
            'requires_admin': True
        }

    except Backup.DoesNotExist:
        raise Exception("Бэкап не найден")
    except Exception as e:
        raise e