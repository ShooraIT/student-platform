// Подключение пуш-уведомлений на странице «Настройки уведомлений»
(function () {
  const box = document.getElementById("push-box");
  if (!box) return;
  const key = box.dataset.key;
  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  const status = document.getElementById("push-status");
  const btnOn = document.getElementById("push-on");
  const btnOff = document.getElementById("push-off");
  const btnTest = document.getElementById("push-test");
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;

  function show(text, on) {
    status.textContent = text;
    btnOn.hidden = on !== false;
    btnOff.hidden = on !== true;
    if (btnTest) btnTest.hidden = on !== true;
  }

  function b64ToBytes(s) {
    const pad = "=".repeat((4 - (s.length % 4)) % 4);
    const raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }

  async function post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error("server " + r.status);
  }

  async function init() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      if (ios && !standalone) {
        show("На iPhone пуш работает только для сайта, добавленного на экран «Домой»: нажмите «Поделиться» → «На экран Домой», откройте Степы с иконки и включите уведомления здесь.", null);
      } else {
        show("Этот браузер не поддерживает пуш-уведомления. Уведомления будут приходить на сайт (🔔).", null);
      }
      return;
    }
    if (Notification.permission === "denied") {
      show("Уведомления запрещены в настройках браузера. Разрешите их для этого сайта и обновите страницу.", null);
      return;
    }
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await post("/notifications/push/subscribe/", sub.toJSON()); // освежить привязку к аккаунту
      show("Пуш-уведомления включены на этом устройстве.", true);
    } else {
      show("Пуш-уведомления на этом устройстве выключены.", false);
    }
  }

  btnOn.addEventListener("click", async () => {
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { show("Вы не разрешили уведомления. Их можно включить в настройках браузера.", false); return; }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
      await post("/notifications/push/subscribe/", sub.toJSON());
      show("Готово! Пуш-уведомления включены на этом устройстве.", true);
    } catch (e) {
      show("Не удалось включить уведомления: " + e.message, false);
    }
  });

  btnOff.addEventListener("click", async () => {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await post("/notifications/push/unsubscribe/", { endpoint: sub.endpoint });
      await sub.unsubscribe();
    }
    show("Пуш-уведомления на этом устройстве выключены.", false);
  });

  init().catch((e) => show("Ошибка: " + e.message, null));
})();
