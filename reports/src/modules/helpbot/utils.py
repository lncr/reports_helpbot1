from telebot import types


def create_lang_inlines(language, user_lng):
    assert language in ['python', 'javascript']

    class_9 = types.InlineKeyboardButton(text='9 класс', callback_data=f'class_9_{language}')
    class_11 = types.InlineKeyboardButton(text='11 класс', callback_data=f'class_11_{language}')
    txt = 'Башкы  меню' if user_lng == 'kg' else 'Главное меню'
    main_menu = types.InlineKeyboardButton(text=txt, callback_data='main_menu')
    return [[class_9], [class_11], [main_menu]]
