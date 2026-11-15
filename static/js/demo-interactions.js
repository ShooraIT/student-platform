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

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var method = (form.getAttribute("method") || "get").toLowerCase();
    event.preventDefault();
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

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addRoleChooser);
  else addRoleChooser();
})();
