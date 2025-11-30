// Умная система подсказок
class TutorialManager {
    constructor() {
        this.currentTutorial = null;
        this.init();
    }

    init() {
        // Показываем подсказки с задержкой после загрузки страницы
        setTimeout(() => {
            this.showRelevantTutorial();
        }, 1000);
    }

    showRelevantTutorial() {
        const path = window.location.pathname;

        // Определяем какую подсказку показывать в зависимости от страницы
        if (path === '/' && !window.userHasSeenWelcome) {
            this.showTutorial('welcome', '.navbar-brand', 'bottom');
        }
        else if (path.includes('/article/create') && !window.userHasSeenArticleCreate) {
            this.showTutorial('article_create', 'form', 'top');
        }
        else if (path.includes('/search') && !window.userHasSeenSearch) {
            this.showTutorial('search', 'input[name="q"]', 'bottom');
        }
        else if (path.includes('/accounts/profile') && !window.userHasSeenProfile) {
            this.showTutorial('profile', '.card', 'top');
        }
        else if (path.includes('/messages') && !window.userHasSeenMessages) {
            this.showTutorial('messages', '.nav-link.active', 'bottom');
        }
        else if (path.includes('/category') && !window.userHasSeenCategories) {
            this.showTutorial('categories', '.category-card:first-child', 'right');
        }
    }

    showTutorial(tutorialType, targetSelector, placement = 'top') {
        const tutorial = document.getElementById(tutorialType + 'Tutorial');
        const target = document.querySelector(targetSelector);

        if (!tutorial || !target) return;

        // Позиционируем подсказку рядом с целевым элементом
        this.positionTutorial(tutorial, target, placement);

        // Показываем подсказку
        tutorial.style.display = 'block';
        tutorial.setAttribute('data-placement', placement);

        this.currentTutorial = tutorialType;
    }

    positionTutorial(tutorial, target, placement) {
        const targetRect = target.getBoundingClientRect();
        const tutorialRect = tutorial.getBoundingClientRect();

        let top, left;

        switch (placement) {
            case 'top':
                top = targetRect.top - tutorialRect.height - 10;
                left = targetRect.left + (targetRect.width - tutorialRect.width) / 2;
                break;
            case 'bottom':
                top = targetRect.bottom + 10;
                left = targetRect.left + (targetRect.width - tutorialRect.width) / 2;
                break;
            case 'left':
                top = targetRect.top + (targetRect.height - tutorialRect.height) / 2;
                left = targetRect.left - tutorialRect.width - 10;
                break;
            case 'right':
                top = targetRect.top + (targetRect.height - tutorialRect.height) / 2;
                left = targetRect.right + 10;
                break;
        }

        // Корректируем позицию чтобы не выходить за границы экрана
        top = Math.max(10, Math.min(top, window.innerHeight - tutorialRect.height - 10));
        left = Math.max(10, Math.min(left, window.innerWidth - tutorialRect.width - 10));

        tutorial.style.top = top + 'px';
        tutorial.style.left = left + 'px';
    }

    closeTutorial(tutorialType) {
        const tutorial = document.getElementById(tutorialType + 'Tutorial');
        if (tutorial) {
            tutorial.style.display = 'none';
        }
        this.currentTutorial = null;
    }
}

// Глобальные функции для вызова из HTML
function markTutorialSeen(tutorialType) {
    fetch(`/tutorial/mark-seen/${tutorialType}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Закрываем текущую подсказку
            if (window.tutorialManager) {
                window.tutorialManager.closeTutorial(tutorialType);
            }
            // Показываем следующую подсказку если есть
            setTimeout(() => {
                if (window.tutorialManager) {
                    window.tutorialManager.showRelevantTutorial();
                }
            }, 500);
        }
    })
    .catch(error => {
        console.error('Error marking tutorial as seen:', error);
        if (window.tutorialManager) {
            window.tutorialManager.closeTutorial(tutorialType);
        }
    });
}

function disableAllTutorials() {
    if (confirm('Отключить все подсказки? Вы сможете включить их снова в настройках профиля.')) {
        window.location.href = '/tutorial/disable/';
    }
}

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

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (window.showTutorials) {
        window.tutorialManager = new TutorialManager();
    }
});