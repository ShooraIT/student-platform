(function () {
  var root = document.getElementById("merch-catalog");
  if (!root) return;
  var script = document.currentScript;
  var base = (script && script.dataset.base) || "";
  var dialog = document.getElementById("merch-preview-dialog");
  var itemsById = {};
  function imageMarkup(item) {
    if (!item.image) return '<div class="merch-art-missing"><span>макет ожидается</span><b>01:17</b></div>';
    return '<img src="' + base + "/static/" + item.image + '" alt="" loading="lazy">';
  }
  function render(items) {
    root.innerHTML = "";
    items.forEach(function (item) {
      itemsById[item.id] = item;
      var card = document.createElement("button");
      card.type = "button"; card.className = "card product-card merch-card";
      card.dataset.demoShopCategory = item.category || "accessories"; card.dataset.merchPreview = item.id;
      var photo = document.createElement("span"); photo.className = "product-photo merch-photo"; photo.innerHTML = imageMarkup(item);
      var status = document.createElement("span"); status.className = "sticker terra"; status.textContent = item.sale_status === "award_only" ? "НАГРАДА" : "МАКЕТ"; photo.appendChild(status);
      var title = document.createElement("strong"); title.textContent = item.title;
      var description = document.createElement("span"); description.className = "muted small"; description.textContent = item.track_title || (item.type === "reward" ? "Выдаётся как награда колледжа" : "Каталог 01:17");
      var bottom = document.createElement("span"); bottom.className = "spread merch-card-bottom";
      var price = document.createElement("span"); price.className = "reward"; price.textContent = item.sale_status === "award_only" ? "Только награда" : "Цена настраивается";
      var arrow = document.createElement("span"); arrow.className = "btn round small"; arrow.textContent = "↗"; bottom.append(price, arrow);
      card.append(photo, title, description, bottom); root.appendChild(card);
    });
  }
  fetch(root.dataset.catalogUrl).then(function (r) { if (!r.ok) throw new Error("catalog"); return r.json(); }).then(function (data) { render(data.items || []); }).catch(function () { root.innerHTML = '<p class="muted">Каталог временно недоступен. Обновите страницу позже.</p>'; });
  root.addEventListener("click", function (event) {
    var card = event.target.closest("[data-merch-preview]"); if (!card || !dialog) return;
    var item = itemsById[card.dataset.merchPreview]; if (!item) return;
    document.getElementById("merch-preview-title").textContent = item.title;
    document.getElementById("merch-preview-track").textContent = item.track_title || (item.sale_status === "award_only" ? "Награда колледжа" : "Общая коллекция 01:17");
    document.getElementById("merch-preview-label").textContent = item.label || "Макет и параметры выдачи согласуются";
    document.getElementById("merch-preview-media").innerHTML = imageMarkup(item); dialog.showModal();
  });
  document.addEventListener("click", function (event) { if (event.target.closest("[data-merch-close]") && dialog) dialog.close(); });
  if (dialog) dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
}());
