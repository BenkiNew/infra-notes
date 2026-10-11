# BenkiNew · Infrastructure notes

Practical notes by **[BenkiNew](https://github.com/BenkiNew)** on Linux servers, monitoring, recovery, and self-hosted services.

These articles explain problems we encountered, the evidence used to investigate them, and the limits of the conclusions. Examples use fictional service names and data. Production configurations, private reports, and personal data are not included.

## Українською

Технічні матеріали **[BenkiNew](https://github.com/BenkiNew)** з експлуатації Linux-серверів, моніторингу та відновлення сервісів.

Пишу про експлуатацію Linux-серверів: що сталося, як перевіряли, що змінили та чого перевірка не доводить. [Профіль автора на DOU](https://dou.ua/users/kostyantin-bank/).

### Статті

- [Як моніторинг помиляється: стара помилка, вимкнений сервіс і недоступна перевірка](articles/uk/monitoring-with-evidence.md) — [публікація на DOU, 10.10.2026](https://dou.ua/forums/topic/62492/).
- [Синхронізація успішна, дані застарілі: як Bash і systemd приховали збій після переносу](articles/uk/bash-errexit-hidden-failure.md) — технічний розбір Bash `errexit` і systemd `ReadWritePaths`; [першоджерело та скрипти у Gist](https://gist.github.com/BenkiNew/03f6f203f6709b8102b2e47b7b899d02), [стаття на його основі на DOU, 11.10.2026](https://dou.ua/forums/topic/62516/).

### Наступні теми

Це план матеріалів, а не вже опубліковані інструкції:

- Автономний frontend: локальні ресурси та спільний пул без CDN.
- Резервування PostgreSQL: як перевіряти відновлення, а не лише створення backup.

## English

Related Ukrainian articles on DOU: [monitoring with evidence, 10.10.2026](https://dou.ua/forums/topic/62492/) and [sync succeeded, data went stale, 11.10.2026](https://dou.ua/forums/topic/62516/). The Bash/systemd article is based on the original GitHub material; this repository maintains the technical explanations, examples, and clarifications.

The monitoring article is currently available in Ukrainian only. It covers misleading monitoring signals: an old error presented as a current incident, an intentionally disabled job presented as healthy, and a failed probe reported as zero errors. It also explains why an inactive oneshot service can be normal and why a running process does not prove application health. An English translation is planned.

- [Sync succeeded, data went stale: how Bash and systemd hid a failure after a move](articles/en/bash-errexit-hidden-failure.md) — Bash `errexit`, systemd filesystem restrictions, and synthetic reproduction scripts; [original Gist](https://gist.github.com/BenkiNew/03f6f203f6709b8102b2e47b7b899d02).

Questions and reports in either Ukrainian or English are welcome in [Discussions](https://github.com/BenkiNew/infra-notes/discussions).

## Обговорення та виправлення

Для запитань про матеріали використовуйте [Discussions](https://github.com/BenkiNew/infra-notes/discussions). Неточності у тексті можна повідомляти через [Issues](https://github.com/BenkiNew/infra-notes/issues) або виправляти через pull request.

Перед надсиланням прикладів приберіть токени, персональні дані, приватні адреси та вміст production-документів. Мінімальний відтворюваний приклад корисніший за повний журнал сервера.
