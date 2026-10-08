# ХАКЕРБАНК · Infrastructure notes

Practical notes by **ХАКЕРБАНК** ([BenkiNew](https://github.com/BenkiNew)) on Linux servers, monitoring, recovery, and self-hosted services.

These articles explain problems we encountered, the evidence used to investigate them, and the limits of the conclusions. Examples use fictional service names and data. Production configurations, private reports, and personal data are not included.

## Українською

Технічні нотатки **ХАКЕРБАНК** з експлуатації Linux-серверів: що сталося, як перевіряли, що змінили та чого перевірка не доводить.

### Статті

- [Як моніторинг помиляється: стара помилка, вимкнений сервіс і недоступна перевірка](articles/uk/monitoring-with-evidence.md)

### Наступні теми

Це план матеріалів, а не вже опубліковані інструкції:

- Автономний frontend: локальні ресурси та спільний пул без CDN.
- Резервування PostgreSQL: як перевіряти відновлення, а не лише створення backup.

## English

The first article is currently available in Ukrainian. It covers misleading monitoring signals: an old error presented as a current incident, an intentionally disabled job presented as healthy, and a failed probe reported as zero errors. It also explains why an inactive oneshot service can be normal and why a running process does not prove application health.

An English translation is planned. Questions and reports in either Ukrainian or English are welcome in [Discussions](https://github.com/BenkiNew/infra-notes/discussions).

## Обговорення та виправлення

Для запитань про матеріали використовуйте [Discussions](https://github.com/BenkiNew/infra-notes/discussions). Неточності у тексті можна повідомляти через [Issues](https://github.com/BenkiNew/infra-notes/issues) або виправляти через pull request.

Перед надсиланням прикладів приберіть токени, персональні дані, приватні адреси та вміст production-документів. Мінімальний відтворюваний приклад корисніший за повний журнал сервера.
