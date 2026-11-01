from __future__ import annotations

import html
import json
import re
from string import Template
from urllib.parse import quote

from app.config import settings
from app.services.llm import chat_completion

ACCENTS = {
    "Бьюти": "rose",
    "Рестораны": "amber",
    "Автосервисы": "cyan",
    "Медицина": "emerald",
    "Фитнес": "lime",
    "Отели": "sky",
    "Услуги": "violet",
    "Магазины": "fuchsia",
}

CITY_PREPOSITIONAL = {
    "Москва": "Москве",
    "Санкт-Петербург": "Санкт-Петербурге",
    "Новосибирск": "Новосибирске",
    "Екатеринбург": "Екатеринбурге",
    "Казань": "Казани",
    "Нижний Новгород": "Нижнем Новгороде",
    "Челябинск": "Челябинске",
    "Красноярск": "Красноярске",
    "Самара": "Самаре",
    "Уфа": "Уфе",
    "Ростов-на-Дону": "Ростове-на-Дону",
    "Краснодар": "Краснодаре",
    "Омск": "Омске",
    "Воронеж": "Воронеже",
    "Пермь": "Перми",
    "Волгоград": "Волгограде",
    "Саратов": "Саратове",
    "Тюмень": "Тюмени",
    "Тольятти": "Тольятти",
    "Барнаул": "Барнауле",
    "Ижевск": "Ижевске",
    "Махачкала": "Махачкале",
    "Хабаровск": "Хабаровске",
    "Ульяновск": "Ульяновске",
    "Иркутск": "Иркутске",
    "Владивосток": "Владивостоке",
    "Ярославль": "Ярославле",
    "Кемерово": "Кемерове",
    "Томск": "Томске",
    "Набережные Челны": "Набережных Челнах",
    "Севастополь": "Севастополе",
    "Ставрополь": "Ставрополе",
    "Оренбург": "Оренбурге",
    "Новокузнецк": "Новокузнецке",
    "Рязань": "Рязани",
    "Балашиха": "Балашихе",
    "Пенза": "Пензе",
    "Чебоксары": "Чебоксарах",
    "Липецк": "Липецке",
    "Калининград": "Калининграде",
    "Астрахань": "Астрахани",
    "Тула": "Туле",
    "Киров": "Кирове",
    "Сочи": "Сочи",
    "Курск": "Курске",
    "Улан-Удэ": "Улан-Удэ",
    "Сургут": "Сургуте",
    "Тверь": "Твери",
    "Магнитогорск": "Магнитогорске",
    "Иваново": "Иваново",
    "Брянск": "Брянске",
    "Белгород": "Белгороде",
    "Владимир": "Владимире",
    "Чита": "Чите",
    "Архангельск": "Архангельске",
    "Калуга": "Калуге",
    "Смоленск": "Смоленске",
    "Саранск": "Саранске",
    "Череповец": "Череповце",
    "Курган": "Кургане",
    "Вологда": "Вологде",
    "Орёл": "Орле",
    "Владикавказ": "Владикавказе",
    "Подольск": "Подольске",
    "Грозный": "Грозном",
    "Мурманск": "Мурманске",
    "Тамбов": "Тамбове",
    "Петрозаводск": "Петрозаводске",
    "Стерлитамак": "Стерлитамаке",
    "Кострома": "Костроме",
    "Нижневартовск": "Нижневартовске",
    "Новороссийск": "Новороссийске",
    "Йошкар-Ола": "Йошкар-Оле",
    "Таганрог": "Таганроге",
    "Сыктывкар": "Сыктывкаре",
    "Нальчик": "Нальчике",
    "Шахты": "Шахтах",
    "Дзержинск": "Дзержинске",
    "Благовещенск": "Благовещенске",
    "Великий Новгород": "Великом Новгороде",
    "Псков": "Пскове",
    "Симферополь": "Симферополе",
    "Якутск": "Якутске",
}

BUSINESS_NOUNS = {
    "Бьюти": "студия красоты",
    "Рестораны": "ресторан",
    "Автосервисы": "автосервис",
    "Медицина": "клиника",
    "Фитнес": "фитнес-клуб",
    "Отели": "отель",
    "Услуги": "компания",
    "Магазины": "магазин",
}

BUSINESS_PLURAL_GENITIVE = {
    "Бьюти": "салонов красоты и студий",
    "Рестораны": "ресторанов и кафе",
    "Автосервисы": "автосервисов и СТО",
    "Медицина": "клиник и медцентров",
    "Фитнес": "фитнес-клубов и студий",
    "Отели": "отелей и гостиниц",
    "Услуги": "компаний сферы услуг",
    "Магазины": "магазинов",
}

PROFILES: dict[str, dict] = {
    "Бьюти": {
        "tagline": "Красота, к которой хочется возвращаться",
        "subtitle": "Онлайн-запись за 30 секунд — без звонков и ожидания",
        "services": [
            ("Маникюр + гель-лак", "от 2 500 ₽", "Стойкое покрытие до 4 недель, дизайн в подарок"),
            ("Педикюр", "от 3 200 ₽", "Аппаратная обработка, уход и покрытие"),
            ("Брови и ресницы", "от 1 900 ₽", "Коррекция, окрашивание, ламинирование"),
            ("Стрижка и укладка", "от 2 800 ₽", "Под ваш тип лица и образ жизни"),
        ],
        "benefits": [
            ("Запись 24/7", "Выберите удобное время онлайн — мы подтвердим за пару минут"),
            ("Опытные мастера", "Средний стаж команды — более 5 лет"),
            ("Стерильность", "Инструменты проходят трёхэтапную обработку"),
            ("Комфорт", "Кофе, музыка и никакой спешки"),
        ],
        "reviews": [
            ("Анна К.", "Делала маникюр — держится уже месяц, идеально. Записалась онлайн за минуту!"),
            ("Мария С.", "Лучшие брови в городе. Мастер услышала все пожелания, результат превзошёл ожидания."),
            ("Екатерина В.", "Уютно, чисто, приятные цены. Теперь только сюда."),
        ],
    },
    "Рестораны": {
        "tagline": "Вкус, который хочется повторить",
        "subtitle": "Забронируйте столик онлайн — без звонков и ожидания на линии",
        "services": [
            ("Бизнес-ланч", "590 ₽", "Салат, суп, горячее и напиток каждый будний день"),
            ("Завтраки весь день", "от 450 ₽", "Сырники, омлеты, каши и свежая выпечка"),
            ("Паста и ризотто", "от 690 ₽", "Готовим из свежих продуктов на ваших глазах"),
            ("Десерты", "от 390 ₽", "Собственная кондитерская и сезонные новинки"),
        ],
        "benefits": [
            ("Бронь онлайн", "Выберите дату и время — столик будет ждать"),
            ("Свежие продукты", "Поставки от локальных фермеров каждое утро"),
            ("Для всей семьи", "Детское меню и игровая зона"),
            ("Быстрая подача", "Среднее время ожидания горячего — 12 минут"),
        ],
        "reviews": [
            ("Дмитрий П.", "Бизнес-ланч — огонь. Порции большие, всё свежее, персонал внимательный."),
            ("Ольга Р.", "Отмечали день рождения, помогли с организацией. Гости в восторге!"),
            ("Иван Т.", "Лучшая паста в городе. Теперь бронирую столик только онлайн."),
        ],
    },
    "Автосервисы": {
        "tagline": "Ремонт без сюрпризов в счёте",
        "subtitle": "Запишитесь онлайн — назовём точную стоимость до начала работ",
        "services": [
            ("Компьютерная диагностика", "от 1 500 ₽", "Полная проверка всех систем автомобиля"),
            ("Замена масла", "от 2 900 ₽", "Работа + оригинальные расходники"),
            ("Шиномонтаж", "от 2 500 ₽", "Балансировка и сезонное хранение шин"),
            ("Кузовной ремонт", "по запросу", "Покраска и восстановление геометрии"),
        ],
        "benefits": [
            ("Гарантия", "До 24 месяцев на все виды работ"),
            ("Честная смета", "Согласуем каждую позицию до ремонта"),
            ("Оригинальные запчасти", "Или качественные аналоги — на ваш выбор"),
            ("Работаем 7 дней", "Без выходных с 8:00 до 21:00"),
        ],
        "reviews": [
            ("Сергей М.", "Сделали диагностику за час, назвали точную цену. Никаких сюрпризов."),
            ("Алексей К.", "Записался онлайн, приехал — машину уже ждали. Всё быстро и качественно."),
            ("Роман Д.", "Доверяю им обе машины в семье. Ни разу не подвели."),
        ],
    },
    "Медицина": {
        "tagline": "Забота о здоровье без очередей",
        "subtitle": "Запишитесь к врачу онлайн — свободное время видно сразу",
        "services": [
            ("Консультация врача", "от 2 500 ₽", "Первичный приём и план лечения"),
            ("Гигиена полости рта", "от 4 900 ₽", "Ультразвуковая чистка и полировка"),
            ("Лечение кариеса", "от 6 500 ₽", "Без боли, с современной анестезией"),
            ("Имплантация", "от 35 000 ₽", "Импланты с пожизненной гарантией"),
        ],
        "benefits": [
            ("Лицензированная клиника", "Все врачи с профильным образованием"),
            ("Онлайн-запись", "Выбирайте врача и время сами"),
            ("Без боли", "Современная анестезия и седация"),
            ("Напоминания", "Пришлём сообщение о приёме заранее"),
        ],
        "reviews": [
            ("Наталья И.", "Боялась стоматологов, но здесь всё прошло спокойно и без боли. Спасибо!"),
            ("Павел Г.", "Записался онлайн за 2 минуты, приняли точно по времени."),
            ("Юлия А.", "Внимательный персонал, чисто, современное оборудование."),
        ],
    },
    "Фитнес": {
        "tagline": "Тело, в котором вам комфортно",
        "subtitle": "Первая тренировка бесплатно — запишитесь онлайн за минуту",
        "services": [
            ("Персональная тренировка", "от 2 500 ₽", "Программа под ваши цели и уровень"),
            ("Групповые занятия", "от 900 ₽", "Йога, стретчинг, HIIT и силовые"),
            ("Абонемент на месяц", "от 4 900 ₽", "Неограниченное количество посещений"),
            ("Онлайн-тренировки", "от 1 200 ₽", "Тренируйтесь из дома с тренером"),
        ],
        "benefits": [
            ("Пробная тренировка", "Бесплатно, чтобы познакомиться с клубом"),
            ("Опытные тренеры", "Сертифицированные специалисты"),
            ("Удобный график", "Занятия с 7:00 до 23:00"),
            ("Без навязывания", "Никаких скрытых платежей"),
        ],
        "reviews": [
            ("Артём В.", "За полгода минус 12 кг. Тренер составил программу и следит за техникой."),
            ("Ксения Л.", "Хожу на йогу и стретчинг. Атмосфера супер, инструкторы внимательные."),
            ("Максим Ш.", "Удобно, что можно записаться онлайн и не ждать звонка."),
        ],
    },
    "Отели": {
        "tagline": "Дом вдали от дома",
        "subtitle": "Забронируйте номер онлайн — подтверждение придёт сразу",
        "services": [
            ("Стандарт", "от 4 900 ₽ / ночь", "Уютный номер со всеми удобствами"),
            ("Люкс", "от 9 800 ₽ / ночь", "Просторный номер с видом на город"),
            ("Завтрак", "включён", "Шведский стол с 7:00 до 11:00"),
            ("Ранний заезд", "по запросу", "Заселение с 8:00 при наличии номеров"),
        ],
        "benefits": [
            ("Бронь за минуту", "Онлайн-подтверждение на почту и в мессенджер"),
            ("Центр города", "До главных достопримечательностей — пешком"),
            ("Чистота", "Ежедневная уборка и свежее бельё"),
            ("Поддержка 24/7", "На связи в любое время"),
        ],
        "reviews": [
            ("Ирина С.", "Останавливались на выходные. Чисто, тихо, завтраки отличные."),
            ("Виктор Н.", "Удобное расположение, приветливый персонал. Бронь подтвердили мгновенно."),
            ("Алина Ж.", "Номер светлый, вид красивый. Обязательно вернёмся."),
        ],
    },
    "Услуги": {
        "tagline": "Делаем то, что нужно, вовремя",
        "subtitle": "Оставьте заявку онлайн — мастер приедет в удобное время",
        "services": [
            ("Консультация", "бесплатно", "Оценим объём работ и назовём цену"),
            ("Выезд мастера", "от 1 500 ₽", "Приедем в удобное для вас время"),
            ("Базовые работы", "от 2 500 ₽", "Качественно и с гарантией"),
            ("Срочный заказ", "+30% к стоимости", "Выполним в течение 24 часов"),
        ],
        "benefits": [
            ("Фиксированная цена", "Смета до начала работ"),
            ("Гарантия", "На все выполненные работы"),
            ("Онлайн-заявка", "Ответим в течение 15 минут"),
            ("Удобная оплата", "Наличные, карта, перевод"),
        ],
        "reviews": [
            ("Олег Б.", "Приехали в день обращения, всё сделали аккуратно и по обещанной цене."),
            ("Татьяна Е.", "Оставила заявку онлайн — перезвонили через 10 минут. Очень удобно."),
            ("Григорий Ф.", "Работой доволен, рекомендую друзьям."),
        ],
    },
    "Магазины": {
        "tagline": "Вещи, которые хочется носить",
        "subtitle": "Закажите онлайн — привезём в день обращения",
        "services": [
            ("Новинки сезона", "от 2 900 ₽", "Свежие коллекции каждую неделю"),
            ("Доставка по городу", "от 300 ₽", "В день заказа, бережно и вовремя"),
            ("Примерка онлайн", "бесплатно", "Поможем с размером по видеосвязи"),
            ("Скидки постоянным клиентам", "до 20%", "Накопительная карта в подарок"),
        ],
        "benefits": [
            ("Онлайн-заказ", "Оформим за пару минут в мессенджере"),
            ("Обмен и возврат", "14 дней без вопросов"),
            ("Только оригинал", "Работаем с проверенными поставщиками"),
            ("Помощь стилиста", "Подберём образ бесплатно"),
        ],
        "reviews": [
            ("Дарья Н.", "Заказала онлайн, привезли на следующий день. Качество отличное."),
            ("Елена М.", "Помогли подобрать размер по видео — всё подошло идеально."),
            ("Александра К.", "Любимый магазин, всегда есть что-то интересное."),
        ],
    },
}

DEFAULT_PROFILE = {
    "tagline": "Начните работать с нами онлайн",
    "subtitle": "Оставьте заявку — ответим в течение 15 минут",
    "services": [
        ("Консультация", "бесплатно", "Ответим на вопросы и подберём решение"),
        ("Основная услуга", "по запросу", "Расскажем детали и стоимость"),
        ("Срочный заказ", "+30% к стоимости", "Выполним в течение 24 часов"),
        ("Выезд специалиста", "от 1 500 ₽", "В удобное для вас время"),
    ],
    "benefits": [
        ("Онлайн-заявка", "Без звонков и ожидания на линии"),
        ("Прозрачные цены", "Согласуем стоимость заранее"),
        ("Гарантия", "Отвечаем за результат"),
        ("Поддержка", "Остаёмся на связи после оказания услуги"),
    ],
    "reviews": [
        ("Алексей П.", "Быстро ответили, помогли с выбором. Рекомендую."),
        ("Марина С.", "Всё сделали качественно и в срок. Спасибо!"),
        ("Игорь В.", "Удобно, что можно написать и не ждать звонка."),
    ],
}

PAGE = Template("""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$business_name — $category $city_in</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html { scroll-behavior: smooth; }
  body {
    font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background-color: #000000;
  }
</style>
</head>
<body class="bg-[#000000] text-white antialiased">
<div class="mx-auto min-h-screen max-w-md bg-[#000000] shadow-2xl">

  <!-- A2. Hero section -->
  <section class="px-6 pb-8 pt-10">
    <div>
      <span class="inline-flex items-center gap-2 rounded-full border border-[#272727] bg-[#181818] px-3 py-1 text-xs font-semibold text-white/80">
        <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
        $category · $city
      </span>

      <!-- B5. Hero heading with gradient from #FFFFFF to #9B9B9B -->
      <h1 class="mt-4 text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-[#9B9B9B] bg-clip-text text-transparent [text-wrap:balance]">
        $business_name
      </h1>
      <p class="mt-2 text-base font-semibold text-white [text-wrap:balance]">$tagline</p>
      <p class="mt-2 text-sm leading-relaxed text-white/70 [text-wrap:pretty]">$subtitle</p>

      <!-- Proof signal -->
      <div class="mt-4 flex items-center gap-2 text-sm">
        <span class="text-amber-400">$stars</span>
        <span class="font-semibold text-white">$rating</span>
        <span class="text-white/40">· $reviews_count проверенных отзывов</span>
      </div>

      <!-- Action -->
      <div class="mt-6 space-y-3">
        $primary_cta
        <div class="$secondary_class">
          $secondary_ctas
        </div>
        <p class="pt-1 text-center text-xs text-white/40">Ответим за 5 минут · Без звонков и ожидания</p>
      </div>
    </div>
  </section>

  <!-- B11. Mandatory Tagline Reveal Section -->
  <section class="border-y border-[#272727] bg-[#181818] px-6 py-8">
    <p class="text-xs font-bold uppercase tracking-wider text-white/40">Главный ориентир</p>
    <p class="mt-2 text-2xl font-bold leading-snug tracking-tight text-white [text-wrap:balance]">
      Качество, за которым клиенты возвращаются снова
    </p>
    <p class="mt-2 text-sm leading-relaxed text-white/60 [text-wrap:pretty]">
      Честный подход, прозрачный расчет стоимости до начала работы и бережное отношение к каждому посетителю.
    </p>
  </section>

  <!-- How It Works (3 Steps) -->
  <section class="border-b border-[#272727] px-6 py-8">
    <h2 class="text-xl font-bold tracking-tight text-white [text-wrap:balance]">Как мы работаем</h2>
    <div class="mt-4 grid grid-cols-3 gap-2">
      <div class="rounded-2xl border border-[#272727] bg-[#181818] p-3 text-center">
        <span class="text-xs font-bold text-white/40">01</span>
        <p class="mt-1 text-xs font-semibold text-white">Заявка</p>
        <p class="mt-1 text-[11px] text-white/50">В один клик</p>
      </div>
      <div class="rounded-2xl border border-[#272727] bg-[#181818] p-3 text-center">
        <span class="text-xs font-bold text-white/40">02</span>
        <p class="mt-1 text-xs font-semibold text-white">Детали</p>
        <p class="mt-1 text-[11px] text-white/50">За 5 минут</p>
      </div>
      <div class="rounded-2xl border border-[#272727] bg-[#181818] p-3 text-center">
        <span class="text-xs font-bold text-white/40">03</span>
        <p class="mt-1 text-xs font-semibold text-white">Результат</p>
        <p class="mt-1 text-[11px] text-white/50">С гарантией</p>
      </div>
    </div>
  </section>

  <!-- Services & Prices -->
  <section class="px-6 py-8">
    <div class="flex items-end justify-between">
      <h2 class="text-xl font-bold tracking-tight text-white">Услуги и цены</h2>
      <span class="text-xs text-white/40">актуальный прайс</span>
    </div>
    <div class="mt-4 space-y-3">
      $service_cards
    </div>
  </section>

  <!-- Benefits -->
  <section class="border-y border-[#272727] bg-[#181818] px-6 py-8">
    <h2 class="text-xl font-bold tracking-tight text-white">Почему выбирают нас</h2>
    <div class="mt-4 grid grid-cols-2 gap-3">
      $benefit_cards
    </div>
  </section>

  <!-- Social Proof / Reviews -->
  <section class="px-6 py-8">
    <h2 class="text-xl font-bold tracking-tight text-white">Отзывы клиентов</h2>
    <div class="mt-4 space-y-3">
      $review_cards
    </div>
  </section>

  <!-- Risk Reversal -->
  <section class="px-6 pb-6">
    <div class="rounded-2xl border border-[#272727] bg-[#1F1F1F] p-4">
      <p class="text-xs font-bold uppercase tracking-wider text-emerald-400">Гарантия прозрачности</p>
      <p class="mt-1 text-sm font-semibold text-white">Честная смета без скрытых доплат</p>
      <p class="mt-1 text-xs leading-relaxed text-white/60 [text-wrap:pretty]">
        Все детали и цены согласуются до начала оказания услуг. Оплата только после выполнения и вашей проверки.
      </p>
    </div>
  </section>

  <!-- Contacts & Location -->
  <section class="px-6 pb-8">
    <div class="rounded-2xl border border-[#272727] bg-[#181818] p-5">
      <h2 class="text-xl font-bold tracking-tight text-white">Как нас найти</h2>
      <div class="mt-4 space-y-2 text-sm text-white/70">
        <p class="flex items-start gap-2.5"><span>📍</span><span>$address</span></p>
        <p class="flex items-start gap-2.5"><span>🕘</span><span>$hours</span></p>
      </div>
      <a href="$map_url" target="_blank" rel="noopener" class="mt-4 inline-flex h-11 w-full items-center justify-center rounded-xl border border-[#272727] bg-[#272727] text-sm font-semibold text-white transition hover:bg-[#313131]">
        Посмотреть на карте
      </a>
    </div>
  </section>

  <!-- Footer -->
  <footer class="border-t border-[#272727] px-6 py-6 text-center text-xs text-white/40">
    <p class="font-semibold text-white/70">$business_name</p>
    <p class="mt-1">$city · $category</p>
    <p class="mt-2">© $year. Все права защищены.</p>
  </footer>

  <div class="h-20"></div>
</div>

<!-- Sticky Bottom Bar -->
<div class="fixed inset-x-0 bottom-0 z-50 border-t border-[#272727] bg-[#181818]/95 backdrop-blur-xl">
  <div class="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-3">
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-semibold text-white">$business_name</p>
      <p class="truncate text-xs text-white/45">$tagline</p>
    </div>
    <a href="$primary_href" target="_blank" rel="noopener" class="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black transition hover:bg-neutral-200">
      $primary_label
    </a>
  </div>
</div>
</body>
</html>
""")


def _safe(value: str | None, fallback: str = "") -> str:
    return html.escape((value or fallback).strip())


def _city_in(city: str | None) -> str:
    city = (city or "").strip()
    if not city:
        return "в вашем городе"
    if city in CITY_PREPOSITIONAL:
        return f"в {CITY_PREPOSITIONAL[city]}"
    clean_lower = city.lower()
    for name, prep in CITY_PREPOSITIONAL.items():
        if name.lower() == clean_lower:
            return f"в {prep}"
    return f"в городе {city}"


def _business_noun(category: str | None) -> str:
    return BUSINESS_NOUNS.get(category or "", "компания")


def _stars(rating: float | None) -> str:
    value = rating or 4.9
    filled = max(1, min(5, round(value)))
    return "★" * filled + "☆" * (5 - filled)


def _phone_digits(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def _primary_href(lead: dict) -> tuple[str, str, str]:
    socials = lead.get("social_links") or {}
    phone = _phone_digits(lead.get("phone"))
    if socials.get("whatsapp"):
        return socials["whatsapp"], "Записаться в WhatsApp", "Записаться"
    if phone:
        return f"https://wa.me/{phone}", "Записаться в WhatsApp", "Записаться"
    if socials.get("telegram"):
        return socials["telegram"], "Написать в Telegram", "Написать"
    return f"tel:{phone}" if phone else "#contacts", "Связаться с нами", "Связаться"


def build_fallback_landing(lead: dict) -> str:
    category = lead.get("category") or "Бизнес"
    profile = PROFILES.get(category, DEFAULT_PROFILE)
    accent = ACCENTS.get(category, "violet")
    socials = lead.get("social_links") or {}
    phone = lead.get("phone")
    phone_digits = _phone_digits(phone)
    primary_href, primary_label, sticky_label = _primary_href(lead)

    service_cards = "".join(
        f"""<div class="flex items-start justify-between gap-4 rounded-2xl border border-[#272727] bg-[#181818] p-4">
          <div>
            <p class="text-sm font-semibold text-white">{_safe(name)}</p>
            <p class="mt-1 text-xs leading-relaxed text-white/50">{_safe(desc)}</p>
          </div>
          <span class="whitespace-nowrap rounded-lg border border-[#272727] bg-[#1F1F1F] px-2.5 py-1 text-xs font-semibold text-white">{_safe(price)}</span>
        </div>"""
        for name, price, desc in profile["services"]
    )

    benefit_cards = "".join(
        f"""<div class="rounded-2xl border border-[#272727] bg-[#181818] p-4">
          <p class="text-sm font-semibold text-white">{_safe(title)}</p>
          <p class="mt-1 text-xs leading-relaxed text-white/50">{_safe(desc)}</p>
        </div>"""
        for title, desc in profile["benefits"]
    )

    review_cards = "".join(
        f"""<div class="rounded-2xl border border-[#272727] bg-[#181818] p-4">
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-white">{_safe(author)}</p>
            <span class="text-xs text-amber-400">★★★★★</span>
          </div>
          <p class="mt-2 text-xs leading-relaxed text-white/60">«{_safe(text)}»</p>
        </div>"""
        for author, text in profile["reviews"]
    )

    secondary: list[str] = []
    if socials.get("telegram"):
        secondary.append(
            f'<a href="{html.escape(socials["telegram"])}" target="_blank" rel="noopener" '
            f'class="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#272727] bg-[#181818] text-sm font-semibold text-white transition hover:bg-[#272727]">'
            f'Telegram</a>'
        )
    if phone:
        secondary.append(
            f'<a href="tel:{html.escape(phone_digits)}" class="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#272727] bg-[#181818] text-sm font-semibold text-white transition hover:bg-[#272727]">'
            f'Позвонить</a>'
        )
    if not secondary:
        secondary.append(
            f'<a href="#contacts" class="inline-flex h-11 items-center justify-center rounded-xl border border-[#272727] bg-[#181818] text-sm font-semibold text-white transition hover:bg-[#272727]">Наши контакты</a>'
        )

    primary_cta = (
        f'<a href="{html.escape(primary_href)}" target="_blank" rel="noopener" '
        f'class="inline-flex h-12 w-full items-center justify-center rounded-xl bg-white text-base font-semibold text-black transition hover:bg-neutral-200">'
        f'{_safe(primary_label)}</a>'
    )

    address = _safe(lead.get("address"), "Адрес уточняется")
    hours = "<br>".join(_safe(item) for item in (lead.get("opening_hours") or [])) or "Ежедневно 10:00–20:00"
    map_url = f"https://yandex.ru/maps/?text={quote(lead.get('name', '') + ' ' + (lead.get('address') or ''))}"
    rating = f"{lead.get('rating'):.1f}" if lead.get("rating") else "4.9"

    return PAGE.safe_substitute(
        business_name=_safe(lead.get("name"), "Ваш бизнес"),
        category=_safe(category),
        city=_safe(lead.get("city"), "вашем городе"),
        city_in=_safe(_city_in(lead.get("city"))),
        tagline=_safe(profile["tagline"]),
        subtitle=_safe(profile["subtitle"]),
        stars=_stars(lead.get("rating")),
        rating=rating,
        reviews_count=lead.get("reviews_count") or 0,
        accent=accent,
        primary_cta=primary_cta,
        secondary_class="grid gap-3" if len(secondary) == 1 else "grid grid-cols-2 gap-3",
        secondary_ctas="".join(secondary),
        primary_href=html.escape(primary_href),
        primary_label=_safe(sticky_label),
        service_cards=service_cards,
        benefit_cards=benefit_cards,
        review_cards=review_cards,
        address=address,
        hours=hours,
        map_url=html.escape(map_url),
        year="2026",
    )


def _sanitize_html(value: str) -> str:
    value = re.sub(
        r"<script(?![^>]*cdn\.tailwindcss\.com)[^>]*>.*?</script>",
        "",
        value,
        flags=re.I | re.S,
    )
    value = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", value, flags=re.I)
    value = re.sub(r"<(object|embed|form)\b[^>]*>.*?</\1>", "", value, flags=re.I | re.S)
    return value


def _extract_html(raw: str) -> str | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.lower().find("<!doctype html")
    if start == -1:
        start = cleaned.lower().find("<html")
    if start == -1:
        return None
    cleaned = cleaned[start:]
    if "</html>" not in cleaned.lower():
        cleaned += "\n</html>"
    if len(cleaned) < 800:
        return None
    return _sanitize_html(cleaned)


LANDING_SYSTEM = (
    "Ты ведущий UI/UX дизайнер и frontend-разработчик премиальных конверсионных мобильных лендингов. "
    "Ты создаёшь посадочные страницы строго по дизайн-системе landing-page-design: "
    "один оффер → одна аудитория → одно целевое действие. "
    "Отвечай ИСКЛЮЧИТЕЛЬНО готовым полным валидным HTML-кодом (начиная с <!DOCTYPE html> и заканчивая </html>), "
    "без markdown-разметки (без тройных бэктиков), без пояснений и комментариев."
)

LANDING_PROMPT = Template(
    """Создай премиальный конверсионный мобильный лендинг (mobile-first) для бизнеса по строгой дизайн-системе landing-page-design.

Данные компании в JSON:
$company

CTA-ссылки:
- WhatsApp: $whatsapp_link
- Telegram: $telegram_link
- Телефон: $phone_link

ТРЕБОВАНИЯ ДИЗАЙН-СИСТЕМЫ (LANDING-PAGE-DESIGN):

ЧАСТЬ 1 — СТРУКТУРА И КОПИРАЙТИНГ (PART A):
1. Структура страницы (max-w-md mx-auto):
   - Hero: заголовок (конкретный результат + аудитория), подзаголовок (детали как именно достигается), один главный CTA, блок социального доказательства (рейтинг со звездами, число реальных отзывов).
   - B11 Tagline Reveal: отдельная выразительная секция (text-2xl / text-3xl font-bold) с главным слоганом/ценностью бизнеса в 2 строки.
   - Проблема → Решение: 1 краткий блок, закрывающий главную боль клиентов в нише «$category».
   - Выгоды: 3-4 пункта, ориентированные на результат (жирный заголовок выгоды + деталь).
   - Как мы работаем: ровно 3 простых последовательных шага.
   - Услуги и цены: карточки с названием, понятным описанием и конкретными реалистичными ценами (без подозрительно круглых цифр).
   - Отзывы: 3 реалистичных отзыва с полными именами людей (например, «Алёна Воронина», «Дмитрий Смирнов») и конкретными фактами.
   - Снятие рисков (Risk reversal): блок о прозрачной смете, гарантии и проверке до оплаты.
   - Контакты и локация: адрес, часы работы, кнопка открытия карты.
   - Фиксированная нижняя панель (sticky bottom bar) с кнопкой быстрой записи в $whatsapp_link или $telegram_link.
2. Копирайтинг:
   - Без дефисов внутри предложений.
   - text-wrap: balance для заголовков, text-wrap: pretty для текста.
   - Запрещены пустые клише: «revolutionize», «cutting edge», «supercharge», «лучший в мире», «инновационный», «премиум под ключ». Пиши живым языком, чем реально полезна услуга.

ЧАСТЬ 2 — СТРОГАЯ ВИЗУАЛЬНАЯ СИСТЕМА (PART B):
1. Шрифт: подключай через Google Fonts СТРОГО шрифт Manrope:
   <link rel="preconnect" href="https://fonts.googleapis.com">
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
   <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
   CSS: font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
   СТРОГО ЗАПРЕЩЕНО: Inter, Roboto, Arial, Open Sans, Helvetica.
   СТРОГО ЗАПРЕЩЕНО использовать курсив (italic) и начертания тяжелее 700 (никаких 900/black).
2. Цвета фона:
   СТРОГО ЗАПРЕЩЕНЫ градиенты на фоне! Все фоны исключительно ПЛОСКИЕ (flat).
   Используй только допустимые темные цвета: #000000, #181818, #1F1F1F, #272727, #313131.
   Фон страницы — #000000. Поверхности карточек — #181818 или #1F1F1F.
3. Градиенты в Hero:
   Градиент разрешен ТОЛЬКО на тексте главного заголовка: слева направо от #FFFFFF к #9B9B9B:
   (bg-gradient-to-r from-white to-[#9B9B9B] bg-clip-text text-transparent). Никаких градиентов на фоне!
4. Границы (Borders):
   Границы карточек — всегда по всему периметру (border border-[#272727] или border-white/10). Запрещено делать границу только с одной стороны.
5. Скругления (Nested radius formula):
   inner radius = outer radius - gap. Если внешняя карточка rounded-2xl (16px) с padding 8px -> внутренний бейдж rounded-lg (8px).
6. Типографика:
   Строго шкала Tailwind: text-xs, text-sm, text-base, text-lg, text-xl, text-2xl, text-3xl, text-4xl.
7. Кнопки:
   Высота h-11 или h-12, text-base, font-semibold, контрастный фон (белый с черным текстом или акцентный).
8. Стилизация только через <script src="https://cdn.tailwindcss.com"></script>. Не добавляй формы сбора данных, метрики и сторонние скрипты.

Верни ТОЛЬКО готовый HTML код."""
)


async def generate_landing_html(lead: dict) -> tuple[str, str]:
    company = {
        "name": lead.get("name"),
        "category": lead.get("category"),
        "city": lead.get("city"),
        "address": lead.get("address"),
        "phone": lead.get("phone"),
        "rating": lead.get("rating"),
        "reviews_count": lead.get("reviews_count"),
        "opening_hours": lead.get("opening_hours"),
        "social_links": lead.get("social_links"),
        "has_website": lead.get("has_website"),
    }
    socials = lead.get("social_links") or {}
    phone = _phone_digits(lead.get("phone"))
    prompt = LANDING_PROMPT.safe_substitute(
        company=json.dumps(company, ensure_ascii=False, indent=2),
        whatsapp_link=socials.get("whatsapp") or (f"https://wa.me/{phone}" if phone else "нет"),
        telegram_link=socials.get("telegram") or "нет",
        phone_link=f"tel:{phone}" if phone else "нет",
        category=lead.get("category") or "Бизнес",
        city=lead.get("city") or "Россия",
    )
    try:
        raw = await chat_completion(LANDING_SYSTEM, prompt, max_tokens=7000, temperature=0.75)
        parsed = _extract_html(raw)
        if parsed:
            return parsed, "llm"
    except Exception:
        pass
    return build_fallback_landing(lead), "template"


OUTREACH_SYSTEM = (
    "Ты профессиональный B2B-копирайтер для фрилансеров и веб-студий. "
    "Твоя задача — составить короткий, тактичный, уважительный и ненавязчивый текст первого отклика "
    "владельцу бизнеса в мессенджере (WhatsApp или Telegram). "
    "Отвечай ТОЛЬКО готовым текстом сообщения без кавычек в начале/конце и без вступительных пояснений."
)

OUTREACH_PROMPT = Template(
    """Составь короткое первое сообщение для владельца компании:
- Название компании: $name
- Сфера: $category
- Город: $city
- Наличие сайта: $has_site
- Ссылка на черновой концепт: $demo_url

Правила:
1. Приветствие строго «Здравствуйте!» (никаких панибратских «Привет»).
2. НЕ критикуй клиента («у вас плохой сайт», «клиенты уходят к конкурентам»). Никакого давления и агрессивного спама.
3. Коротко поясни, что разрабатываешь сайты под ключ для этой сферы бизнеса, помогаешь упаковать услуги и привлекать клиентов через мессенджеры.
4. Мягкий призыв: если тема актуальна — напишите в ответ, пришлю примеры реальных работ и сориентирую по ценам и срокам.
5. В конце в скобках или P.S. ненавязчиво упомяни ссылку на черновой концепт: $demo_url.
6. Заверши пожеланием хорошего дня.
7. Текст должен быть живым, естественным и лаконичным (до 80-120 слов)."""
)


def build_outreach(lead: dict, demo_url: str) -> str:
    city = lead.get("city") or ""
    city_in = _city_in(city)
    name = lead.get("name") or "ваша компания"
    noun = _business_noun(lead.get("category"))
    plural_gen = BUSINESS_PLURAL_GENITIVE.get(lead.get("category") or "", "локального бизнеса")
    socials = lead.get("social_links") or {}
    channel = "Telegram" if socials.get("telegram") else "WhatsApp"

    if lead.get("has_website"):
        lead_context = f"Обратил внимание на ваш бизнес {noun} «{name}» {city_in}."
        niche_focus = (
            f"Я занимаюсь созданием и упаковкой современных сайтов для {plural_gen} — "
            f"помогаю привлекать клиентов из поиска и рекламы, оформлять удобную запись в {channel} с телефона."
        )
    else:
        lead_context = (
            f"Увидел ваш бизнес {noun} «{name}» {city_in}. "
            f"Заметил, что у вас пока нет отдельного мобильного сайта."
        )
        niche_focus = (
            f"Я как раз разрабатываю быстрые сайты под ключ для {plural_gen} — с понятным прайсом, "
            f"онлайн-записью в {channel} и адаптацией под смартфоны, чтобы клиентам было просто обращаться."
        )

    return (
        f"Здравствуйте! {lead_context}\n\n"
        f"{niche_focus}\n\n"
        f"Если для вас сейчас актуально привлечение новых клиентов — напишите мне в ответ. "
        f"Если интересно, с радостью пришлю примеры реальных работ и сориентирую по срокам и стоимости.\n\n"
        f"(Кстати, набросал черновой вариант интерактивного концепта под вас, можно взглянуть здесь: {demo_url})\n\n"
        f"Хорошего вам дня!"
    )


async def generate_outreach_message(lead: dict, demo_url: str) -> str:
    if settings.llm_provider and settings.llm_provider.lower() != "mock":
        name = lead.get("name") or "ваша компания"
        category = lead.get("category") or "Бизнес"
        city = lead.get("city") or "Россия"
        has_site = "Есть сайт" if lead.get("has_website") else "Нет отдельного сайта"
        prompt = OUTREACH_PROMPT.safe_substitute(
            name=name,
            category=category,
            city=city,
            has_site=has_site,
            demo_url=demo_url,
        )
        try:
            raw = await chat_completion(OUTREACH_SYSTEM, prompt, max_tokens=1000, temperature=0.7)
            cleaned = raw.strip().strip('"').strip("'")
            if cleaned and len(cleaned) > 50:
                return cleaned
        except Exception:
            pass
    return build_outreach(lead, demo_url)
