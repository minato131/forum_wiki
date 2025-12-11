document.addEventListener('DOMContentLoaded', function() {
    // Обработка лайков комментариев
    document.querySelectorAll('.comment-like-btn').forEach(button => {
        button.addEventListener('click', function() {
            const commentId = this.dataset.commentId;
            const isLiked = this.dataset.liked === 'true';

            // Визуальная обратная связь
            this.classList.add('loading');

            // Отправляем запрос
            fetch(`/comment/${commentId}/like/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Обновляем состояние кнопки
                    this.dataset.liked = data.liked.toString();

                    if (data.liked) {
                        this.classList.add('liked');
                        this.innerHTML = `<i class="fas fa-thumbs-up"></i> <span class="comment-likes-count">${data.likes_count}</span>`;
                    } else {
                        this.classList.remove('liked');
                        this.innerHTML = `<i class="fas fa-thumbs-up"></i> <span class="comment-likes-count">${data.likes_count}</span>`;
                    }

                    // Показываем уведомление
                    showNotification(data.liked ? 'Лайк добавлен!' : 'Лайк убран!', 'success');
                } else {
                    showNotification('Ошибка: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Ошибка при отправке лайка', 'error');
            })
            .finally(() => {
                this.classList.remove('loading');
            });
        });
    });

    // Вспомогательная функция для получения CSRF токена
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Функция для показа уведомлений
    function showNotification(message, type = 'info') {
        // Реализация показа уведомлений (можно использовать Toast или alert)
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});