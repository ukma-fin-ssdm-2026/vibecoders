# Traceability Matrix

| Вимога   | Тип | Опис                                                                | Компонент(и) архітектури                                               |
|----------|-----|---------------------------------------------------------------------|------------------------------------------------------------------------|
| US-001   | FR  | Гравець записується на гру з вільним місцем                         | Web Client (HTMX), Game Management Service, Relational Database        |
| US-002   | FR  | Майстер перевіряє доступність і бронює кімнату                      | Web Client (HTMX), Room Booking Service, Relational Database           |
| US-003   | FR  | Власник сайту блокує кімнату                                        | Room Booking Service, Relational Database                              |
| US-004   | FR  | Власник сайту блокує користувача                                    | FastAPI Router / Auth Controller, Relational Database                  |
| US-005   | FR  | Гравець скасовує своє бронювання                                    | Game Management Service, Relational Database                           |
| US-006   | FR  | Гравець переглядає заплановані ігри                                 | Web Client (HTMX), Game Management Service                             |
| US-007   | FR  | Майстер бачить список учасників та наповненість гри                 | Game Management Service, Auth Controller, Relational Database          |
| US-008   | FR  | Майстер видаляє створену гру                                        | Game Management Service, Room Booking Service, Relational Database     |
| PERF-001 | NFR | Оновлення лічильника вільних місць < 1с                             | Web Client (HTMX), Game Management Service                             |
| REL-001  | NFR | Запобігання подвійному бронюванню кімнати при 20 одночасних спробах | Room Booking Service, Relational Database (ACID-транзакції)            |
| REL-002  | NFR | Заборона призначення майстра на дві гри, що перетинаються           | Game Management Service                                                |
| SEC-002  | NFR | Доступ до персональних даних лише гравцю та власнику                | FastAPI Router / Auth Controller (підтверджено: Pydantic response models фільтрують чутливі поля — див. threat-model.md, Information Disclosure) |
| SEC-004  | NFR | Відхилення реєстрації на email заблокованого профілю за ≤300мс      | FastAPI Router / Auth Controller, Relational Database                  |
| USAB-001 | NFR | Реєстрація + перша заявка за 3 хв                                   | Web Client (HTMX)                                                      |

## Використання ШІ

- Прив'язка вимог до компонентів архітектури (верифіковано переглядом: звірено з high-level-design.md та threat-model.md)
