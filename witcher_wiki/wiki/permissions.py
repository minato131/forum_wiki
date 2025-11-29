# wiki/permissions.py - ОБНОВЛЯЕМ существующий файл

GROUP_PERMISSIONS = {
    'Пользователь': {
        'description': 'Обычный пользователь сайта',
        'permissions': [
            'Просмотр опубликованных статей',
            'Создание статей (требуют модерации)',
            'Редактирование своих статей в статусе черновика',
            'Комментирование статей',
            'Лайки статей',
            'Просмотр профилей других пользователей',
            'Отправка личных сообщений',
        ],
        # ДОБАВЛЯЕМ технические права для автоматической настройки
        'technical_permissions': {
            'article': ['view', 'add'],
            'comment': ['view', 'add'],
            'userprofile': ['view', 'change'],
            'articlelike': ['view', 'add', 'delete'],
            'message': ['view', 'add', 'delete'],
        },
        'custom_permissions': [
            'can_create_articles',
            'can_edit_own_articles',
        ]
    },
    'Редактор': {
        'description': 'Редактор контента',
        'permissions': [
            'Все права пользователя',
            'Редактирование любых статей',
            'Проверка и правка статей перед публикацией',
            'Отправка статей на согласование авторам',
            'Доступ к панели редактора',
        ],
        'technical_permissions': {
            'article': ['view', 'add', 'change', 'delete'],
            'comment': ['view', 'add', 'change', 'delete'],
            'userprofile': ['view', 'change'],
            'articlelike': ['view', 'add', 'delete'],
            'message': ['view', 'add', 'delete'],
            'articlemedia': ['view', 'add', 'change', 'delete'],
            'category': ['view'],
        },
        'custom_permissions': [
            'can_create_articles',
            'can_edit_own_articles',
            'can_edit_any_articles',
            'can_edit_content',
            'can_manage_media',
        ]
    },
    'Модератор': {
        'description': 'Модератор контента',
        'permissions': [
            'Все права редактора',
            'Модерация статей (одобрение/отклонение/отправка на доработку)',
            'Управление категориями',
            'Удаление комментариев',
            'Просмотр очереди модерации',
        ],
        'technical_permissions': {
            'article': ['view', 'add', 'change', 'delete'],
            'comment': ['view', 'add', 'change', 'delete'],
            'userprofile': ['view', 'change'],
            'articlelike': ['view', 'add', 'delete'],
            'message': ['view', 'add', 'delete'],
            'articlemedia': ['view', 'add', 'change', 'delete'],
            'category': ['view', 'add', 'change', 'delete'],
            'moderationcomment': ['view', 'add', 'change', 'delete'],
        },
        'custom_permissions': [
            'can_create_articles',
            'can_edit_own_articles',
            'can_edit_any_articles',
            'can_edit_content',
            'can_manage_media',
            'can_moderate',
            'can_manage_categories',
            'can_delete_comments',
            'can_view_moderation_queue',
        ]
    },
    'Администратор': {
        'description': 'Полный доступ к системе',
        'permissions': [
            'Все права модератора',
            'Управление пользователями',
            'Доступ к админ-панели Django',
            'Управление системными настройками',
            'Просмотр логов системы',
            'Создание резервных копий',
        ],
        'technical_permissions': {
            'article': ['view', 'add', 'change', 'delete'],
            'comment': ['view', 'add', 'change', 'delete'],
            'userprofile': ['view', 'add', 'change', 'delete'],
            'articlelike': ['view', 'add', 'change', 'delete'],
            'message': ['view', 'add', 'change', 'delete'],
            'articlemedia': ['view', 'add', 'change', 'delete'],
            'category': ['view', 'add', 'change', 'delete'],
            'moderationcomment': ['view', 'add', 'change', 'delete'],
            'articlerevision': ['view', 'add', 'change', 'delete'],
            'searchquery': ['view', 'add', 'change', 'delete'],
            'emailverification': ['view', 'add', 'change', 'delete'],
            'telegramuser': ['view', 'add', 'change', 'delete'],
            'authcode': ['view', 'add', 'change', 'delete'],
        },
        'custom_permissions': [
            'can_create_articles',
            'can_edit_own_articles',
            'can_edit_any_articles',
            'can_edit_content',
            'can_manage_media',
            'can_moderate',
            'can_manage_categories',
            'can_delete_comments',
            'can_view_moderation_queue',
            'can_manage_users',
            'can_access_admin',
            'can_view_logs',
            'can_backup_data',
        ]
    }
}