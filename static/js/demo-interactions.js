(function () {
  "use strict";

  var script = document.currentScript;
  var base = (script && script.dataset.base) || "/student-platform";
  base = base.replace(/\/+$/, "");
  var monthNames = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];

  function toast(message) {
    var box = document.getElementById("demo-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "demo-toast";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      box.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:1000;max-width:min(92vw,640px);padding:12px 18px;border-radius:12px;background:#1d1f27;color:#fff;box-shadow:0 8px 30px #0003;font:600 14px/1.45 Inter,system-ui,sans-serif;text-align:center;opacity:0;transition:opacity .18s";
      document.body.appendChild(box);
    }
    box.textContent = message;
    box.style.opacity = "1";
    clearTimeout(box._hideTimer);
    box._hideTimer = setTimeout(function () { box.style.opacity = "0"; }, 3200);
  }

  function statusMeansMine(card) {
    if (card.dataset.demoMine) return card.dataset.demoMine === "true" || card.dataset.demoMine === "1";
    var status = (card.querySelector(".badge") || {}).textContent || "";
    status = status.trim().toLocaleLowerCase("ru");
    return ["записан", "посещено", "лист ожидания", "выполнено", "на проверке", "нужна доработка", "не пройдено", "можно попробовать снова", "пройдено"].some(function (item) {
      return status.indexOf(item) === 0;
    });
  }

  function applyActivities(form) {
    var mineInput = form.querySelector('[name="mine"]');
    var onlyMine = !!(mineInput && mineInput.checked);
    var list = document.querySelector(".activity-list");
    if (list) {
      var cards = Array.prototype.slice.call(list.querySelectorAll(".activity-card"));
      var shown = 0;
      cards.forEach(function (card) {
        var visible = !onlyMine || statusMeansMine(card);
        card.hidden = !visible;
        if (visible) shown += 1;
      });
      toast(onlyMine ? ("Показаны ваши активности: " + shown) : ("Показаны все активности: " + shown));
      return;
    }

    var calendar = document.getElementById("cal");
    if (!calendar) { toast("Фильтр применён к демонстрационному списку."); return; }
    var category = (form.querySelector('[name="cat"]') || {}).value || "";
    var events = Array.prototype.slice.call(calendar.querySelectorAll(".ev"));
    var shownEvents = 0;
    events.forEach(function (event) {
      var categoryMatch = !category || event.dataset.demoCategory === category;
      var mineMatch = !onlyMine || event.dataset.demoMine === "true" || event.dataset.demoMine === "1" || event.classList.contains("mine");
      event.hidden = !(categoryMatch && mineMatch);
      if (!event.hidden) shownEvents += 1;
    });
    toast("В календаре показано событий: " + shownEvents);
  }

  function applyEmployerFilter(form) {
    var select = form.querySelector('[name="track"]');
    var track = select ? select.value : "";
    var trackLabel = select && select.selectedOptions.length ? select.selectedOptions[0].textContent.trim().toLocaleLowerCase("ru") : "";
    var cards = document.querySelectorAll(".grid > article.card");
    var shown = 0;
    cards.forEach(function (card) {
      var chips = Array.prototype.slice.call(card.querySelectorAll(".chip")).map(function (chip) { return chip.textContent.trim().toLocaleLowerCase("ru"); });
      var visible = !track || chips.indexOf(trackLabel) !== -1;
      card.hidden = !visible;
      if (visible) shown += 1;
    });
    toast(track ? ("Найдено работодателей: " + shown) : ("Показаны все работодатели: " + shown));
  }

  function applyMeetingFilter(form) {
    var input = form.querySelector('[name="only"]');
    var onlyMine = !!(input && input.checked);
    var cards = Array.prototype.slice.call(form.parentElement.querySelectorAll(":scope > article.card"));
    var shown = 0;
    cards.forEach(function (card) {
      var button = card.querySelector("form button");
      var booked = button && /отменить запись|выйти из записи/i.test(button.textContent);
      var visible = !onlyMine || booked;
      card.hidden = !visible;
      if (visible) shown += 1;
    });
    toast(onlyMine ? ("Ваши записи: " + shown) : ("Показаны встречи: " + shown));
  }

  function applySearch(form) {
    var field = form.querySelector('input[type="search"], input[name="q"], input[name="search"]');
    var query = field ? field.value.trim().toLocaleLowerCase("ru") : "";
    var container = form.nextElementSibling;
    if (!container) { toast("Введите запрос, чтобы найти совпадения."); return; }
    var cards = Array.prototype.slice.call(container.querySelectorAll("article, .list-item, .activity-card"));
    if (!cards.length) { toast("В этом разделе нет элементов для поиска."); return; }
    var shown = 0;
    cards.forEach(function (card) {
      var visible = !query || card.textContent.toLocaleLowerCase("ru").indexOf(query) !== -1;
      card.hidden = !visible;
      if (visible) shown += 1;
    });
    toast("Найдено элементов: " + shown);
  }

  function isDemoFilter(form) {
    return !!form.querySelector('[name="track"], [name="only"], [name="cat"], [name="mine"], input[type="search"], [name="q"], [name="search"]');
  }

  function applyShopCategory(kind) {
    var cards = document.querySelectorAll(".shop-grid [data-demo-shop-category]");
    if (!cards.length) return;
    cards.forEach(function (card) {
      card.hidden = !!kind && card.dataset.demoShopCategory !== kind;
    });
    document.querySelectorAll("[data-demo-shop-filter]").forEach(function (link) {
      var active = link.dataset.demoShopFilter === kind;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function initShopCategory() {
    if (!document.querySelector(".shop-grid [data-demo-shop-category]")) return;
    applyShopCategory(new URLSearchParams(location.search).get("category") || "");
  }

  function updateGroupSummary(form) {
    if (!form || form.id !== "activity-demo-form") return;
    var summary = form.querySelector("[data-groups-summary]");
    var selected = form.querySelectorAll('[name="groups"]:checked').length;
    if (summary) summary.textContent = selected ? ("Выбрано групп: " + selected) : "Выберите группы";
    var trackSummary = form.querySelector("[data-tracks-summary]");
    var selectedTracks = form.querySelectorAll('[name="tracks"]:checked').length;
    if (trackSummary) trackSummary.textContent = selectedTracks ? ("Выбрано направлений: " + selectedTracks) : "Выберите направления";
  }

  function updateActivityFields(form) {
    if (!form) return;
    var type = form.elements.activity_type.value;
    form.querySelectorAll(".event-only").forEach(function (node) { node.hidden = type !== "event"; });
    form.querySelectorAll(".task-only").forEach(function (node) { node.hidden = type !== "task"; });
    form.querySelectorAll(".survey-only").forEach(function (node) { node.hidden = type !== "survey"; });
  }

  function trackSpecialtyMap() {
    return {
      "it-support": ["09.02.07", "09.02.12"],
      "it-ai": ["09.02.13"],
      "it-development": ["09.02.07", "09.02.09", "09.02.11"],
      "creative-design": ["54.01.20", "54.02.01"],
      "creative-animation": ["55.02.02"],
      "finance": ["38.02.06"],
      "cooks": ["43.02.15"],
      "transport-service": ["43.02.06"],
      "hospitality": ["43.02.16"]
    };
  }

  function initTrackDetails() {
    var match = location.pathname.match(/\/career\/tracks\/([^/]+)\/?$/);
    if (!match) return;
    var roles = {
      "it-support": ["Специалист технической поддержки информационных систем", "Диагностирует обращения, настраивает рабочие места и доступы, документирует решения.", "Операционные системы, компьютерные сети, основы информационной безопасности, сервис-деск.", "Поиск причин неисправностей, настройка ПО, коммуникация, техническая документация."],
      "it-ai": ["Специалист по интеграции решений с ИИ", "Подбирает ИИ-инструменты под задачу, подключает сервисы и API, проверяет качество и безопасность результата.", "Основы ИИ, работа с данными, API и приватность.", "Постановка задач, тестирование ответов, базовое программирование, оценка рисков."],
      "it-development": ["Веб-разработчик / разработчик программного обеспечения", "Создаёт и поддерживает сайты и приложения, исправляет ошибки, работает с командой и документацией.", "Языки программирования, алгоритмы, базы данных, API, системы контроля версий.", "Разработка и отладка кода, чтение технических заданий, командная работа."],
      "creative-design": ["Графический / отраслевой дизайнер", "Исследует задачу, разрабатывает визуальную концепцию, готовит макеты к публикации или производству.", "Композиция, типографика, цвет, визуальные коммуникации, авторское право.", "Графические редакторы, прототипирование, презентация решений, работа с обратной связью."],
      "creative-animation": ["Художник-аниматор", "Создаёт раскадровки и анимацию, готовит материалы и сцены, участвует в производственном цикле.", "Основы драматургии, композиция, движение, принципы 2D/3D-анимации.", "Раскадровка, работа с кадром и таймингом, цифровые инструменты, командная работа."],
      "finance": ["Специалист финансового направления", "Обрабатывает финансовые документы, готовит расчёты и сводки, помогает контролировать бюджет.", "Основы экономики, финансового учёта, документооборота и деловой этики.", "Точность расчётов, таблицы, анализ данных, внимательность."],
      "cooks": ["Повар-кондитер", "Подготавливает продукты, готовит блюда и изделия по технологическим картам, соблюдает санитарные требования.", "Технология приготовления, сырьё, рецептуры, хранение и безопасность продуктов.", "Работа с оборудованием, точность рецептуры, организация рабочего места, соблюдение времени."],
      "transport-service": ["Специалист сервиса на транспорте", "Помогает пассажирам, координирует сервисные операции, решает типовые запросы во время поездки.", "Клиентский сервис, правила безопасности, основы транспортной логистики.", "Коммуникация, решение нестандартных ситуаций, внимательность, командная работа."],
      "hospitality": ["Специалист гостиничного сервиса", "Работает с бронированиями и размещением, отвечает на запросы гостей, координирует обслуживание.", "Гостиничные процессы, стандарты обслуживания, основы туризма и деловой коммуникации.", "Системы бронирования, иностранный язык, решение запросов гостей, командная работа."]
    };
    var role = roles[match[1]];
    var head = document.querySelector("main .page-head");
    var firstCard = head && head.nextElementSibling;
    if (!role || !firstCard || !firstCard.classList.contains("card")) return;
    var specialty = new URLSearchParams(location.search).get("specialty") || "09.02.07";
    if (!(trackSpecialtyMap()[match[1]] || []).includes(specialty)) {
      var notice = document.createElement("p");
      notice.className = "badge warn";
      notice.textContent = "Этот трек не связан со специальностью демо-студента. Вернитесь к списку и выберите другую специальность.";
      firstCard.prepend(notice);
      firstCard.querySelectorAll("form button").forEach(function (button) { button.disabled = true; });
    }
    var info = document.createElement("div");
    info.className = "track-role-info";
    info.innerHTML = "<h2>Пример должности: " + role[0] + "</h2><h3>Типовые задачи</h3><p>" + role[1] + "</p><h3>Что нужно знать</h3><p>" + role[2] + "</p><h3>Какие навыки развивать</h3><p>" + role[3] + "</p>";
    var enrollForm = firstCard.querySelector("form");
    if (enrollForm) firstCard.insertBefore(info, enrollForm);
    else firstCard.appendChild(info);
    var opportunities = document.createElement("section");
    opportunities.className = "card";
    opportunities.innerHTML = "<h2>Работодатели и вакансии</h2><p>В реальной платформе колледж публикует здесь предложения компаний, практики и профессиональные пробы по этому треку.</p><p class=\"admin-note\">Демо-версия показывает раздел; актуальные предложения появятся после настройки колледжем.</p><a class=\"btn secondary\" href=\"/student-platform/career/employers/\">Работодатели →</a>";
    firstCard.insertAdjacentElement("afterend", opportunities);
  }

  function initTrackList() {
    if (!/\/career\/tracks\/?$/.test(location.pathname)) return;
    var titles = {
      "it-support": "Специалист технической поддержки информационных систем",
      "it-ai": "Специалист по интеграции решений с ИИ",
      "it-development": "Веб-разработчик / разработчик программного обеспечения",
      "creative-design": "Графический / отраслевой дизайнер",
      "creative-animation": "Художник-аниматор",
      "finance": "Специалист финансового направления",
      "cooks": "Повар-кондитер",
      "transport-service": "Специалист сервиса на транспорте",
      "hospitality": "Специалист гостиничного сервиса"
    };
    var picker = document.querySelector("[data-demo-specialty]");
    var params = new URLSearchParams(location.search);
    var currentSpecialty = params.get("specialty") || "09.02.07";
    if (picker) picker.value = currentSpecialty;
    document.querySelectorAll("main .grid > article.card").forEach(function (card) {
      var link = card.querySelector("h2 a[href*='/career/tracks/']");
      var slug = link && link.getAttribute("href").match(/\/career\/tracks\/([^/]+)\//);
      var title = slug && titles[slug[1]];
      if (!title) return;
      var allowed = (trackSpecialtyMap()[slug[1]] || []).includes(currentSpecialty);
      card.hidden = !allowed;
      card.querySelectorAll("a[href]").forEach(function (itemLink) {
        var linkUrl = new URL(itemLink.href, location.origin);
        linkUrl.searchParams.set("specialty", currentSpecialty);
        itemLink.href = linkUrl.pathname + linkUrl.search;
      });
      var position = document.createElement("p");
      position.innerHTML = "<b>Пример должности:</b> " + title;
      link.closest("h2").insertAdjacentElement("afterend", position);
    });
    if (picker) picker.addEventListener("change", function () {
      var next = new URL(location.href);
      next.searchParams.set("specialty", picker.value);
      location.href = next.pathname + next.search;
    });
    if (!params.has("specialty")) {
      params.set("specialty", currentSpecialty);
      history.replaceState(null, "", location.pathname + "?" + params.toString());
    }
  }

  var demoStudents = {
    anna: { initial: "А", name: "Анна Иванова", group: "ПО-116", direction: "09.02.11 · Разработка и управление программным обеспечением", course: 1, balance: 70, earned: 70, achievementCount: 1, rankGroup: 2, rankDirection: 5, rankTrack: 2, rankAll: 18, progress: 84, stages: "4 из 5 этапов", track: "ИТ · Разработка", achievements: [{ icon: "★", name: "Первый шаг", date: "13.11.2026" }], history: [{ title: "Достижение «Первый шаг»", detail: "13.11.2026 · Значок", amount: "+5" }, { title: "Посещение: Хакатон «Цифровой колледж»", detail: "13.11.2026 · Посещение мероприятия", amount: "+50" }, { title: "Посещение: Мастер-класс по скетчингу", detail: "13.11.2026 · Посещение мероприятия", amount: "+15" }], registrations: ["Экскурсия в ИТ-компанию · зарегистрирована", "Встреча с разработчиком · в списке ожидания"], orders: ["Футболка 01:17 · готов к выдаче"] },
    dmitry: { initial: "Д", name: "Дмитрий Смирнов", group: "ИИ-116", direction: "09.02.13 · Интеграция решений с применением технологий искусственного интеллекта", course: 1, balance: 120, earned: 160, achievementCount: 3, rankGroup: 1, rankDirection: 3, rankTrack: 1, rankAll: 7, progress: 68, stages: "Текущий трек", track: "ИТ · ИИ", achievements: [{ icon: "◎", name: "Профиль интересов", date: "12.11.2026" }, { icon: "↗", name: "Путь выбран", date: "10.11.2026" }, { icon: "★", name: "Первый шаг", date: "08.11.2026" }], history: [{ title: "Посещение: Встреча с ИТ-командой", detail: "14.11.2026 · Посещение мероприятия", amount: "+40" }, { title: "Профдиагностика завершена", detail: "12.11.2026 · Карьерный трек", amount: "+20" }, { title: "Задание «Мой первый проект»", detail: "10.11.2026 · Задание", amount: "+10" }], registrations: ["Встреча с ИТ-командой · посетил"], orders: ["Рюкзак 01:17 · заказан"] },
    ekaterina: { initial: "Е", name: "Екатерина Петрова", group: "Дизайн-ДЕМО", direction: "54.01.20 · Графический дизайн", course: 1, balance: 95, earned: 135, achievementCount: 4, rankGroup: 3, rankDirection: 2, rankTrack: 1, rankAll: 12, progress: 91, stages: "Текущий трек", track: "Креатив · Дизайн", achievements: [{ icon: "✦", name: "Автор идеи", date: "14.11.2026" }, { icon: "◎", name: "Профиль интересов", date: "12.11.2026" }, { icon: "↗", name: "Путь выбран", date: "09.11.2026" }], history: [{ title: "Внешнее достижение подтверждено", detail: "14.11.2026 · Портфолио", amount: "+25" }, { title: "Посещение: Дизайн-сессия", detail: "12.11.2026 · Посещение мероприятия", amount: "+15" }, { title: "Задание «Визуальная концепция»", detail: "09.11.2026 · Задание", amount: "+20" }], registrations: ["Дизайн-сессия с представителем компании · посетила"], orders: [] }
  };

  var demoRosterGroups = [
    { slug: "it-support", group: "ИС-116", direction: "09.02.12 · Техническая эксплуатация и сопровождение информационных систем", track: "ИТ · Поддержка", sample: null },
    { slug: "it-ai", group: "ИИ-116", direction: "09.02.13 · Интеграция решений с применением технологий искусственного интеллекта", track: "ИТ · ИИ", sample: "dmitry" },
    { slug: "it-development", group: "ПО-116", direction: "09.02.11 · Разработка и управление программным обеспечением", track: "ИТ · Разработка", sample: "anna" },
    { slug: "creative-design", group: "Дизайн-ДЕМО", direction: "54.01.20 · Графический дизайн (демо)", track: "Креатив · Дизайн", sample: "ekaterina" },
    { slug: "creative-animation", group: "Анимация-ДЕМО", direction: "55.02.02 · Анимация и анимационное кино (демо)", track: "Креатив · Анимация", sample: null },
    { slug: "finance", group: "26ФН-01", direction: "38.02.06 · Финансы", track: "Финансы", sample: null },
    { slug: "cooks", group: "26ПКД-02", direction: "43.02.15 · Поварское и кондитерское дело", track: "Повара", sample: null },
    { slug: "transport-service", group: "26СТ-07", direction: "43.02.06 · Сервис на транспорте", track: "Сервис на транспорте", sample: null },
    { slug: "hospitality", group: "26ТГ-06", direction: "43.02.16 · Туризм и гостеприимство", track: "Гостиницы", sample: null }
  ];
  var demoFirstNames = ["Анна", "Даниил", "Софья", "Максим", "Алиса", "Иван", "Мария", "Кирилл", "Виктория", "Артём", "Полина", "Михаил", "Елизавета", "Дмитрий", "Варвара", "Матвей", "Анастасия", "Роман", "Дарья", "Никита", "Ксения", "Егор", "Арина", "Лев", "Милана", "Тимофей", "Ева", "Илья", "Василиса", "Александр"];
  var demoLastNames = ["Иванова", "Попов", "Кузнецова", "Смирнов", "Петрова", "Васильев", "Соколова", "Михайлов", "Новикова", "Фёдоров", "Морозова", "Волков", "Алексеева", "Лебедев", "Семёнова", "Егоров", "Павлова", "Козлов", "Степанова", "Николаев", "Орлова", "Андреев", "Макарова", "Захаров", "Зайцева", "Соловьёв", "Борисова", "Яковлев", "Григорьева", "Романов"];

  function renderDemoRoster() {
    var tbody = document.querySelector("[data-demo-student-roster]");
    if (!tbody) return;
    var fragment = document.createDocumentFragment();
    demoRosterGroups.forEach(function (group, groupIndex) {
      for (var index = 1; index <= 30; index += 1) {
        var id = group.sample && index === 1 ? group.sample : "demo-" + group.slug + "-" + String(index).padStart(2, "0");
        var student = demoStudents[id];
        if (!student) {
          var name = demoFirstNames[(index - 1 + groupIndex * 3) % demoFirstNames.length] + " " + demoLastNames[(index - 1 + groupIndex * 7) % demoLastNames.length];
          var progress = 45 + ((index * 7 + groupIndex * 11) % 55);
          var balance = 30 + ((index * 13 + groupIndex * 9) % 140);
          student = demoStudents[id] = {
            initial: name.charAt(0), name: name, group: group.group, direction: group.direction, course: 1,
            balance: balance, earned: balance + 20 + (index % 5) * 10, achievementCount: 1 + (index % 4),
            rankGroup: index, rankDirection: index, rankTrack: index, rankAll: groupIndex * 30 + index,
            progress: progress, stages: Math.min(5, Math.floor(progress / 20)) + " из 5 этапов", track: group.track,
            achievements: [{ icon: "★", name: index % 2 ? "Первый шаг" : "Знакомство с профессией", date: "17.11.2026" }],
            history: [{ title: "Участие в карьерной активности", detail: "17.11.2026 · Демо-запись", amount: "+10" }],
            registrations: ["Встреча с представителем направления · зарегистрирован"], orders: []
          };
        }
        var row = document.createElement("tr");
        row.dataset.rosterGroup = group.slug;
        row.dataset.rosterSearch = (student.name + " " + group.group + " " + group.track).toLocaleLowerCase("ru");
        var studentCell = document.createElement("td");
        var profileButton = document.createElement("button");
        profileButton.className = "student-profile-link";
        profileButton.type = "button";
        profileButton.dataset.studentProfile = id;
        profileButton.textContent = student.name;
        studentCell.appendChild(profileButton);
        var groupCell = document.createElement("td"); groupCell.textContent = "1 курс · " + group.group;
        var trackCell = document.createElement("td"); trackCell.textContent = group.track;
        var progressCell = document.createElement("td");
        var progressBar = document.createElement("div"); progressBar.className = "admin-progress";
        var progressFill = document.createElement("i"); progressFill.style.width = student.progress + "%"; progressBar.appendChild(progressFill);
        var progressText = document.createElement("small"); progressText.textContent = student.progress + "%";
        progressCell.append(progressBar, progressText);
        row.append(studentCell, groupCell, trackCell, progressCell);
        fragment.appendChild(row);
      }
    });
    tbody.replaceChildren(fragment);
    var search = document.querySelector("[data-roster-search]");
    var groupFilter = document.querySelector("[data-roster-group]");
    function filterRows() {
      var query = search.value.trim().toLocaleLowerCase("ru");
      var selectedGroup = groupFilter.value;
      Array.from(tbody.rows).forEach(function (row) {
        row.hidden = (selectedGroup && row.dataset.rosterGroup !== selectedGroup) || (query && !row.dataset.rosterSearch.includes(query));
      });
    }
    if (search) search.addEventListener("input", filterRows);
    if (groupFilter) groupFilter.addEventListener("change", filterRows);
  }

  renderDemoRoster();

  function fillStudentProfile(id, dialog) {
    var student = demoStudents[id];
    if (!student || !dialog) return;
    var root = dialog.querySelector("[data-student-card]");
    root.hidden = false;
    root.querySelector("[data-profile-initial]").textContent = student.initial;
    root.querySelector("[data-profile-name]").textContent = student.name;
    root.querySelector("[data-profile-group]").textContent = student.group;
    root.querySelector("[data-profile-course]").textContent = student.course;
    root.querySelector("[data-profile-direction]").textContent = student.direction;
    root.querySelector("[data-profile-balance]").textContent = student.balance;
    root.querySelector("[data-profile-earned]").textContent = student.earned;
    root.querySelector("[data-profile-achievement-count]").textContent = student.achievementCount;
    root.querySelectorAll("[data-profile-progress]").forEach(function (node) { node.textContent = student.progress + "%"; });
    ["group", "direction", "track", "all"].forEach(function (key) {
      var rank = root.querySelector("[data-profile-rank-" + key + "]");
      if (rank) rank.textContent = student["rank" + key.charAt(0).toUpperCase() + key.slice(1)] + " место";
    });
    root.querySelector("[data-profile-stage-count]").textContent = student.stages;
    root.querySelector("[data-profile-progress-bar]").style.width = student.progress + "%";
    root.querySelector("[data-profile-track]").textContent = student.course === 1
      ? ("Трек «" + student.track + "» выбран для карьерного маршрута.")
      : ("Активный профессиональный трек: " + student.track + ".");
    root.querySelector("[data-profile-path-title]").textContent = student.course === 1 ? "Карьерный маршрут" : "Профессиональный трек";

    var achievements = root.querySelector("[data-profile-achievements]");
    achievements.replaceChildren();
    student.achievements.forEach(function (item) {
      var badge = document.createElement("div");
      badge.className = "profile-badge";
      var icon = document.createElement("span"); icon.textContent = item.icon;
      var name = document.createElement("strong"); name.textContent = item.name;
      var date = document.createElement("small"); date.textContent = item.date;
      badge.append(icon, name, date); achievements.appendChild(badge);
    });
    var history = root.querySelector("[data-profile-history]");
    history.replaceChildren();
    student.history.forEach(function (item) {
      var row = document.createElement("div"); row.className = "list-item";
      var copy = document.createElement("div"); copy.style.flex = "1";
      var title = document.createElement("strong"); title.textContent = item.title;
      var detail = document.createElement("div"); detail.className = "muted small"; detail.textContent = item.detail;
      var amount = document.createElement("b"); amount.className = "profile-positive"; amount.textContent = item.amount;
      copy.append(title, detail); row.append(copy, amount); history.appendChild(row);
    });
    ["registrations", "orders"].forEach(function (key) {
      var target = root.querySelector("[data-profile-" + key + "]");
      if (!target) return;
      target.replaceChildren();
      (student[key] || []).forEach(function (text) {
        var row = document.createElement("div"); row.className = "list-item"; row.textContent = text; target.appendChild(row);
      });
      if (!student[key] || !student[key].length) target.textContent = key === "orders" ? "Заказов нет." : "Регистраций нет.";
    });
    var adjustment = root.querySelector("[data-profile-adjust]");
    if (adjustment) adjustment.reset();
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var method = (form.getAttribute("method") || "get").toLowerCase();
    event.preventDefault();
    if (form.id === "team-role-demo") {
      var roleNames = { organizer: "Организатор", researcher: "Исследователь", creator: "Создатель", communicator: "Коммуникатор" };
      var counts = { organizer: 0, researcher: 0, creator: 0, communicator: 0 };
      new FormData(form).forEach(function (value) { if (Object.prototype.hasOwnProperty.call(counts, value)) counts[value] += 1; });
      var rankedRoles = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
      var result = form.querySelector("[data-team-role-result]");
      result.hidden = false;
      result.innerHTML = "<h3>Твои выраженные роли</h3><p><strong>" + roleNames[rankedRoles[0]] + "</strong> · " + Math.round(counts[rankedRoles[0]] * 100 / 4) + "%" +
        (counts[rankedRoles[1]] ? "<br>Также проявляется: " + roleNames[rankedRoles[1]] + " · " + Math.round(counts[rankedRoles[1]] * 100 / 4) + "%" : "") +
        "</p><small class=\"admin-note\">Это ориентир для обсуждения в команде, не психологическая оценка.</small>";
      return;
    }
    if (form.matches("[data-profile-adjust]")) {
      var delta = Number(form.elements.amount.value || 0);
      var reason = form.elements.reason.value.trim();
      toast(delta && reason ? "Демо: операция показана, баланс и журнал не изменены." : "Укажите ненулевую сумму и причину операции.");
      if (delta && reason) form.reset();
      return;
    }
    if (form.id === "activity-demo-form" || form.id === "shop-demo-form") {
      var submittedDialog = form.closest("dialog");
      if (submittedDialog) submittedDialog.close();
      form.reset();
      toast(form.id === "activity-demo-form"
        ? "Демо: активность не создана. Данные не сохраняются и не отправляются."
        : "Демо: изменения каталога не сохранены.");
      return;
    }
    if (method === "get") {
      if (form.querySelector('[name="track"]')) applyEmployerFilter(form);
      else if (form.querySelector('[name="only"]')) applyMeetingFilter(form);
      else if (form.querySelector('[name="cat"], [name="mine"]')) applyActivities(form);
      else if (isDemoFilter(form)) applySearch(form);
      else toast("Фильтр применён в демо. Данные не отправляются.");
      return;
    }
    var submitter = event.submitter;
    var label = submitter ? submitter.textContent.trim() : "";
    if (/отправить|сохранить|записаться|отменить|проголосовать|ответить|обменять|выйти|изменить|прислать|прочитать|попробовать|проверить|показать профиль/i.test(label)) {
      toast("Демо-режим: это действие изменяет данные, поэтому ничего не отправлено.");
    } else {
      toast("Демо-режим: форма не отправлена и данные не сохранены.");
    }
  }, true);

  document.addEventListener("change", function (event) {
    if (event.target.matches('#activity-demo-form [name="groups"], #activity-demo-form [name="tracks"]')) updateGroupSummary(event.target.form);
    if (event.target.matches('#activity-demo-form [name="activity_type"]')) updateActivityFields(event.target.form);
  });

  document.addEventListener("reset", function (event) {
    if (event.target.id === "activity-demo-form") setTimeout(function () { updateGroupSummary(event.target); updateActivityFields(event.target); }, 0);
  });

  function download(name, content, type) {
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  document.addEventListener("click", function (event) {
    var openTeamRole = event.target.closest("[data-open-team-role]");
    if (openTeamRole) {
      var teamDialog = document.getElementById("team-role-dialog");
      if (teamDialog && typeof teamDialog.showModal === "function") teamDialog.showModal();
      return;
    }

    var demoQrButton = event.target.closest("[data-qr-scan]");
    if (demoQrButton) {
      event.preventDefault();
      toast("Отметка по QR доступна в основной платформе. Эта демонстрационная версия не сохраняет посещения.");
      return;
    }

    var shopFilter = event.target.closest("[data-demo-shop-filter]");
    if (shopFilter) {
      event.preventDefault();
      var shopKind = shopFilter.dataset.demoShopFilter || "";
      applyShopCategory(shopKind);
      var nextUrl = new URL(location.href);
      if (shopKind) nextUrl.searchParams.set("category", shopKind);
      else nextUrl.searchParams.delete("category");
      history.replaceState(null, "", nextUrl.pathname + nextUrl.search + nextUrl.hash);
      return;
    }

    var closeButton = event.target.closest("[data-demo-close]");
    if (closeButton) {
      event.preventDefault();
      var dialogToClose = closeButton.closest("dialog");
      if (dialogToClose) dialogToClose.close();
      return;
    }

    var adjustToggle = event.target.closest("[data-profile-adjust-toggle]");
    if (adjustToggle) {
      var adjustmentForm = adjustToggle.closest(".student-profile-view").querySelector("[data-profile-adjust]");
      if (adjustmentForm) {
        adjustmentForm.hidden = !adjustmentForm.hidden;
        adjustToggle.setAttribute("aria-expanded", String(!adjustmentForm.hidden));
      }
      return;
    }

    var exportButton = event.target.closest("[data-profile-export]");
    if (exportButton) {
      var profile = exportButton.closest(".student-profile-view");
      var exportName = profile.querySelector("[data-profile-name]").textContent.trim();
      var exportData = ["Профиль студента: " + exportName,
        "Группа: " + profile.querySelector("[data-profile-group]").textContent,
        "Направление: " + profile.querySelector("[data-profile-direction]").textContent,
        "Курс: " + profile.querySelector("[data-profile-course]").textContent,
        "Баланс степов: " + profile.querySelector("[data-profile-balance]").textContent,
        "Всего заработано: " + profile.querySelector("[data-profile-earned]").textContent,
        "Достижений: " + profile.querySelector("[data-profile-achievement-count]").textContent,
        "Портфолио и резюме: демонстрационный экспорт"].join("\n");
      download("portfolio-demo.txt", exportData, "text/plain;charset=utf-8");
      toast("Скачан пример выгрузки. Это демонстрационные данные.");
      return;
    }

    var profileButton = event.target.closest("[data-student-profile]");
    if (profileButton) {
      var profileDialog = document.getElementById("student-profile-dialog");
      if (profileDialog && typeof profileDialog.showModal === "function") {
        var profile = profileDialog.querySelector("[data-student-card]");
        if (profile) profile.hidden = true;
        fillStudentProfile(profileButton.dataset.studentProfile, profileDialog);
        profileDialog.showModal();
      }
      return;
    }

    var reviewToggle = event.target.closest("[data-review-toggle]");
    if (reviewToggle) {
      var reviewDetail = document.getElementById(reviewToggle.dataset.reviewToggle);
      if (reviewDetail) {
        reviewDetail.hidden = !reviewDetail.hidden;
        reviewToggle.setAttribute("aria-expanded", String(!reviewDetail.hidden));
        reviewToggle.textContent = reviewDetail.hidden
          ? (reviewToggle.dataset.reviewOpen || "Открыть материалы")
          : (reviewToggle.dataset.reviewClose || "Свернуть материалы");
      }
      return;
    }

    var reviewDecision = event.target.closest("[data-demo-write]");
    if (reviewDecision) {
      toast("Демо-режим: решение не отправлено и не сохранено.");
      return;
    }

    var shopButton = event.target.closest("[data-shop-add], [data-shop-edit]");
    if (shopButton) {
      var shopDialog = document.getElementById("shop-dialog");
      var shopForm = document.getElementById("shop-demo-form");
      if (shopDialog && shopForm && typeof shopDialog.showModal === "function") {
        shopForm.reset();
        if (shopButton.hasAttribute("data-shop-edit")) {
          shopForm.elements.product_title.value = shopButton.dataset.productName || "";
          shopForm.elements.product_kind.value = shopButton.dataset.productKind || "merch";
          shopForm.elements.product_category.value = shopButton.dataset.productCategory || "accessories";
          shopForm.elements.product_price.value = shopButton.dataset.productPrice || 0;
          shopForm.elements.product_stock.value = shopButton.dataset.productStock || 0;
          document.getElementById("shop-dialog-title").textContent = "Редактировать товар";
        } else {
          document.getElementById("shop-dialog-title").textContent = "Добавить товар";
        }
        shopDialog.showModal();
        shopForm.elements.product_title.focus();
      }
      return;
    }

    var ics = event.target.closest("[data-demo-ics]");
    if (ics) {
      event.preventDefault();
      function toIcs(value) {
        var date = new Date(value);
        if (isNaN(date.getTime())) date = new Date();
        return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
      }
      var title = (ics.dataset.title || "Событие 01:17").replace(/[,\n;]/g, " ");
      var place = (ics.dataset.place || "").replace(/[,\n;]/g, " ");
      var body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//01:17 Demo//RU", "BEGIN:VEVENT", "UID:demo-" + Date.now() + "@0117", "DTSTAMP:" + toIcs(new Date().toISOString()), "DTSTART:" + toIcs(ics.dataset.start), "DTEND:" + toIcs(ics.dataset.end), "SUMMARY:" + title, "LOCATION:" + place, "END:VEVENT", "END:VCALENDAR", ""].join("\r\n");
      download("event-0117.ics", body, "text/calendar;charset=utf-8");
      toast("Файл события скачан. Его можно добавить в календарь.");
      return;
    }

    var action = event.target.closest("[data-demo-action]");
    if (action) {
      event.preventDefault();
      var label = action.textContent.trim().toLocaleLowerCase("ru");
      if (label.indexOf("скачать отчёт") !== -1) {
        var rows = Array.prototype.slice.call(document.querySelectorAll(".admin-table tr"));
        var csv = rows.map(function (row) {
          return Array.prototype.slice.call(row.querySelectorAll("th,td")).map(function (cell) {
            return '"' + cell.innerText.replace(/"/g, '""').replace(/\s+/g, " ").trim() + '"';
          }).join(",");
        }).join("\r\n");
        download("0117-demo-report.csv", "\uFEFF" + csv, "text/csv;charset=utf-8");
        toast("Демонстрационный отчёт скачан.");
      } else if (label.indexOf("очеред") !== -1) {
        var queue = document.getElementById("demo-queue-details");
        if (queue) {
          queue.hidden = !queue.hidden;
          action.setAttribute("aria-expanded", String(!queue.hidden));
          toast(queue.hidden ? "Подробности очереди свернуты." : "Показаны заявки на проверку.");
        } else {
          toast("Очередь проверки доступна в рабочей панели колледжа.");
        }
      } else if (action.dataset.demoAction === "activity") {
        var dialog = document.getElementById("activity-dialog");
        var typeSelect = dialog && dialog.querySelector('[name="activity_type"]');
        if (dialog && typeof dialog.showModal === "function") {
          if (typeSelect && action.dataset.activityType) typeSelect.value = action.dataset.activityType;
          if (dialog) updateActivityFields(dialog.querySelector("#activity-demo-form"));
          dialog.showModal();
          var titleInput = dialog.querySelector('[name="title"]');
          if (titleInput) titleInput.focus();
        } else {
          toast("Форма создания активности недоступна в этом браузере.");
        }
      } else {
        toast("В реальной платформе это действие создаст запись. В демо данные не сохраняются.");
      }
      return;
    }

    var monthLink = event.target.closest(".calendar-month-head a");
    if (monthLink && monthLink.getAttribute("href").indexOf("?view=month") === 0) {
      event.preventDefault();
      shiftCalendar(monthLink.textContent.trim() === "←" ? -1 : 1);
      return;
    }

    var standaloneButton = event.target.closest('button[type="button"]');
    if (standaloneButton) {
      toast("Это действие доступно в рабочей версии платформы. В демо данные не изменяются.");
    }
  }, true);

  function shiftCalendar(delta) {
    var heading = document.querySelector(".calendar-month-head b");
    var calendar = document.getElementById("cal");
    if (!heading || !calendar) return;
    if (!calendar.dataset.demoOriginal) calendar.dataset.demoOriginal = calendar.innerHTML;
    var match = heading.textContent.trim().toLocaleLowerCase("ru").match(/^([а-яё]+)\s+(\d{4})$/);
    if (!match) { toast("Не удалось сменить месяц в демо."); return; }
    var month = monthNames.indexOf(match[1]) + delta;
    var year = Number(match[2]);
    if (month < 0) { month = 11; year -= 1; }
    if (month > 11) { month = 0; year += 1; }
    heading.textContent = monthNames[month][0].toLocaleUpperCase("ru") + monthNames[month].slice(1) + " " + year;
    var initial = calendar.dataset.demoInitialHeading || "";
    if (!initial) calendar.dataset.demoInitialHeading = match[1] + " " + match[2];
    var initialName = monthNames.indexOf((calendar.dataset.demoInitialHeading.split(" ")[0] || "").toLocaleLowerCase("ru"));
    var initialYear = Number(calendar.dataset.demoInitialHeading.split(" ")[1]);
    if (month === initialName && year === initialYear) {
      calendar.innerHTML = calendar.dataset.demoOriginal;
      applyActivities(document.querySelector(".activity-filters form") || document.createElement("form"));
      return;
    }
    calendar.innerHTML = "";
    var first = new Date(Date.UTC(year, month, 1));
    var offset = (first.getUTCDay() + 6) % 7;
    var days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
    var cells = Math.ceil((offset + days) / 7) * 7;
    for (var i = 0; i < cells; i += 1) {
      var number = i - offset + 1;
      var day = document.createElement("div");
      day.className = "day" + (number < 1 || number > days ? " out" : "");
      var value = number < 1 ? new Date(Date.UTC(year, month, number)) : number > days ? new Date(Date.UTC(year, month + 1, number - days)) : null;
      var label = value ? value.getUTCDate() : number;
      day.innerHTML = '<div class="num">' + label + '</div>';
      calendar.appendChild(day);
    }
    toast("Календарь: " + monthNames[month] + " " + year + ". В демо для этого месяца событий нет.");
  }

  function addRoleChooser() {
    var path = location.pathname.replace(/\/+$/, "");
    if (path !== base && !(base === "" && path === "")) return;
    var main = document.querySelector("main");
    var hero = main && main.querySelector(".dashboard-hero");
    if (!hero || document.querySelector(".demo-role-chooser")) return;
    var section = document.createElement("section");
    section.className = "dashboard-section demo-role-chooser";
    section.innerHTML = '<div class="dashboard-section-head"><div><span class="eyebrow">ДЕМО ПЛАТФОРМЫ</span><h2>Выберите роль</h2></div><span class="muted">Данные вымышленные</span></div><div class="dashboard-columns"><a class="card dashboard-card" href="' + base + '/" style="display:block;text-decoration:none;color:inherit;border:2px solid var(--yellow)"><span class="eyebrow">СТУДЕНТ</span><h3>Демо студента</h3><p class="muted">События, задания, магазин и личный кабинет.</p><strong>Открыто сейчас →</strong></a><a class="card dashboard-card" href="' + base + '/admin-demo/" style="display:block;text-decoration:none;color:inherit"><span class="eyebrow">АДМИНИСТРАТОР</span><h3>Демо администратора</h3><p class="muted">Сводка колледжа, модерация и активность студентов.</p><strong>Открыть панель →</strong></a></div>';
    hero.parentNode.insertBefore(section, hero);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { addRoleChooser(); initShopCategory(); updateGroupSummary(document.getElementById("activity-demo-form")); updateActivityFields(document.getElementById("activity-demo-form")); initTrackDetails(); initTrackList(); });
  } else {
    addRoleChooser();
    initShopCategory();
    updateGroupSummary(document.getElementById("activity-demo-form"));
    updateActivityFields(document.getElementById("activity-demo-form"));
    initTrackDetails();
    initTrackList();
  }
})();
