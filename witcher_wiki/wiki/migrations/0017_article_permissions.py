from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0016_telegramuser'),  # Правильная зависимость!
    ]

    operations = [
        migrations.AlterModelOptions(
            name='article',
            options={
                'verbose_name': 'Статья',
                'verbose_name_plural': 'Статьи',
                'ordering': ['-created_at'],
                'permissions': [
                    ('can_create_articles', 'Может создавать статьи'),
                    ('can_edit_own_articles', 'Может редактировать свои статьи'),
                    ('can_edit_any_articles', 'Может редактировать любые статьи'),
                    ('can_moderate', 'Может модерировать статьи'),
                    ('can_manage_categories', 'Может управлять категориями'),
                    ('can_edit_content', 'Может редактировать контент'),
                    ('can_manage_media', 'Может управлять медиафайлами'),
                    ('can_delete_comments', 'Может удалять комментарии'),
                    ('can_view_moderation_queue', 'Может видеть очередь модерации'),
                    ('can_manage_users', 'Может управлять пользователями'),
                    ('can_access_admin', 'Доступ к админ-панели'),
                    ('can_view_logs', 'Может просматривать логи'),
                    ('can_backup_data', 'Может создавать бэкапы'),
                ],
            },
        ),
    ]