from django import template

register = template.Library()

@register.filter
def get_status_badge(status):
    status_map = {
        'draft': 'secondary',
        'review': 'warning',
        'needs_correction': 'info',
        'editor_review': 'primary',
        'author_review': 'warning',
        'published': 'success',
        'rejected': 'danger',
        'archived': 'dark'
    }
    return status_map.get(status, 'secondary')