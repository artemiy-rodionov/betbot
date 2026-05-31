CHECK_RESULTS_BUTTON = "Посмотреть ставки"
RESULTS_TITLE = "Ставки сделаны, ставок больше нет. Начинается матч %s."
RESULTS_TABLE = "Таблица результатов [доступна по ссылке](%s) или жми /scores."
PRESS_BET = "Жми /bet, чтобы сделать новую ставку или изменить существующую."
MY_BETS = "/mybets, чтобы посмотреть свои ставки."
SETTINGS_HELP = (
    "/setname <имя> — изменить отображаемое имя. /timezone — настроить часовой пояс."
)
HELP_MSG = PRESS_BET + " " + MY_BETS + " " + RESULTS_TABLE + "\n" + SETTINGS_HELP
START_MSG = "Привет, %s! Поздравляю, ты в игре!\n"
SEND_PRIVATE_MSG = "Tcccc, не пали контору. Напиши мне личное сообщение"
NAVIGATION_ERROR = (
    "Сорян, что-то пошло не так в строке %d. Попробуй еще раз.\n" + HELP_MSG
)
NO_MATCHES_MSG = "Уже не на что ставить =("
SCORE_REQUEST = "Сколько голов забьет %s%s?"
PENALTY_WINNER_REQUEST = "Кто победит по пенальти?"
EXTRA_WINNER_REQUEST = "Кто победит в дополнительное время или по пенальти?"
TOO_LATE_MSG = (
    "Уже поздно ставить на этот матч. Попробуй поставить на другой.\n" + HELP_MSG
)
CONFIRMATION_MSG = (
    "Ставка %s сделана %s. Начало матча %s по Москве. Удачи, %s!\n" + HELP_MSG
)
NO_BETS_MSG = "Ты еще не сделал(а) ни одной ставки. " + PRESS_BET
CHOOSE_MATCH_TITLE = "Выбери матч"
LEFT_ARROW = "\u2b05"
RIGHT_ARROW = "\u27a1"
NOT_REGISTERED = (
    "Ты пока не зарегистрирован(а). "
    "Нажми кнопку ниже, чтобы запросить доступ, "
    "и {admin_name} подтвердит тебя."
)

# Self-serve gated signup (admin approval queue)
REQUEST_ACCESS_BUTTON = "Запросить доступ"
APPROVE_BUTTON = "✅ Одобрить"
REJECT_BUTTON = "❌ Отклонить"
REQUEST_RECEIVED = "Заявка отправлена! Жди — администратор скоро её рассмотрит."
REQUEST_PENDING = "Твоя заявка уже на рассмотрении. Немного терпения 🙂"
NEW_REQUEST_ADMIN = (
    "🔔 Новая заявка на доступ:\n%s%s (id: %s)"  # name, " @username" or "", id
)
REQUEST_APPROVED_ADMIN = "✅ Доступ выдан: %s"
REQUEST_REJECTED_ADMIN = "❌ Заявка отклонена: %s"
REQUEST_STALE_ADMIN = "Эта заявка уже обработана или отозвана."
PENDING_LIST_HEADER = "📋 Заявки на доступ (%d):"
PENDING_LIST_EMPTY = "Заявок на доступ нет."
PENDING_LIST_ITEM = "%s%s (id: %s) — %s"  # name, " @username" or "", id, requested_at
REQUEST_APPROVED_USER = "Тебя одобрили! Добро пожаловать в игру 🎉\n"
REQUEST_REJECTED_USER = (
    "Увы, заявка на доступ отклонена. Если это ошибка — напиши {admin_name}."
)

# Self-serve name change
NAME_USAGE = 'Чтобы сменить имя, напиши "/setname <новое имя>".\nТекущее имя: %s'
NAME_CHANGED = "Готово! Теперь тебя зовут %s."
NAME_TOO_LONG = "Слишком длинное имя. Максимум %d символов."
NAME_EMPTY = "Имя не может быть пустым."
ALREADY_REGISTERED = "%s (%s) уже зарегистрирован(а)."
REGISTER_SHOULD_BE_REPLY = "Сообщение о регистрации должно быть ответом."
REGISTER_SHOULD_BE_REPLY_TO_FORWARD = (
    "Сообщение о регистрации должно быть ответом на форвард."
)
REGISTRATION_SUCCESS = "%s aka %s (%s) успешно зарегистрирован."
ERROR_MESSAGE_ABSENT = "Этот виджет сломан, вызови /bet снова."
USER_NOT_REGISTERED = "Пользователь не зарегистрирован."
SUCCESS = "Успех."
FAILURE = "Не получилось("
REMIND_MSG = "Уж встреча близится, а ставочки все нет."
REMIND_DAY_MSG = "Матч начнется через сутки. Можно и ставку закинуть."
ADMIN_HELP_MSG = (
    "\nAdmin commands:\n"
    "/pendingRequests - показать заявки на доступ (с кнопками одобрить/отклонить)\n"
    "/register - Регистрация пользователя"
    "(ввести в ответ на форвард сообщения от пользователя)\n"
    "/makeQueen - сделать олигархом(как выше)\n"
    "/unmakeQueen - разжаловать(как выше)\n"
    "/registerAdmin - зарегать себя\n"
    "/registerBot [name] - создать 1-0 бота (только один разрешен)\n"
    "/listBots - показать всех зарегистрированных ботов\n"
    "/removeBot - удалить 1-0 бота и все его ставки\n"
    "/updateFixtures - обновить данные из АПИ(не использовать очень часто)\n"
    "/finalScores - вывести полную таблицу с аналитикой\n"
    "/chartRace - отправить видео в группе(предварительно надо вручную сгенерить)\n"
    "/sendLast - отправить ставки в группу по последним матчам\n"
)

TIMEZONE_MSG = 'Текущий часовой пояс "{tz}"'
TIMEZONE_HELP_MSG = (
    'Вводи команду в формате "/timezone <имя часового пояса>"\n'
    "Часовые пояса можно найти по [ссылке](https://timezonedb.com/time-zones)"
)
