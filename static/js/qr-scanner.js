(function () {
  "use strict";

  var button = document.querySelector("[data-qr-scan]");
  var dialog = document.getElementById("qr-scan-dialog");
  var video = document.getElementById("qr-scan-video");
  var status = document.getElementById("qr-scan-status");
  if (!button || !dialog || !video || !status) return;

  var stream = null;
  var detector = null;
  var frame = null;
  var scanning = false;

  function setStatus(message) {
    status.textContent = message;
  }

  function stopCamera() {
    scanning = false;
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
    stream = null;
    video.srcObject = null;
  }

  function isCheckinUrl(value) {
    try {
      var scanned = new URL(value, window.location.href);
      var prefix = (button.dataset.checkinPrefix || "/events/").replace(/\/+$/, "");
      var escapedPrefix = prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      var allowedPath = new RegExp("^" + escapedPrefix + "/\\d+/qr/$");
      if (scanned.origin !== window.location.origin || !allowedPath.test(scanned.pathname) || !scanned.searchParams.get("t")) return null;
      return scanned.href;
    } catch (error) {
      return null;
    }
  }

  async function scanFrame() {
    if (!scanning) return;
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      try {
        var codes = await detector.detect(video);
        for (var i = 0; i < codes.length; i += 1) {
          var destination = isCheckinUrl(codes[i].rawValue);
          if (destination) {
            scanning = false;
            stopCamera();
            setStatus("QR-код принят. Открываю отметку посещения…");
            window.location.assign(destination);
            return;
          }
          if (codes[i].rawValue) setStatus("Это не QR-код отметки посещения 01:17. Наведите камеру на код мероприятия.");
        }
      } catch (error) {
        // A frame can fail to decode while the camera is moving; keep scanning.
      }
    }
    frame = requestAnimationFrame(scanFrame);
  }

  async function startCamera() {
    stopCamera();
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Браузер не может открыть камеру на этой странице. Откройте камеру телефона и наведите её на QR-код мероприятия.");
      return;
    }
    if (!("BarcodeDetector" in window)) {
      setStatus("Встроенное сканирование недоступно в этом браузере. Откройте камеру телефона и наведите её на QR-код мероприятия.");
      return;
    }
    try {
      var formats = await window.BarcodeDetector.getSupportedFormats();
      if (formats.indexOf("qr_code") === -1) {
        setStatus("Этот браузер не распознаёт QR-коды. Используйте камеру телефона.");
        return;
      }
      detector = new window.BarcodeDetector({ formats: ["qr_code"] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      video.srcObject = stream;
      await video.play();
      scanning = true;
      setStatus("Наведите камеру на QR-код мероприятия.");
      scanFrame();
    } catch (error) {
      stopCamera();
      setStatus(error && error.name === "NotAllowedError"
        ? "Нет доступа к камере. Разрешите его в настройках браузера или воспользуйтесь камерой телефона."
        : "Не удалось запустить сканер. Проверьте доступ к камере или отсканируйте QR камерой телефона.");
    }
  }

  button.addEventListener("click", function () {
    setStatus("Подключаю камеру…");
    dialog.showModal();
    startCamera();
  });
  dialog.addEventListener("close", stopCamera);
  dialog.addEventListener("cancel", stopCamera);
  dialog.querySelectorAll("[data-qr-close]").forEach(function (closeButton) {
    closeButton.addEventListener("click", function () { dialog.close(); });
  });
})();
