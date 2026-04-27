class ElementType():
    TEXT = 'TEXT'
    USER_MENTION = 'USER_MENTION'
    LINK = 'LINK'
    ANIMOJI = 'ANIMOJI'

class MessageType():
    USER = 'USER'
    SYSTEM = 'SYSTEM'
    SERVICE = 'SERVICE'

class MessageLinkType():
    REPLY = 'REPLY'

class MessageStatus():
    REMOVED = 'REMOVED'

class ChatType(str):
    DIALOG = 'DIALOG'
    CHAT = 'CHAT'
    CHANNEL = 'CHANNEL'

class AccessType(str):
    PUBLIC = 'PUBLIC'
    PRIVATE = 'PRIVATE'
    SECRET = 'SECRET'

class ChatActions():
    TYPING = 'TYPING'
    FILE = 'FILE'
    STICKER = 'STICKER'

class ContactActions():
    ADD = 'ADD'
    REMOVE = 'REMOVE'
    BLOCK = 'BLOCK'
    UNBLOCK = 'UNBLOCK'

class Constants():
    PHONE_REGEX = r'^\+?\d{10,15}$'

class Opcode():
    PING = 1
    NAVIGATION = 5
    INIT = 6
    CHANGE_PROFILE_DATA = 16
    AUTH_REQUEST = 17
    AUTH = 18
    LOGIN = 19
    LOG_OUT = 20
    CONTACT_INFO = 32
    CONTACT_UPDATE = 34
    CHAT_DELETE = 52
    CHAT_HISTORY = 49
    SEND_MESSAGE = 64
    DELETE_MESSAGE = 66
    EDIT_MESSAGE = 67
    CHAT_MEMBERS_UPDATE = 77
    VIDEO_PLAY = 83
    FILE_DOWNLOAD = 88
    SESSIONS_CLOSE = 97
    NOTIF_MESSAGE = 128
    NOTIF_CHAT_ACTION = 129

# Rate limits (requests per second)
RATE_LIMITS = {
    Opcode.SEND_MESSAGE: 15.0,            # отправка сообщений, файлов, контактов
    Opcode.EDIT_MESSAGE: 15.0,            # редактирование сообщений
    Opcode.CHAT_HISTORY: 0.5,             # получение истории (1 запрос в 2 сек)
    Opcode.CHAT_MEMBERS_UPDATE: 0.5,      # удаление участников, назначение админа
    Opcode.CONTACT_INFO: 0.5,             # получение контактов
    # при необходимости можно добавить другие опкоды
}
DEFAULT_RATE_LIMIT = 20.0