### MyTaskBot
Проект представляет собой Telegram-бота для напоминаний о задачах. Бот написан на python с использованием библиотеки aiogram и базы данных PostgreSQL. Бот позволяет пользователям добавлять, редактировать, удалять и просматривать задачи с напоминаниями, настроенными на определенное время. Также бот поддерживает повторяющиеся напоминания. Бот использует английский язык.

https://t.me/mytasksalert_bot

#### Основные функции:
1. Добавление задач:
    - Пользователь вводит название задачи.
    - Пользователь выбирает дату напоминания через кнопки (сегодня, завтра, дни недели и т.д.).
    - Пользователь указывает время напоминания.
    - Пользователь может установить повторение задачи (ежедневно, еженедельно, ежемесячно, ежегодно).
2. Редактирование задач:
    - Пользователь выбирает задачу из списка для редактирования.
    - Редактирование проходит по тем же этапам, что и добавление новой задачи.
3. Удаление задач:
    - Пользователь выбирает задачу из списка для удаления.
4. Просмотр задач:
    - Все задачи пользователя отображаются в виде пронумерованного списка, отсортированного по дате и времени напоминания.
5. Напоминания:
    - Бот периодически проверяет задачи и отправляет пользователю напоминания о предстоящих задачах.
  
#### SQL запрос для реализации таблицы базы данных
```
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    task TEXT NOT NULL,
    remind_at TIMESTAMP NOT NULL,
    repeat_interval VARCHAR(20) DEFAULT 'no_repeat'
);
```

