# Модель даних (ER-модель)

## Опис сутностей та кардинальність
Модель даних розроблена для підтримки ключових функцій системи: реєстрації, бронювання кімнат, створення ігор та запису гравців.

1. **User (Користувач)**: Зберігає дані власників, майстрів та гравців. 
2. **Room (Кімната)**: Фізичні приміщення клубу.
3. **Game (Гра)**: Подія, створена Майстром, прив'язана до конкретної Кімнати та Часу.
4. **GameEnrollment (Запис на гру)**: Зв'язуюча таблиця (Many-to-Many) між Користувачами (гравцями) та Іграми.

## Чутливі дані (Sensitive Data)
Відповідно до вимог безпеки, наступні атрибути є чутливими і вимагають особливого захисту:
* `User.password_hash` – суворо конфіденційні дані (хеш пароля).
* `User.email` – персональні дані користувача.
* `User.contacts` – персональні контакти гравця, доступні лише йому та власнику клубу.

## ER-діаграма (PlantUML)
Діаграма відображає зв'язки типу "Один-до-Багатьох" (Майстер -> Ігри, Кімната -> Ігри) та "Багато-до-Багатьох" (через таблицю GameEnrollment).

```plantuml
@startuml
skinparam roundcorner 5
skinparam shadowing false

entity "User" as user {
  * id : INT <<PK>>
  --
  * email : VARCHAR <<Чутливі дані>>
  * password_hash : VARCHAR <<Чутливі дані>>
  * role : ENUM (Player, Master, Admin)
  contacts : VARCHAR <<Чутливі дані>>
  avatar_url : VARCHAR
}

entity "Room" as room {
  * id : INT <<PK>>
  --
  * name : VARCHAR
  capacity : INT
}

entity "Game" as game {
  * id : INT <<PK>>
  --
  * master_id : INT <<FK>>
  * room_id : INT <<FK>>
  * title : VARCHAR
  * start_time : DATETIME
  * duration_minutes : INT
  max_players : INT
}

entity "GameEnrollment" as enrollment {
  * id : INT <<PK>>
  --
  * game_id : INT <<FK>>
  * player_id : INT <<FK>>
  enrolled_at : DATETIME
}

user ||--o{ game : "Створює (як Майстер)"
room ||--o{ game : "Хостить"
user ||--o{ enrollment : "Бере участь (як Гравець)"
game ||--o{ enrollment : "Має гравців"

@enduml